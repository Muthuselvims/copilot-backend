from fastapi import APIRouter, Request
from app.services.agent_servies import (
    create_conversational_agent,
    handle_agent_request,
    test_agent_response,
    publish_agent,
    schedule_agent,
)
from app.models.agent import AgentConfig

router = APIRouter()

# ✅ STEP 1: Conversational Agent Creation (Validates + Builds Sample Prompts + Saves to File + Sends to DB)
@router.post("/create-agent-chat")
async def create_agent_chat(request: Request):
    data = await request.json()

    # Call service to validate + build config + send to SaveAgentDetails API
    result = await create_conversational_agent(data)
    return result


# ✅ STEP 2: Run the Agent – Check if user wants PPT or just chat insights
@router.post("/run-agent")
async def run_agent(request: Request):
    data = await request.json()
    return await handle_agent_request(data)


# ✅ STEP 2 (alias): Legacy support for /agent-request
@router.post("/agent-request")
async def agent_request(request: Request):
    data = await request.json()
    return await handle_agent_request(data)


# ✅ STEP 3: Test Agent Response (no final PPT/Word/Excel)
@router.post("/test-agent")
async def test_agent(request: Request):
    data = await request.json()
    return await test_agent_response(data)


# ✅ STEP 4: Publish Agent (mark as published)
@router.post("/publish-agent")
async def publish_agent_route(request: Request):
    data = await request.json()
    return publish_agent(data)


# ✅ STEP 5: Schedule Agent (future cron integration)
@router.post("/schedule-agent")
async def schedule_agent_route(request: Request):
    data = await request.json()
    return schedule_agent(data)
