from openai import OpenAI
from app.utils.llm_validator import validate_purpose_and_instructions

from app.utils.agent_builder import VALID_ROLES, generate_sample_prompts

client = OpenAI()

async def guide_agent_creation_conversation():
    conversation = []

    # Ask for agent name
    agent_name = await ask_user("What would you like to name your agent?", conversation)

    # Ask for role
    while True:
        role = await ask_user("What is the role of your f"'{agent_name}'"? (e.g., Inventory Planner, Forecasting Analyst)", conversation)
        if role not in VALID_ROLES:
            conversation.append({"role": "assistant", "content": f"'{role}' is not a valid role. Please choose from: {', '.join(VALID_ROLES)}"})
        else:
            break

    # Ask for purpose
    purpose = await ask_user("What is the f"'{agent_name}'" main purpose or task? (e.g., Analyze inventory, Forecast demand)", conversation)

    # Ask for instructions
    while True:
        instructions = await ask_user("What instructions should  f"'{agent_name}'" follow?", conversation)
        result = validate_purpose_and_instructions(role, purpose, [instructions])
        if result["purpose_valid"] and not result["invalid_instructions"]:
            break
        else:
            err = []
            if not result["purpose_valid"]:
                err.append("❌ Purpose is invalid.")
            if result["invalid_instructions"]:
                err.append(f"❌ Invalid instructions: {result['invalid_instructions']}")
            conversation.append({"role": "assistant", "content": " ".join(err) + " Please try again."})

    # Suggest prompts
    prompts = generate_sample_prompts(role, purpose)

    # Return the final agent config
    return {
        "name": agent_name,
        "role": role,
        "purpose": purpose,
        "instructions": [instructions],
        "sample_prompts": prompts
    }

async def ask_user(prompt, conversation_history):
    conversation_history.append({"role": "assistant", "content": prompt})
    response = input(f"{prompt}\n> ")  # Replace with frontend input capture if needed
    conversation_history.append({"role": "user", "content": response})
    return response


VALID_CAPABILITIES = {
    "Summarize results",
    "Generate output as PPT",
    "Generate Excel output",
    "Send email reports",
    "Highlight exceptions",
    "Forecast metrics",
    "Recommend actions",
    "Explain trends"
}

def validate_capabilities(capabilities: list[str]) -> list[str]:
    """
    Returns list of invalid capabilities (if any).
    """
    if not isinstance(capabilities, list):
        return ["Capabilities must be a list."]
    
    invalid = [c for c in capabilities if c not in VALID_CAPABILITIES]
    return invalid
