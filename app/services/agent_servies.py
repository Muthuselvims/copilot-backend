# agent_services.py

import os
import json
import numpy as np
import requests
from datetime import datetime
from collections import defaultdict

from app.db.sql_connection import execute_sql_query
from app.utils.ppt_generator import generate_ppt, generate_excel, generate_word, generate_insights
from app.utils.schema_reader import get_schema_and_sample_data, get_db_schema
from app.utils.agent_builder import validate_agent_role, generate_sample_prompts, VALID_ROLES
from app.utils.gpt_utils import generate_sql_query
from app.utils.gpt_utils import is_question_relevant_to_purpose
from app.utils.gpt_utils import serialize
from app.utils.llm_validator import validate_purpose_and_instructions
from app.agents.agent_conversation import  validate_capabilities

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



async def handle_agent_request(data : dict):
    incoming_config = data.get("agent_config")
    agent_name = incoming_config.get("name") if incoming_config else None
    question = data.get("question")
    structured_schema = data.get("structured_schema")
    sample_data = data.get("sample_data")
    encrypted_filename = data.get("encrypted_filename")
    created_by = data.get("created_by")
    formatdata = data.get("formatdata", {})

    if not all([question, agent_name, created_by, encrypted_filename]):
        return {"error": "❌ Missing one or more required fields: 'question', 'name', 'created_by', 'encrypted_filename'"}

    # ✅ Load existing agent config
    agent_config = load_agent_config(agent_name)
    if not agent_config:
        return {"error": f"❌ Agent '{agent_name}' not found"}

    
    # GPT-based semantic check
    is_relevant = await is_question_relevant_to_purpose(question, agent_config.purpose)
    if not is_relevant:
     return {"error": f"❌ Question does not align with agent's purpose: '{agent_config.purpose}'"}


    # ✅ Load schema and data
    structured_schema, schema_text, sample_data = get_schema_and_sample_data()

    # ✅ Generate SQL
    sql_query = generate_sql_query(question, structured_schema)
    result = execute_sql_query(sql_query)

    if result.empty:
        return {"error": "❌ Query returned no data"}

    # ✅ Clean result
    result_cleaned = result.replace([np.inf, -np.inf], np.nan).fillna("null")
    response = {
        "sql_query": sql_query,
        "top_rows": result_cleaned.head(10).to_dict(orient="records")
    }

    # ✅ Detect output format
    output_format = detect_output_format(question)
    output_path = None

    if output_format == "ppt":
        output_path = generate_ppt(question, result_cleaned)
    elif output_format == "excel":
        output_path = generate_excel(result_cleaned, question)
    elif output_format == "word":
        output_path = generate_word(result_cleaned, question)
    
    # ✅ Upload PPT/Excel/Word to external API
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

    return serialize(response)


# ✅ Test Agent
async def test_agent_response(agent_config: AgentConfig, structured_schema, sample_data, question
):
    #Convert dict to Pydantic model
    agent_config = AgentConfig(**agent_config)

    agent_name = agent_config.name
    question = question or (agent_config.sample_prompts[0] if agent_config.sample_prompts else "Give a summary of the data")

    sql_query = generate_sql_query(question, structured_schema)
    df = execute_sql_query(sql_query)

    if df.empty:
        return {"error": "❌ No data returned"}

    df_clean = df.replace([np.inf, -np.inf], np.nan).fillna("null")
    insights, recs = generate_insights(df_clean)

    tone_prefix = f"Hello! I'm {agent_name}, your {agent_config.role}.\nUsing a {agent_config.tone} tone:"

    return {
       # "sql_query": sql_query,
        "top_rows": df_clean.head(10).to_dict(orient="records"),
        "insights": insights,
        "recommendations": recs,
        "agent_response": f"{tone_prefix}\n\n{insights}\n\nRecommendations:\n{recs}"
    }


GET_AGENT_URL = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/GetAgentDetails"
PUBLISH_AGENT_URL = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/UpdateAgentDetails"

    
def publish_agent (agent_name):
    try:
        if not agent_name:
            return {"error": "Missing 'agent_name'"}

        # 1. Get all agents
        get_response = requests.get(GET_ALL_AGENTS_URL)
        if get_response.status_code != 200:
            return {"error": f"Failed to fetch agents. Status code: {get_response.status_code}"}

        agents = get_response.json().get("Table", [])
        normalized_agents = [{k.lower(): v for k, v in agent.items()} for agent in agents]

        # 2. Find agent by name
        matching_index = next(
            (i for i, agent in enumerate(normalized_agents)
             if agent.get("name", "").lower() == agent_name.lower()),
            None
        )
        if matching_index is None:
            return {"error": f"Agent '{agent_name}' not found."}

        # 3. Get original agent details
        original_agent = agents[matching_index]

        # 4. Build payload — Published = True
        payload = {
            "ExistingAgentName": agent_name,
            "NewAgentName": original_agent.get("Name", ""),
            "ExistingRole": original_agent.get("Role", ""),
            "NewRole": original_agent.get("Role", ""),
            "ExistingPurpose": original_agent.get("Purpose", ""),
            "NewPurpose": original_agent.get("Purpose", ""),
            "Published": "True"  # ✅ Set Published to True
        }

        # ✅ Log payload
        print("\n📤 Final Payload to PUBLISH_AGENT_URL:")
        print(json.dumps(payload, indent=2))

        # 5. Send POST request
        post_response = requests.post(PUBLISH_AGENT_URL, json=payload)

        print("📥 Status Code:", post_response.status_code)
        print("📥 Response Text:", post_response.text)

        # 6. Handle response
        if post_response.status_code == 200 and post_response.text.strip().lower() != "internal server error":
            try:
                response_json = post_response.json()
                return {
                    "message": f"✅ Agent '{agent_name}' published successfully",
                    "updated_config": response_json
                }
            except Exception as e:
                return {
                    "message": f"✅ Agent '{agent_name}' published successfully (non-JSON response)",
                    "updated_config": {
                        "raw_response": post_response.text,
                        "parse_error": str(e)
                    }
                }
        else:
            return {
                "error": f"❌ Failed to publish agent. Status code: {post_response.status_code}",
                "details": post_response.text
            }

    except Exception as e:
        return {"error": f"❌ Exception occurred: {str(e)}"}
    
