# === ✅ Validate if the agent role is supported
VALID_ROLES = [
    "Supply Chain Planner",
    "Demand Planner",
    "Production Planner",
    "Supply Chain Analyst",
    "Sales & Operations Planning (S&OP) Manager",
    "Inventory Planner",
    "Capacity Planning Specialist",
    "Procurement Specialist / Buyer",
    "Strategic Sourcing Manager",
    "Category Manager",
    "Supplier Relationship Manager",
    "Contract & Compliance Manager",
    "Vendor Development Executive",
    "Global Sourcing Specialist",
    "Supply Chain Data Analyst",
    "ERP/SAP Supply Chain Consultant",
    "Forecasting Analyst",
    "AI/ML Supply Chain Modeler",
    "Digital Supply Chain Transformation Manager",
    "Inventory Optimization Specialist"
]

def validate_agent_role(role: str, purpose: str) -> bool:
    """Ensure the user-selected role is from the valid list."""
    return role in VALID_ROLES


# === ✅ Generate sample prompts based on purpose or role
def generate_sample_prompts(role: str, purpose: str) -> list[str]:
    purpose_lower = purpose.lower()

    if "forecast" in purpose_lower:
        return [
            "What is the expected forecat for next month?",
            "Give me a monthly forecast summary",
            "Create a presentation of next month’s forecast"
        ]
    elif "inventory" in purpose_lower:
        return [
            "List SKUs with excess inventory",
            "Show me inventory turnover vs demand",
            "Which items have slow-moving inventory?"
        ]
    elif "supplier" in purpose_lower or "vendor" in purpose_lower:
        return [
            "Which suppliers are most delayed?",
            "Show supplier performance scorecard",
            "List top 5 vendors by leadtime and PO"
        ]
    elif "procure" in purpose_lower or "sourcing" in purpose_lower:
        return [
            "Give me a report of high-value purchases last month",
            "List items with highest sourcing lead time",
            "Create a ppt of sourcing cost breakdown"
        ]
    elif "capacity" in purpose_lower:
        return [
            "Which plants are running at full capacity?",
            "What is my capacity utilization by week?",
            "Create a report of idle resources"
        ]
    else:
        return [
            f"What are my insights for {purpose_lower}?",
            f"Generate a ppt for {purpose_lower}",
            f"Summarize key metrics for {purpose_lower}"
        ]
