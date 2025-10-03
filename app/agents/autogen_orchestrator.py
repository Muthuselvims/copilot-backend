import os
import logging
from typing import Dict, Any, Optional, List  # Added List import
from openai import OpenAI
import re
import json
import requests
from datetime import datetime
from app.services.agent_servies import (
    load_agent_config,
    is_question_supported_by_capabilities,
    detect_output_format,
)
    
from app.utils.schema_reader import get_schema_and_sample_data
from app.services.agent_servies import (
    validate_question_safety,
    validate_ethical_use,
    is_sql_read_only,
    enforce_sql_row_limit,
    validate_sql_tables,
)
from app.db.sql_connection import execute_sql_query
from app.utils.ppt_generator import (
    generate_ppt,
    generate_excel,
    generate_word,
    generate_insights,
    generate_direct_response,
)
import numpy as np
from app.utils.message_bus import get_message_bus
from app.utils.message_schemas import AgentEvent

logger = logging.getLogger("app.agents.autogen_orchestrator")


def _get_openai_client() -> OpenAI:
    # Avoid accidental routing to our own API by default
    use_custom = os.getenv("USE_OPENAI_CUSTOM_BASE", "false").lower() == "true"
    base_url = os.getenv("OPENAI_BASE_URL") if use_custom else "https://api.openai.com/v1"
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url)

def _get_model() -> str:
    return os.getenv("AUTOGEN_MODEL", "gpt-4o-mini")

def _extract_select_query(raw_text: str) -> str:
    """Extract the first read-only SELECT statement from LLM output.
    - Strips code fences and commentary
    - Takes content starting at the first 'select' (case-insensitive)
    - Stops at the first semicolon if present
    """
    if not raw_text:
        return ""
    text = raw_text.strip()
    # Remove code fences
    if text.startswith("```"):
        text = text.strip("`\n").split("\n", 1)[-1]
    # Find first occurrence of 'select'
    lowered = text.lower()
    idx = lowered.find("select")
    if idx == -1:
        return ""
    text = text[idx:]
    # Cut at first semicolon if any
    semi = text.find(";")
    if semi != -1:
        text = text[:semi]
    # Single line cleanup
    return " ".join(text.split())

def _strip_non_tsql_limits(sql_text: str) -> str:
    """Remove non-T-SQL limit syntaxes like LIMIT/FETCH FIRST to avoid conflicts with TOP."""
    if not sql_text:
        return sql_text
    cleaned = sql_text
    # Remove MySQL/Postgres LIMIT n
    cleaned = re.sub(r"(?i)\s+limit\s+\d+\s*$", "", cleaned)
    # Remove FETCH FIRST n ROW ONLY (DB2/Oracle style)
    cleaned = re.sub(r"(?i)\s+fetch\s+first\s+\d+\s+rows?\s+only\s*$", "", cleaned)
    # Remove OFFSET ... ROWS [FETCH NEXT n ROWS ONLY]
    cleaned = re.sub(r"(?i)\s+offset\s+\d+\s+rows(\s+fetch\s+next\s+\d+\s+rows\s+only)?\s*$", "", cleaned)
    # Remove trailing semicolon
    cleaned = re.sub(r";\s*$", "", cleaned)
    return cleaned

