# agent_services.py

import os
import json
import numpy as np
import requests
from datetime import datetime

from app.db.sql_connection import execute_sql_query
from app.utils.ppt_generator import generate_ppt, generate_excel, generate_word, generate_insights
from app.utils.schema_reader import get_schema_and_sample_data, get_db_schema
from app.utils.agent_builder import validate_agent_role, generate_sample_prompts, VALID_ROLES
from app.utils.gpt_utils import generate_sql_query
from app.utils.llm_validator import validate_purpose_and_instructions
from app.models.agent import AgentConfig

AGENT_DIR = "agents"
os.makedirs(AGENT_DIR, exist_ok=True)

ALLOWED_CAPABILITIES = [
    "Summarize results", "Generate output as text", "Generate output as PPT",
    "Generate output as Excel", "Generate output as Word", "Highlight anomalies",
    "Generate visual reports", "Provide data-driven recommendations",
    "Assist with data analysis", "Create data-driven insights", "Automate repetitive tasks",
    "Support decision-making", "Charts and graphs", "Data validation", "Data visualization"
]


def detect_output_format(question: str) -> str:
    q = question.lower()
    if any(x in q for x in ["ppt", "pptx", "presentation"]):
        return "ppt"
    elif any(x in q for x in ["excel", "xlsx"]):
        return "excel"
    elif any(x in q for x in ["word", "doc", "docx"]):
        return "word"
    return "none"


def save_agent_config(agent_config: AgentConfig):
    path = f"{AGENT_DIR}/{agent_config.name}.json"
    with open(path, "w") as f:
        json.dump(agent_config.dict(), f, indent=2)
    return {"message": "Agent config saved", "path": path, "agent": agent_config.dict()}


