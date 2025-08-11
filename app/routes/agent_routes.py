from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.utils.schema_reader import get_schema_and_sample_data, get_db_schema
from app.utils.llm_validator import validate_purpose_and_instructions
from app.utils.agent_builder import VALID_ROLES, generate_sample_prompts
from app.services.agent_servies import save_agent_config
from app.services.agent_servies import test_agent_response
from app.models.agent import AgentConfig
from app.utils.gpt_utils import serialize
from fastapi.encoders import jsonable_encoder
import traceback
from uuid import uuid4
import requests
from app.services.agent_servies import (
    edit_agent_config,
    publish_agent,
    test_agent_response,
    load_agent_config
)
from app.services.agent_servies import handle_agent_request
router = APIRouter()

# In-memory session tracking (temporary store for demo purposes)
user_threads = {}
user_collected_fields = {}

@router.post("/agent-message")
async def agent_message(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        message = data.get("message", "").strip()

        if not user_id or not message:
            return JSONResponse({"error": "Missing user_id or message"}, status_code=400)

        # Init user thread
        if user_id not in user_threads:
            user_threads[user_id] = []
            user_collected_fields[user_id] = {
                "name": None,
                "role": None,
                "purpose": None,
                "instructions": None,
            }

        thread = user_threads[user_id]
        collected = user_collected_fields[user_id]
        thread.append({"user": message})

        # Collect agent data step-by-step
        if not collected["name"]:
            collected["name"] = message
            return JSONResponse({"message": "What is the agent's role?"})

        elif not collected["role"]:
            collected["role"] = message

            if collected["role"] not in VALID_ROLES:
                user_threads[user_id] = []
                user_collected_fields[user_id] = {}
                return JSONResponse({
                    "error": f"Invalid role: '{collected['role']}'",
                    "allowed_roles": VALID_ROLES
                }, status_code=400)

            return JSONResponse({"message": "What is the purpose of this agent?"})

        elif not collected["purpose"]:
            collected["purpose"] = message
            return JSONResponse({"message": "What are the detailed instructions for the agent?"})

        elif not collected["instructions"]:
            collected["instructions"] = message
            return JSONResponse({"message": "List the agent's capabilities (comma-separated)."})

        elif not collected.get("capabilities"):
            collected["capabilities"] = [cap.strip() for cap in message.split(",")]
            return JSONResponse({"message": "What welcome message should the agent greet users with?"})

        elif not collected.get("welcome_message"):
            collected["welcome_message"] = message

            # ✅ Validate using LLM
            structured_schema, _, sample_data = get_schema_and_sample_data()
            validation = validate_purpose_and_instructions(
                collected["purpose"], collected["instructions"], structured_schema, sample_data
            )

            if not validation.get("purpose_valid", False):
                user_threads[user_id] = []
                user_collected_fields[user_id] = {}
                return JSONResponse({
                    "error": "Invalid purpose. Must relate to querying, analyzing, summarizing, or reporting on data."
                }, status_code=400)

            if validation.get("invalid_instructions"):
                user_threads[user_id] = []
                user_collected_fields[user_id] = {}
                return JSONResponse({
                    "error": "Invalid instructions.",
                    "invalid_instructions": validation["invalid_instructions"]
                }, status_code=400)

            # ✅ Final config
            agent_config = {
                "name": collected["name"],
                "role": collected["role"],
                "purpose": collected["purpose"],
                "instructions": [collected["instructions"]],
                "sample_prompts": generate_sample_prompts(collected["purpose"], collected["role"]),
                "tone": "friendly",
                "knowledge_base": [],
                "welcome_message": collected["welcome_message"],
                "capabilities": collected["capabilities"],
                "system_prompt": "You are a SQL assistant. Return only the query without explanation.",
                "frequency": "once",
                "time": "09:00",
                "schedule_enabled": True,
                "output_method": "chat",
                "published": False
            }

            agent_model = AgentConfig(**agent_config)
            save_agent_config(agent_model)

            # ✅ Sync to external API
            try:
                api_url = "https://supplysenseaiapi-aadngxggarc0g6hz.z01.azurefd.net/api/iSCM/SaveAgentDetails"
                payload = {
                    "Name": agent_model.name,
                    "Role": agent_model.role,
                    "Purpose": agent_model.purpose,
                    "Instructions": agent_model.instructions,
                    "Capabilities": agent_model.capabilities,
                    "WelcomeMessage": agent_model.welcome_message,
                    "Tone": agent_model.tone,
                    "KnowledgeBase": agent_model.knowledge_base,
                    "SamplePrompts": agent_model.sample_prompts,
                    "ScheduleEnabled": agent_model.schedule_enabled,
                    "Frequency": agent_model.frequency,
                    "Time": agent_model.time,
                    "OutputMethod": agent_model.output_method,
                    "Published": agent_model.published
                }

                api_response = requests.post(api_url, json=payload)

                try:
                    api_body = api_response.json()
                except ValueError:
                    api_body = api_response.text or "No response body"

                db_status = {
                    "code": api_response.status_code,
                    "body": api_body
                }

            except Exception as e:
                db_status = {
                    "code": "error",
                    "body": f"❌ API call failed: {str(e)}"
                }

            # ✅ Optionally test agent behavior
            result = await test_agent_response(agent_config, structured_schema, sample_data)

            # ✅ Reset after success
            user_threads[user_id] = []
            user_collected_fields[user_id] = {}

            print("API Status Code:", api_response.status_code)
            print("API Response:", api_response.text)

            return JSONResponse(content=jsonable_encoder({
                "message": "Agent created and validated successfully!",
                "agent_config": agent_config,
                "test_result": result,
                "sync_status": db_status
            }))

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/agent/edit")
async def edit_agent(request: Request):
    try:
        data = await request.json()
        print("Received data:", data)

        # Extract existing_name and new_data from incoming request
        existing_name = data.get("ExistingAgentName")
        new_data = {
            "name": data.get("NewAgentName"),
            "role": data.get("NewRole"),
            "purpose": data.get("NewPurpose")
        }

        if not existing_name or not all(new_data.values()):
            return JSONResponse(
                content={"error": "Missing required fields in the request"},
                status_code=400
            )

        # Now call your edit_agent_config with 2 arguments
        result = edit_agent_config(existing_name, new_data)

        if isinstance(result, dict) and result.get("error"):
            return JSONResponse(content=result, status_code=500)

        return JSONResponse(content={
            "message": "✅ Agent updated successfully via API",
            "updated_config": result
        }, status_code=200)

    except Exception as e:
        return JSONResponse(content={
            "message": "❌ Exception occurred while editing agent.",
            "details": str(e)
        }, status_code=500)


@router.post("/agent/publish")
async def publish_existing_agent(request: Request):
    try:
        data = await request.json()
        agent_name = data.get("name")  # Expecting {"name": "Loki"}

        if not agent_name:
            return JSONResponse({"error": "Missing 'name' in request body"}, status_code=400)

        result = publish_agent(agent_name)  # ✅ Pass only the name
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse(
            {"error": f"❌ Exception occurred while publishing agent: {str(e)}"},
            status_code=500
        )

@router.post("/agent/test")
async def test_existing_agent(request: Request):
    data = await request.json()
    name = data.get("name")
    question = data.get("question")
    created_by = data.get("created_by", "test_user@example.com")
    encrypted_filename = data.get("encrypted_filename", f"{name}_test_output")
    formatdata = data.get("formatdata", {})

    agent_config = load_agent_config(name)
    if not agent_config:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    # Load schema and sample data
    structured_schema, _, sample_data = get_schema_and_sample_data()

    # Use file generator only if ppt/excel/doc is mentioned in question
    question_lower = question.lower() if question else ""
    if any(word in question_lower for word in ["ppt", "presentation", "pptx", "excel", "xlsx", "word", "docx"]):
        # ✅ Merge all required params into a single data dictionary
        payload = {
            "agent_config": agent_config.dict(),
            "question": question,
            "structured_schema": structured_schema,
            "sample_data": sample_data,
            "encrypted_filename": encrypted_filename,
            "created_by": created_by,
            "formatdata": formatdata
        }

        result = await handle_agent_request(payload)
    else:
        # Only test for insights and recommendations
        result = await test_agent_response(agent_config.dict(), structured_schema, sample_data, question)

    return JSONResponse(result)

@router.get("/agent/play/{name}")
async def play_published_agent(name: str):
    agent_config = load_agent_config(name)
    if not agent_config:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    if not agent_config.published:
        return JSONResponse({"error": "Agent not published"}, status_code=400)

    return JSONResponse({
        "message": f"Agent '{name}' is ready to assist!",
        "welcome": agent_config.welcome_message,
        "sample_prompts": agent_config.sample_prompts,
    })