def run_autogen_orchestration(
    question: str,
    agent_name: Optional[str] = None,
    created_by: Optional[str] = None,
    encrypted_filename: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    previous_results: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    # Step 1: Get schema
    structured_schema, _, _ = get_schema_and_sample_data()
    logger.info("Structured schema loaded", extra={"tables": list(structured_schema.keys())})
    if not structured_schema:
        return {"error": "No database schema available"}

    # Step 2: OpenAI setup
    client = _get_openai_client()
    model = _get_model()

    # Step 3: Add context
    context_str = ""
    if context:
        context_str = "\n\nContext from previous agents:\n"
        for key, value in context.items():
            context_str += f"{key}: {str(value)[:200]}...\n"

    if previous_results:
        context_str += "\n\nPrevious agent results:\n"
        for result in previous_results:
            agent_name = result.get("agent", "Unknown")

            def safe_truncate(text, max_length):
                if len(text) <= max_length:
                    return text
                truncated = text[:max_length]
                if " " in truncated:
                    truncated = truncated.rsplit(" ", 1)[0]
                return truncated

            answer = safe_truncate(result.get("answer", ""), 200)
            context_str += f"{agent_name}: {answer}...\n"

    # Step 4: Planning prompt
    plan_prompt = (
        "You are a planning assistant. Decide if a file (ppt/excel/word) is needed and "
        "draft a clear, concise plan for getting the data and presenting it."
        f"\nUser question: {question}"
        f"{context_str}"
        f"\nAllowed tables: {list(structured_schema.keys())}"
    )

    try:
        plan_resp = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a helpful planning assistant."},
                {"role": "user", "content": plan_prompt},
            ],
        )
        plan_text = (plan_resp.choices[0].message.content or "").strip()
        logger.info("Plan generated by GPT", extra={"plan": plan_text})
    except Exception as e:
        logger.exception("Failed to generate plan", extra={"question": question})
        return {"error": f"Planning failed: {str(e)}"}

    # Step 5: SQL generation
    sql_prompt = (
        "Generate exactly one SQL Server SELECT query only.\n"
        "Requirements:\n"
        "- Read-only (SELECT only).\n"
        "- No comments, no explanation, no CTE, no DDL/DML.\n"
        "- Do NOT include a trailing semicolon.\n"
        "- Use only these tables/columns: " + str(structured_schema) + "\n"
        f"{context_str}"
        "Task: " + question
    )

    try:
        attempt = 0
        last_err = None
        while attempt < 2:
            sql_resp = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": "You generate a single SQL Server SELECT query only."},
                    {"role": "user", "content": sql_prompt},
                ],
            )
            if not sql_resp.choices:
                return {"error": "No SQL generated by LLM"}

            sql_text = (sql_resp.choices[0].message.content or "").strip()
            sql_text = _extract_select_query(sql_text)
            sql_text = _strip_non_tsql_limits(sql_text)

            if not is_sql_read_only(sql_text):
                return {"error": "Generated SQL not read-only"}

            sql_text = enforce_sql_row_limit(sql_text)
            ok_tables, bad = validate_sql_tables(sql_text, list(structured_schema.keys()))
            if not ok_tables:
                # Ask model to regenerate constrained to allowed columns only
                attempt += 1
                last_err = {"error": "Unauthorized table access", "tables": bad}
                sql_prompt_regen = sql_prompt + "\nRegenerate using only allowed tables/columns."
                sql_prompt = sql_prompt_regen
                continue
            break
        else:
            return last_err or {"error": "SQL generation failed"}

    except Exception as e:
        logger.exception("SQL generation failed", extra={"question": question})
        return {"error": f"SQL generation failed: {str(e)}"}

    # Step 6: Execute SQL
    try:
        df = execute_sql_query(sql_text)
        if df is None or df.empty:
            return {"error": "No data returned from SQL query"}
    except ConnectionError as e:
        logger.error(f"Database connection error: {str(e)}")
        return {"error": f"Database connection failed: {str(e)}", "sql": sql_text}
    except ValueError as e:
        # Invalid column error - regenerate SQL with actual schema
        if "Invalid column name" in str(e):
            logger.warning("Invalid column detected, regenerating SQL", extra={"error": str(e)})
            # Get actual columns for the tables used
            used_tables = []
            for table in structured_schema.keys():
                if table.lower() in sql_text.lower():
                    used_tables.append(table)
            
            if used_tables:
                actual_columns = []
                for table in used_tables:
                    actual_columns.extend([f"{table}.{col}" for col in structured_schema[table]])
                
                # Regenerate with actual columns
                sql_prompt_fixed = (
                    f"Generate exactly one SQL Server SELECT query only.\n"
                    f"Requirements:\n"
                    f"- Read-only (SELECT only).\n"
                    f"- No comments, no explanation, no CTE, no DDL/DML.\n"
                    f"- Do NOT include a trailing semicolon.\n"
                    f"- Use ONLY these exact columns: {', '.join(actual_columns)}\n"
                    f"- Task: {question}\n"
                    f"- Previous error: {str(e)}"
                )
                
                try:
                    sql_resp_fixed = client.chat.completions.create(
                        model=model,
                        temperature=0,
                        messages=[
                            {"role": "system", "content": "You generate a single SQL Server SELECT query only using the exact columns provided."},
                            {"role": "user", "content": sql_prompt_fixed},
                        ],
                    )
                    sql_text = (sql_resp_fixed.choices[0].message.content or "").strip()
                    sql_text = _extract_select_query(sql_text)
                    sql_text = _strip_non_tsql_limits(sql_text)
                    
                    if not is_sql_read_only(sql_text):
                        return {"error": "Generated SQL not read-only"}
                    
                    sql_text = enforce_sql_row_limit(sql_text)
                    ok_tables, bad = validate_sql_tables(sql_text, list(structured_schema.keys()))
                    if not ok_tables:
                        return {"error": "Unauthorized table access after regeneration", "tables": bad}
                    
                    # Retry execution with fixed SQL
                    df = execute_sql_query(sql_text)
                    if df is None or df.empty:
                        return {"error": "No data returned from regenerated SQL query"}
                        
                except Exception as regen_e:
                    logger.exception("SQL regeneration failed", extra={"original_error": str(e)})
                    return {"error": f"SQL regeneration failed: {str(regen_e)}"}
            else:
                return {"error": f"Database error: {str(e)}"}
        else:
            raise  # Re-raise if not a column error

    # Clean data
    df_clean = df.replace([np.inf, -np.inf], np.nan)
    for col in df_clean.select_dtypes(include=["object"]).columns:
        df_clean[col] = df_clean[col].fillna("null")

    # Step 7: Generate answer
    answer = generate_direct_response(question, df_clean)
    insights, recs = generate_insights(df_clean)

    # Step 8: Generate file (if agent has capabilities)
    file_path = None
    file_type = None
    if agent_name:
        agent_cfg = load_agent_config(agent_name)
        if agent_cfg:
            fmt = detect_output_format((question or "") + " " + (plan_text or ""))
            required_capability = {
                "ppt": "Generate output as PPT",
                "excel": "Generate output as Excel",
                "word": "Generate output as Word",
            }
            capabilities = getattr(agent_cfg, "capabilities", [])
            if fmt in required_capability and required_capability[fmt] in capabilities:
                include_charts = any(k in question.lower() for k in ["chart", "graph", "visual", "visualize"])
                try:
                    if fmt == "ppt":
                        file_path = generate_ppt(question, df_clean, include_charts=include_charts)
                        file_type = "ppt"
                    elif fmt == "excel":
                        file_path = generate_excel(df_clean, question, include_charts=include_charts)
                        file_type = "excel"
                    elif fmt == "word":
                        file_path = generate_word(df_clean, question, include_charts=include_charts)
                        file_type = "word"
                except Exception as e:
                    logger.exception(f"File generation failed for format '{fmt}'")

    # Step 9: Upload file (optional)
    result: Dict[str, Any] = {
        "plan": plan_text,
        "sql": sql_text,
        "preview_rows": df_clean.head(10).to_dict(orient="records"),
        "answer": answer,
        "insights": insights,
        "recommendations": recs,
    }

    if file_path and file_type:
        result[f"{file_type}_path"] = file_path
        if created_by and encrypted_filename:
            try:
                api_root = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/"
                save_url = f"{api_root}PostSavePPTDetailsV2"
                save_resp = requests.post(
                    save_url,
                    params={
                        "FileName": encrypted_filename,
                        "CreatedBy": created_by,
                        "Date": datetime.now().strftime('%Y-%m-%d'),
                    },
                    timeout=20,
                )
                if save_resp.status_code != 200:
                    result["upload_status"] = f"Metadata save failed: {save_resp.text[:300]}"
            except Exception as e:
                result["upload_status"] = f"Metadata error: {str(e)}"

            try:
                filtered_obj = {"slide": 1, "title": "Auto-generated Slide", "data": question}
                file_ext = {"ppt": "pptx", "excel": "xlsx", "word": "docx"}.get(file_type, "dat")
                filename_with_ext = f"{encrypted_filename}.{file_ext}"

                with open(file_path, "rb") as f:
                    files = {
                        "file": (
                            filename_with_ext,
                            f,
                            {
                                "ppt": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            }[file_type],
                        ),
                        "content": (None, json.dumps({"content": [filtered_obj]}), "application/json"),
                    }

                    upload_url = f"{api_root}UpdatePptFileV2"
                    upload_resp = requests.post(
                        upload_url,
                        params={"FileName": encrypted_filename, "CreatedBy": created_by},
                        files=files,
                        timeout=60,
                    )
                    result["upload_status"] = (
                        f"{file_type.upper()} uploaded successfully"
                        if upload_resp.status_code == 200
                        else f"Upload failed: {upload_resp.status_code}"
                    )
                    result["upload_response"] = upload_resp.text
            except Exception as e:
                logger.exception(f"Exception during file upload for '{file_type}': {e}")
                result["upload_status"] = f"Upload error: {str(e)}"

    # Publish orchestration completion event before return
    try:
        bus = get_message_bus()
        bus.publish(
            AgentEvent(
                topic="agent.orchestration.completed",
                payload={
                    "question": question,
                    "agent": agent_name,
                    "produced_file_type": file_type,
                    "has_file": bool(file_path),
                },
                correlation_id=None,
            )
        )
    except Exception:
        logger.exception("Failed to publish orchestration completion event")

    return result
