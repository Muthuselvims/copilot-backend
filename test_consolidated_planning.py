#!/usr/bin/env python3
"""
Test script to demonstrate the consolidated planning approach
"""

import json
from app.agents.autogen_manager import AgentManager

def test_consolidated_planning():
    """Test the consolidated planning with the inventory turnover example"""
    
    # Initialize the agent manager
    manager = AgentManager()
    
    # Test case 1: Task that should be consolidated (all turnover analysis)
    task1 = "Check inventory and turnover rate. Find which Materials are selling fast and which are slow"
    
    print("=== Test Case 1: Turnover Analysis Task ===")
    print(f"Input Task: {task1}")
    
    # Generate plan
    plan1 = manager.plan_from_task(task1)
    print(f"\nInitial Plan: {json.dumps(plan1, indent=2)}")
    
    # Check consolidation
    consolidated_plan1 = manager._consolidate_plan_if_needed(plan1)
    print(f"\nConsolidated Plan: {json.dumps(consolidated_plan1, indent=2)}")
    
    # Test case 2: Task that should remain separate (different agent types)
    task2 = "Find the top-selling product and then get its supplier information"
    
    print("\n=== Test Case 2: Multi-Agent Task ===")
    print(f"Input Task: {task2}")
    
    plan2 = manager.plan_from_task(task2)
    print(f"\nInitial Plan: {json.dumps(plan2, indent=2)}")
    
    consolidated_plan2 = manager._consolidate_plan_if_needed(plan2)
    print(f"\nConsolidated Plan: {json.dumps(consolidated_plan2, indent=2)}")
    
    print("\n=== Benefits of Consolidated Planning ===")
    print("✅ Reduces API calls when all steps use the same agent")
    print("✅ Provides comprehensive analysis in single response")
    print("✅ Better user experience with consolidated results")
    print("✅ Maintains multi-agent workflow when different agents are needed")

def test_with_available_agents():
    """Test with actual available agents"""
    manager = AgentManager()
    
    print("\n=== Available Agents ===")
    agents = manager.discover_all_agents()
    for agent in agents:
        print(f"- {agent['name']}: {agent.get('purpose', 'No purpose defined')}")
    
    # Test the specific turnover task
    task = "Check inventory and turnover rate. Find which Materials are selling fast and which are slow"
    print(f"\n=== Testing Task: {task} ===")
    
    # This will show the full planning process
    try:
        result = manager.plan_and_run(task)
        print(f"Final Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        print("This is expected if database connection is not configured.")

if __name__ == "__main__":
    test_consolidated_planning()
    test_with_available_agents()
