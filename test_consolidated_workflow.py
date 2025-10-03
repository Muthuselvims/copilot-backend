#!/usr/bin/env python3
"""
Test script to demonstrate the consolidated workflow approach
"""

import json
from app.agents.autogen_manager import AgentManager

def test_consolidated_workflow():
    """Test the consolidated workflow with the inventory turnover example"""
    
    # Initialize the agent manager
    manager = AgentManager()
    
    # Test the new consolidated planning approach
    task = "Check inventory and turnover rate. Find which Materials are selling fast and which are slow"
    
    print("=== NEW: Consolidated Planning Approach ===")
    print(f"Input Task: {task}")
    
    # Generate plan (should now create consolidated plan)
    plan = manager.plan_from_task(task)
    print(f"\nGenerated Plan: {json.dumps(plan, indent=2)}")
    
    # Check if consolidation is applied
    consolidated_plan = manager._consolidate_plan_if_needed(plan)
    print(f"\nAfter Consolidation: {json.dumps(consolidated_plan, indent=2)}")
    
    print("\n=== OLD: Multiple Step Approach (for comparison) ===")
    # Example plan that would previously call multiple Turnover Agents
    old_plan = [
        {
            "task": "Check the current inventory levels of all materials.",
            "output_key": "inventory_levels"
        },
        {
            "task": "Calculate the turnover rate for each material based on {inventory_levels}.",
            "output_key": "turnover_rates"
        },
        {
            "task": "Identify fast-selling materials from {turnover_rates}.",
            "output_key": "fast_selling_materials"
        },
        {
            "task": "Identify slow-selling materials from {turnover_rates}.",
            "output_key": "slow_selling_materials"
        }
    ]
    
    print("Old Plan (Multiple Steps):")
    for i, step in enumerate(old_plan, 1):
        print(f"{i}. {step['task']} -> {step['output_key']}")
    
    # Discover available agents
    agents = manager.discover_all_agents()
    print(f"\n=== Available Agents ({len(agents)}) ===")
    for agent in agents:
        print(f"- {agent['name']}: {agent.get('purpose', 'No purpose defined')}")
    
    # Group steps by agent
    grouped_steps = manager._group_steps_by_agent(plan, agents)
    print(f"\n=== Grouped Steps by Agent ===")
    for agent_name, steps in grouped_steps.items():
        print(f"\n{agent_name}: {len(steps)} tasks")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step['task']}")
    
    # Demonstrate task consolidation
    print(f"\n=== Task Consolidation Example ===")
    for agent_name, steps in grouped_steps.items():
        if len(steps) > 1:
            consolidated = manager._consolidate_tasks(steps, {})
            print(f"\nConsolidated task for {agent_name}:")
            print(f"'{consolidated}'")
    
    print(f"\n=== Benefits ===")
    print("✓ Reduces multiple API calls to the same agent")
    print("✓ Provides comprehensive analysis in single response")
    print("✓ Maintains context across related tasks")
    print("✓ Improves efficiency and reduces costs")
    print("✓ Better user experience with consolidated results")

if __name__ == "__main__":
    test_consolidated_workflow()