def schedule_agent(data):
    agent_name = data.get("name")
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

from uuid import uuid4
from app.models.agent import AgentConfig
API_URL = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/GetAgentDetails"

def load_agent_config(name: str) -> AgentConfig:
    try:
        resp = requests.get(API_URL, params={"AgentName": name}, timeout=20)
        resp.raise_for_status()
        data = resp.json().get("Table", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching agent details: {e}")
        return None

    if not data:
        return None

    # Group by name
    grouped = defaultdict(list)
    for record in data:
        agent_name = record.get("Name")
        if agent_name:
            grouped[agent_name].append(record)

    entries = grouped.get(name)
    if not entries:
        return None

    for rec in entries:
        rec["_parsed_time"] = datetime.fromisoformat(rec.get("Time"))

    latest = sorted(entries, key=lambda x: x["_parsed_time"], reverse=True)[0]
    latest.pop("_parsed_time", None)

    # ✅ Fix bad structure before Pydantic validation
    transformed = {
    "name": latest.get("Name"),
    "role": latest.get("Role"),
    "purpose": latest.get("Purpose"),
    "instructions": _ensure_list(latest.get("Instructions")),
    "capabilities": _ensure_list(latest.get("Capabilities")),
    "welcome_message": latest.get("WelcomeMessage") or "",
    "knowledge_base": _ensure_list(latest.get("KnowledgeBase")),
    "sample_prompts": _ensure_list(latest.get("SamplePrompts")),
    "tone": latest.get("Tone", "neutral"),  # ✅ Required field
}

    return AgentConfig(**transformed)

def _ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]





GET_ALL_AGENTS_URL = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/GetAgentdetails"
EDIT_AGENT_URL = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/UpdateAgentDetails"

def edit_agent_config(existing_name, new_data):
    try:
        # ✅ Extract values from new_data dictionary
        new_name = new_data.get("name")
        new_role = new_data.get("role")
        new_purpose = new_data.get("purpose")

        if not existing_name:
            return {"error": "Missing 'ExistingAgentName'"}

        # 1. Get all agents
        get_response = requests.get(GET_ALL_AGENTS_URL)
        if get_response.status_code != 200:
            return {"error": f"Failed to fetch agents. Status code: {get_response.status_code}"}

        agents = get_response.json().get("Table", [])
        normalized_agents = [{k.lower(): v for k, v in agent.items()} for agent in agents]

        # 2. Find agent by existing name
        matching_index = next(
            (i for i, agent in enumerate(normalized_agents)
             if agent.get("name", "").lower() == existing_name.lower()),
            None
        )
        if matching_index is None:
            return {"error": f"Agent '{existing_name}' not found."}

        # 3. Get original agent details for reference
        original_agent = agents[matching_index]

        # 4. Build minimal payload for update API
        payload = {
            "ExistingAgentName": existing_name,
            "NewAgentName": new_name or original_agent.get("Name", ""),
            "ExistingRole": original_agent.get("Role", ""),
            "NewRole": new_role or original_agent.get("Role", ""),
            "ExistingPurpose": original_agent.get("Purpose", ""),
            "NewPurpose": new_purpose or original_agent.get("Purpose", ""),
            "Published": original_agent.get("Published", "False")  # Keep existing published state
        }

        # ✅ Log what we are sending
        print("\n📤 Final Payload to EDIT_AGENT_URL (minimal form):")
        print(json.dumps(payload, indent=2))

        # 5. Send POST request
        post_response = requests.post(EDIT_AGENT_URL, json=payload)

        # ✅ Log the response
        print("📥 Status Code:", post_response.status_code)
        print("📥 Response Text:", post_response.text)

        # 6. Handle success and parse response
        if post_response.status_code == 200 and post_response.text.strip().lower() != "internal server error":
            try:
                response_json = post_response.json()
                return {
                    "message": "✅ Agent updated successfully",
                    "updated_config": response_json
                }
            except Exception as e:
                return {
                    "message": "✅ Agent updated but response is not JSON",
                    "updated_config": {
                        "raw_response": post_response.text,
                        "parse_error": str(e)
                    }
                }
        else:
            return {
                "error": f"❌ Failed to update agent. Status code: {post_response.status_code}",
                "details": post_response.text
            }

    except Exception as e:
        return {"error": f"❌ Exception occurred: {str(e)}"}