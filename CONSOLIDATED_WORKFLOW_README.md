# Consolidated Workflow Implementation

## Overview

This implementation addresses the issue where multiple tasks requiring the same agent type resulted in multiple separate API calls. Instead of calling "Turnover Agent" multiple times for related tasks, the system now consolidates these tasks into a single comprehensive call.

## Problem Solved

**Before**: 
```
Task 1: "Calculate turnover rates" → Turnover Agent (Call 1)
Task 2: "Identify fast-selling materials" → Turnover Agent (Call 2) 
Task 3: "Identify slow-selling materials" → Turnover Agent (Call 3)
```

**After**:
```
All 3 tasks → Consolidated Turnover Agent (Single Call)
```

## Key Changes

### 1. Enhanced AgentManager (`app/agents/autogen_manager.py`)

#### New Methods Added:

- **`_group_steps_by_agent()`**: Groups workflow steps by the agent that would handle them
- **`_consolidate_tasks()`**: Combines multiple tasks for the same agent into a comprehensive request
- **Enhanced `run_workflow()`**: Now processes tasks in groups rather than individually

#### Workflow Logic:

1. **Grouping Phase**: All steps are grouped by their assigned agent
2. **Consolidation Phase**: Steps for the same agent are combined into comprehensive tasks
3. **Execution Phase**: Each agent group is executed once with the consolidated task
4. **Result Distribution**: Results are distributed back to individual step contexts

### 2. Consolidated Agent Configuration

Created `agents/consolidated_turnover_agent.json` with:
- **Comprehensive purpose**: Handles multiple related turnover analysis tasks
- **Enhanced capabilities**: Covers calculation, identification, and reporting
- **Professional tone**: Suitable for business analysis

## Benefits

### Performance
- ✅ **Reduced API calls**: Multiple calls to same agent → Single call
- ✅ **Lower latency**: Fewer round trips to external services
- ✅ **Cost efficiency**: Reduced token usage and API costs

### User Experience
- ✅ **Comprehensive responses**: Single agent provides complete analysis
- ✅ **Better context**: Agent sees full scope of related tasks
- ✅ **Consistent output**: Unified analysis format

### Maintainability
- ✅ **Cleaner logs**: Fewer agent execution entries
- ✅ **Simplified debugging**: Single point of failure per agent type
- ✅ **Easier monitoring**: Clear agent utilization patterns

## Usage Example

### Original Workflow (Multiple Calls)
```json
{
  "plan": [
    {"task": "Check inventory levels", "output_key": "inventory_levels"},
    {"task": "Calculate turnover rates from {inventory_levels}", "output_key": "turnover_rates"},
    {"task": "Identify fast-selling from {turnover_rates}", "output_key": "fast_selling"},
    {"task": "Identify slow-selling from {turnover_rates}", "output_key": "slow_selling"}
  ]
}
```

**Result**: 4 separate agent calls (assuming all go to Turnover Agent)

### Consolidated Workflow (Single Call)
```json
{
  "plan": [
    {"task": "Check inventory levels", "output_key": "inventory_levels"},
    {"task": "Calculate turnover rates from {inventory_levels}", "output_key": "turnover_rates"},
    {"task": "Identify fast-selling from {turnover_rates}", "output_key": "fast_selling"},
    {"task": "Identify slow-selling from {turnover_rates}", "output_key": "slow_selling"}
  ]
}
```

**Result**: 1 consolidated call to Turnover Agent with comprehensive task

## Implementation Details

### Task Consolidation Logic

```python
def _consolidate_tasks(self, steps: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
    """Consolidate multiple tasks for the same agent into a single comprehensive task"""
    
    # Extract and format all tasks with context
    formatted_tasks = []
    for step in steps:
        task = step.get("task", "").strip()
        formatted_task = task.format(**context) if context else task
        formatted_tasks.append(formatted_task)
    
    # Create comprehensive request
    consolidated = "Please perform the following analysis tasks comprehensively:\n\n"
    for i, task in enumerate(formatted_tasks, 1):
        consolidated += f"{i}. {task}\n"
    
    consolidated += "\nPlease provide a complete analysis covering all the above tasks in a single comprehensive response."
    
    return consolidated
```

### Agent Grouping Logic

```python
def _group_steps_by_agent(self, plan: List[Dict[str, Any]], agents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group steps by the agent that would handle them"""
    
    grouped = {}
    for step in plan:
        task = step.get("task", "").strip()
        agent = self.route(task, agents)  # Use existing routing logic
        agent_name = agent.get("name")
        
        if agent_name not in grouped:
            grouped[agent_name] = []
        grouped[agent_name].append(step)
    
    return grouped
```

## Testing

Run the test script to see the consolidation in action:

```bash
python test_consolidated_workflow.py
```

This will demonstrate:
- Original plan structure
- Available agents
- Grouped steps by agent
- Consolidated task examples
- Benefits summary

## Configuration

To use consolidated agents:

1. **Create agent configs** with comprehensive purposes and capabilities
2. **Ensure published=true** for the consolidated agents
3. **Use descriptive names** that indicate their consolidated nature
4. **Include all related capabilities** in the capabilities array

## Migration Guide

### For Existing Workflows

No changes required! The system automatically:
- Detects when multiple steps use the same agent
- Consolidates them into comprehensive tasks
- Maintains backward compatibility

### For New Workflows

Consider creating consolidated agents for:
- Related analysis tasks (turnover, forecasting, optimization)
- Multi-step reporting workflows
- Comprehensive data analysis scenarios

## Future Enhancements

1. **Smart Consolidation**: AI-driven task grouping based on semantic similarity
2. **Parallel Execution**: Run different agent groups in parallel
3. **Result Merging**: Intelligent merging of results from different agent types
4. **Performance Metrics**: Track consolidation effectiveness and performance gains

## Troubleshooting

### Common Issues

1. **Context Formatting Errors**: Ensure task templates use proper `{key}` syntax
2. **Agent Routing Failures**: Verify agent configurations and purposes
3. **Result Distribution**: Check that output_key values are properly set

### Debug Mode

Enable detailed logging to see:
- Task grouping decisions
- Consolidation process
- Agent execution details
- Context updates

```python
import logging
logging.getLogger("app.agents.autogen_manager").setLevel(logging.DEBUG)
```