async def create_conversational_agent(data):
    name = data.get("name")
    role = data.get("role")
    tone = data.get("tone", "neutral")
    knowledge_base = data.get("knowledge_base", [])
    frequency = data.get("frequency", "Weekly")
    schedule_time = data.get("time", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    output_method = data.get("output_method", "PPT")

    structured_schema, schema_text, sample_data = get_schema_and_sample_data()
    if not schema_text:
        return {"error": "❌ Failed to load DB schema for validation."}

    if not validate_agent_role(role, ""):
        return {
            "error": f"❌ Role '{role}' is not supported. Choose from: {', '.join(sorted(VALID_ROLES))}"
        }

    purpose = data.get("purpose", f"Assist with {role.lower()} tasks")
    instructions = data.get("instructions", [
        f"Provide insights and recommendations related to {role.lower()}.",
        "Use clear business language and examples.",
        "Ask clarifying questions if needed."
    ])
    capabilities = data.get("capabilities", ["Summarize results", "Generate output as PPT"])

    # ✅ Updated GPT-based validation
    # ✅ GPT-based validation of purpose & instructions
    validation_result = validate_purpose_and_instructions(purpose, instructions, structured_schema, sample_data)

    if not validation_result["success"]:
        return {
        "error": f"❌ LLM validation failed: {validation_result.get('error') or 'Unknown error.'}"
    }

    if not validation_result["purpose_valid"]:
        return {
        "error": "❌ The provided purpose is not valid based on the database schema or sample data.",
        "raw_response": validation_result["raw"]
    }

    if validation_result["invalid_instructions"]:
        return {
        "error": "❌ One or more instructions are invalid for this agent.",
        "invalid_instructions": validation_result["invalid_instructions"],
        "raw_response": validation_result["raw"]
    }


    for c in capabilities:
        if c not in ALLOWED_CAPABILITIES:
            return {"error": f"❌ Capability '{c}' not supported. Choose from: {ALLOWED_CAPABILITIES}"}

    sample_prompts = generate_sample_prompts(role, purpose)
    welcome_message = f"Hi, I'm your {role}. I'm here to help with {purpose.lower()}."

    agent_config = AgentConfig(
        name=name,
        role=role,
        task=purpose,
        purpose=purpose,
        tone=tone,
        knowledge_base=knowledge_base,
        schedule_enabled=True,
        frequency=frequency,
        time=schedule_time,
        output_method=output_method,
        instructions=instructions,
        capabilities=capabilities,
        welcome_message=welcome_message,
        sample_prompts=sample_prompts,
        system_prompt="You are a SQL assistant. Return only the query without explanation.",
        published=False
    )

    result = save_agent_config(agent_config)

    try:
        api_url = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/SaveAgentDetails"
        payload = {
            "Name": agent_config.name,
            "Role": agent_config.role,
            "Purpose": agent_config.purpose,
            "Instructions": " ".join(agent_config.instructions),
            "Capabilities": ", ".join(agent_config.capabilities),
            "WelcomeMessage": agent_config.welcome_message,
            "Tone": agent_config.tone,
            "SamplePrompts": " | ".join(agent_config.sample_prompts),
            "ScheduleEnabled": "Yes" if agent_config.schedule_enabled else "No",
            "Frequency": agent_config.frequency,
            "Time": agent_config.time,
            "OutputMethod": agent_config.output_method,
            "Published": "Yes" if agent_config.published else "No"
        }
        api_response = requests.post(api_url, json=payload)
        result["api_status"] = "✅ Agent saved to DB" if api_response.status_code == 200 else f"❌ DB error: {api_response.text}"
    except Exception as e:
        result["api_status"] = f"❌ API error: {str(e)}"

    return {
        "message": "Agent created successfully",
        "config": agent_config.dict(),
        "sample_prompts": sample_prompts,
        "path": result["path"],
        "db_status": result.get("api_status")
    }


async def test_agent_response(data):
    agent_name = data.get("agent_name")
    question = data.get("question")
    path = f"{AGENT_DIR}/{agent_name}.json"

    if not os.path.exists(path):
        return {"error": "❌ Agent not found"}

    with open(path, "r") as f:
        config = json.load(f)

    schema = get_db_schema()
    sql_query = generate_sql_query(question, schema, system_prompt=config.get("system_prompt"))
    df = execute_sql_query(sql_query)

    if df.empty:
        return {"error": "❌ No data returned"}

    df_clean = df.replace([np.inf, -np.inf], np.nan).fillna("null")
    insights, recs = generate_insights(df_clean)
    tone_prefix = f"Hello! I'm {config['name']}, your {config['role']}.\nUsing a {config['tone']} tone:"

    return {
        "sql_query": sql_query,
        "top_rows": df_clean.head(10).to_dict(orient="records"),
        "insights": insights,
        "recommendations": recs,
        "agent_response": f"{tone_prefix}\n\n{insights}\n\nRecommendations:\n{recs}"
    }


async def handle_agent_request(data):
    question = data.get("question")
    agent_name = data.get("agent_name")
    created_by = data.get("created_by")
    encrypted_filename = data.get("encrypted_filename")
    formatdata = data.get("formatdata", {})

    if not question:
        return {"error": "❌ Missing 'question'"}

    structured_schema, schema_text, sample_data = get_schema_and_sample_data()

    sql_query = generate_sql_query(question, structured_schema)
    result = execute_sql_query(sql_query)

    if result.empty:
        return {"error": "❌ Query returned no data"}

    result_cleaned = result.replace([np.inf, -np.inf], np.nan).fillna("null")
    response = {
        "sql_query": sql_query,
        "top_rows": result_cleaned.head(10).to_dict(orient="records")
    }

    output_format = detect_output_format(question)
    output_path = None

    if output_format == "ppt":
        output_path = generate_ppt(question, result_cleaned)
    elif output_format == "excel":
        output_path = generate_excel(result_cleaned, question)
    elif output_format == "word":
        output_path = generate_word(result_cleaned, question)

    if output_path:
        response[f"{output_format}_path"] = output_path

        try:
            api_root = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/"
            save_url = f"{api_root}PostSavePPTDetailsV2?FileName={encrypted_filename}&CreatedBy={created_by}&Date={datetime.now().strftime('%Y-%m-%d')}"
            save_response = requests.post(save_url)
            if save_response.status_code != 200:
                response["upload_status"] = f"Metadata save failed: {save_response.text}"
        except Exception as e:
            response["upload_status"] = f"Metadata error: {str(e)}"

        try:
            filtered_obj = {"slide": 1, "title": "Auto-generated Slide", "data": question}
            file_ext = {"ppt": "pptx", "excel": "xlsx", "word": "docx"}.get(output_format, "dat")
            filename_with_ext = f"{encrypted_filename}.{file_ext}"

            with open(output_path, "rb") as f:
                files = {
                    "file": (
                        filename_with_ext,
                        f,
                        {
                            "ppt": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        }[output_format]
                    ),
                    "content": (None, json.dumps({"content": [filtered_obj]}), "application/json")
                }

                upload_url = f"{api_root}UpdatePptFileV2?FileName={encrypted_filename}&CreatedBy={created_by}"
                upload_response = requests.post(upload_url, files=files)

                response["upload_status"] = (
                    f"{output_format.upper()} uploaded successfully"
                    if upload_response.status_code == 200
                    else f"Upload failed: {upload_response.status_code}"
                )
                response["upload_response"] = upload_response.text
        except Exception as e:
            response["upload_status"] = f"Upload error: {str(e)}"

    return response


def publish_agent(data):
    agent_name = data.get("agent_name")
    path = f"{AGENT_DIR}/{agent_name}.json"
    if not os.path.exists(path):
        return {"error": "❌ Agent config not found"}
    with open(path, "r+") as f:
        config = json.load(f)
        config["published"] = True
        f.seek(0)
        json.dump(config, f, indent=2)
        f.truncate()
    return {"message": "✅ Agent published"}


def schedule_agent(data):
    agent_name = data.get("agent_name")
    path = f"{AGENT_DIR}/{agent_name}.json"
    if not os.path.exists(path):
        return {"error": "❌ Agent config not found"}
    with open(path, "r+") as f:
        config = json.load(f)
        config["schedule_enabled"] = True
        config["frequency"] = data.get("frequency")
        config["time"] = data.get("time")
        config["output_method"] = data.get("output_method")
        f.seek(0)
        json.dump(config, f, indent=2)
        f.truncate()
    return {"message": "✅ Agent scheduled"}
