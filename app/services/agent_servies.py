# agent_services.py

import os
import json
import numpy as np
import requests
from datetime import datetime
from collections import defaultdict

from app.db.sql_connection import execute_sql_query
from app.utils.ppt_generator import generate_ppt, generate_excel, generate_word, generate_insights, generate_direct_response
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
# ✅ Ensure any value is returned as a list
def _ensure_list(data):
    """
    Ensures the input is a list of clean, stripped strings.
    """
    if isinstance(data, list):
        # If it's a list with one item that's a comma-separated string, split it.
        if len(data) == 1 and isinstance(data[0], str) and ',' in data[0]:
            return [item.strip() for item in data[0].split(',')]
        # Otherwise, assume it's a clean list and strip each item.
        return [item.strip() for item in data if isinstance(item, str)]
    elif isinstance(data, str):
        # If it's a string, split by comma.
        return [item.strip() for item in data.split(',')]
    return [] # Return an empty list for invalid input.

def is_question_supported_by_capabilities(question: str, capabilities: list) -> bool:
    capability_keywords = {
        "ppt": "Generate output as PPT",
        "pptx": "Generate output as PPT",
        "presentation": "Generate output as PPT",
        "excel": "Generate output as Excel",
        "xlsx": "Generate output as Excel",
        "word": "Generate output as Word",
        "doc": "Generate output as Word",
        "docx": "Generate output as Word",
        "chart": "Charts and graphs",
        "graph": "Charts and graphs",
        "visual": "Data visualization",
        "recommend": "Provide data-driven recommendations",
        "summarize": "Summarize results",
        "insight": "Create data-driven insights",
        "anomaly": "Highlight anomalies",
        "validate": "Data validation",
        "automate": "Automate repetitive tasks",
        "assist": "Assist with data analysis",
        "support": "Support decision-making",
        "visualize": "Data visualization",
        "data-driven": "Provide data-driven recommendations",

        "data analysis": "Assist with data analysis",
        "data insights": "Create data-driven insights"
    }

    for keyword, required_capability in capability_keywords.items():
        if keyword in question.lower():
            if required_capability not in capabilities:
                return False
    return True

    


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

    # ✅ Capability enforcement
    if not is_question_supported_by_capabilities(question, agent_config.capabilities):
     return {
        "error": f"❌ This question requires capabilities not available in agent '{agent_name}'.",
        "allowed_capabilities": agent_config.capabilities
    }

    
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

        # ✅ Detect if visualization is requested
    visual_keywords = ["chart", "graph", "visual", "visualize"]
    include_charts = any(k in question.lower() for k in visual_keywords)

    output_path = None

    if output_format == "ppt":
        output_path = generate_ppt(question, result_cleaned,  include_charts=include_charts)
    elif output_format == "excel":
        output_path = generate_excel(result_cleaned, question,  include_charts=include_charts)
    elif output_format == "word":
        output_path = generate_word(result_cleaned, question,  include_charts=include_charts)
    
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

    # ✅ Generate a single, comprehensive response
    agent_response_content = generate_direct_response(question, df_clean)

    tone_prefix = f"Hello! I'm {agent_name}, your {agent_config.role}.\nUsing a {agent_config.tone} tone:"
    final_response = f"{tone_prefix}\n\n{agent_response_content}"
    insights, recs = generate_insights(df_clean)

    tone_prefix = f"Hello! I'm {agent_name}, your {agent_config.role}.\nUsing a {agent_config.tone} tone:"

    return {
       # "sql_query": sql_query,
        "top_rows": df_clean.head(10).to_dict(orient="records"),
        "insights": insights,
        "recommendations": recs,
        "agent_response": final_response
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
            "ExistingInstruction": original_agent.get("Instructions", ""),
            "Instruction": original_agent.get("Instructions", ""),
            "Existingcapabilities": original_agent.get("Capabilities", ""),
            "Capabilities": original_agent.get("Capabilities", ""),
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

    # Normalize published to boolean
    published_raw = latest.get("Published", False)
    published = str(published_raw).lower() == "true"

    # Fix bad structure before Pydantic validation
    transformed = {
        "name": latest.get("Name"),
        "role": latest.get("Role"),
        "purpose": latest.get("Purpose"),
        "instructions": _ensure_list(latest.get("Instructions")),
        "capabilities": _ensure_list(latest.get("Capabilities")),
        "welcome_message": latest.get("WelcomeMessage") or "",
        "knowledge_base": _ensure_list(latest.get("KnowledgeBase")),
        "sample_prompts": _ensure_list(latest.get("SamplePrompts")),
        "tone": latest.get("Tone", "neutral"),  # Required field
        "published": published  # <-- Added here
    }

    return AgentConfig(**transformed)





GET_ALL_AGENTS_URL = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/GetAgentdetails"
EDIT_AGENT_URL = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/UpdateAgentDetails"
# Ensure we correctly convert list to comma-separated string
def list_to_str(value):
    if isinstance(value, list):
        return ", ".join(value)
    return value or ""

def edit_agent_config(existing_name, new_data):
    try:
        new_name = new_data.get("name")
        new_role = new_data.get("role")
        new_purpose = new_data.get("purpose")
        new_instruction = new_data.get("instruction")
        new_capabilities = new_data.get("capabilities")

        if not existing_name:
            return {"error": "Missing 'ExistingAgentName'"}

        # Step 1: Fetch agents
        get_response = requests.get(GET_ALL_AGENTS_URL)
        if get_response.status_code != 200:
            return {"error": f"Failed to fetch agents. Status code: {get_response.status_code}"}

        agents = get_response.json().get("Table", [])
        normalized_agents = [{k.lower(): v for k, v in agent.items()} for agent in agents]

        # Step 2: Find the existing agent
        matching_index = next(
            (i for i, agent in enumerate(normalized_agents)
             if agent.get("name", "").lower() == existing_name.lower()),
            None
        )
        if matching_index is None:
            return {"error": f"Agent '{existing_name}' not found."}

        original_agent = agents[matching_index]

        # Step 3: Normalize old instruction/capabilities
        existing_instruction = _ensure_list(original_agent.get("Instructions", ""))
        existing_capabilities = _ensure_list(original_agent.get("Capabilities", ""))

        
        # Step 4: Normalize new instruction/capabilities
        #new_instruction = _ensure_list(new_instruction)
        #new_capabilities = _ensure_list(new_capabilities)
        new_instruction_list = _ensure_list(new_data.get("Instruction"))
        new_capabilities_list = _ensure_list(new_data.get("Capabilities"))

        # Step 5: Build Payload
        payload = {
    "ExistingAgentName": existing_name,
    "NewAgentName": new_name or original_agent.get("Name", ""),
    "ExistingRole": original_agent.get("Role", ""),
    "NewRole": new_role or original_agent.get("Role", ""),
    "ExistingPurpose": original_agent.get("Purpose", ""),
    "NewPurpose": new_purpose or original_agent.get("Purpose", ""),
    "Published": original_agent.get("Published", "False"),
    "ExistingInstruction": list_to_str(new_data.get("ExistingInstruction") or original_agent.get("Instructions")),
            "Instruction": list_to_str(new_data.get("Instruction") or original_agent.get("Instructions")),
            "Existingcapabilities": list_to_str(new_data.get("Existingcapabilities") or original_agent.get("Capabilities")),
            "Capabilities": list_to_str(new_data.get("Capabilities") or original_agent.get("Capabilities"))
}


        print("\n📤 Final Payload to EDIT_AGENT_URL (minimal form):")
        print(json.dumps(payload, indent=2))
        

        post_response = requests.post(EDIT_AGENT_URL, json=payload)

        print("📥 Status Code:", post_response.status_code)
        print("📥 Response Text:", post_response.text)

        if post_response.status_code == 200 and post_response.text.strip().lower() != "internal server error":
            try:
                return {
                    "message": "✅ Agent updated successfully",
                    "updated_config": post_response.json()
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
