# Consolidated Planning Implementation - Update

## Overview

This update implements **intelligent plan consolidation** that automatically detects when multiple tasks would be handled by the same agent type and consolidates them into a single comprehensive task upfront, rather than during execution.

## Problem Solved

**Before**: Even with consolidated workflow execution, the planning phase would still create multiple steps:
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

**After**: The planning phase now creates a single consolidated task:
```json
{
  "plan": [
    {
      "task": "Perform comprehensive inventory turnover analysis including checking current inventory levels, calculating turnover rates for all materials, and identifying both fast-selling and slow-selling materials with detailed insights and recommendations.",
      "output_key": "turnover_analysis"
    }
  ]
}
```

## Key Changes

### 1. Enhanced Planning Prompt

**Updated `plan_from_task()` method** with intelligent consolidation guidance:

```python
prompt = (
    "You are an intelligent assistant that creates a JSON plan to solve a user's task. "
    "Break the main task into 2-4 sequential steps, BUT if all steps would likely be handled by the same type of agent, create a single comprehensive task instead.\n\n"
    # ... enhanced rules and examples ...
)
```

**Key Features**:
- ✅ **Consolidation Guidance**: Explicitly instructs LLM to consolidate when appropriate
- ✅ **Smart Examples**: Shows both multi-agent and consolidated examples
- ✅ **Same-Agent Detection**: Encourages consolidation for same agent types

### 2. Post-Processing Consolidation

**New `_consolidate_plan_if_needed()` method**:

```python
def _consolidate_plan_if_needed(self, plan: List[Dict[str, Any]], candidate_agents: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Check if all steps would go to the same agent and consolidate if needed"""
    
    # Check which agent each step would go to
    agent_assignments = []
    for step in plan:
        task = step.get("task", "").strip()
        agent = self.route(task, agents)
        agent_name = agent.get("name") if agent else "unknown"
        agent_assignments.append(agent_name)
    
    # If all steps go to the same agent, consolidate them
    if len(set(agent_assignments)) == 1 and len(agent_assignments) > 1:
        # Create consolidated task
        consolidated_task = "Please perform the following analysis tasks comprehensively:\n\n"
        for i, step in enumerate(plan, 1):
            consolidated_task += f"{i}. {step['task']}\n"
        consolidated_task += "\nPlease provide a complete analysis covering all the above tasks in a single comprehensive response."
        
        return [{"task": consolidated_task, "output_key": "consolidated_analysis"}]
    
    return plan
```

### 3. Integrated Workflow

**Updated `plan_and_run()` method**:

```python
def plan_and_run(self, task: str, candidate_agents: Optional[List[str]] = None) -> Dict[str, Any]:
    plan = self.plan_from_task(task)
    logger.info("Plan from GPT", extra={"plan": plan})
    
    # Post-process plan to consolidate steps that would go to the same agent
    plan = self._consolidate_plan_if_needed(plan, candidate_agents)
    logger.info("Final plan after consolidation", extra={"plan": plan})
    
    result = self.run_workflow(plan, candidate_agents)
    return {"plan": plan, "steps": result.get("steps", [])}
```

## How It Works

### Step 1: Intelligent Planning
The LLM analyzes the user's task and decides whether to:
- Create multiple steps (for different agent types)
- Create a single consolidated step (for same agent type)

### Step 2: Agent Assignment Check
The system checks which agent each planned step would be assigned to using the existing routing logic.

### Step 3: Automatic Consolidation
If all steps would go to the same agent, they are automatically consolidated into a single comprehensive task.

### Step 4: Execution
The consolidated task is executed once, providing comprehensive results.

## Examples

### Example 1: Turnover Analysis (Consolidated)
**Input**: `"Check inventory and turnover rate. Find which Materials are selling fast and which are slow"`

**Generated Plan**:
```json
[
  {
    "task": "Perform comprehensive inventory turnover analysis including checking current inventory levels, calculating turnover rates for all materials, and identifying both fast-selling and slow-selling materials with detailed insights and recommendations.",
    "output_key": "turnover_analysis"
  }
]
```

**Result**: Single call to Turnover Agent with comprehensive analysis

### Example 2: Multi-Agent Task (Separate)
**Input**: `"Find the top-selling product and then get its supplier information"`

**Generated Plan**:
```json
[
  {
    "task": "Identify the top-selling product.",
    "output_key": "top_product"
  },
  {
    "task": "Find the supplier for {top_product}.",
    "output_key": "supplier_info"
  }
]
```

**Result**: Multiple calls to different agents (Sales Agent → Supplier Agent)

## Benefits

### Performance Improvements
- ✅ **Fewer API Calls**: Single consolidated call instead of multiple calls
- ✅ **Reduced Latency**: Faster response times
- ✅ **Lower Costs**: Reduced token usage and API costs

### User Experience
- ✅ **Comprehensive Responses**: Complete analysis in single response
- ✅ **Better Context**: Agent sees full scope of related tasks
- ✅ **Consistent Output**: Unified analysis format

### System Efficiency
- ✅ **Smart Planning**: Intelligent upfront consolidation
- ✅ **Reduced Complexity**: Simpler execution paths
- ✅ **Better Resource Utilization**: Optimal agent usage

## Testing

### Test Scripts Available

1. **`test_consolidated_planning.py`** - Tests the new planning logic
2. **`test_consolidated_workflow.py`** - Tests both planning and execution

### Running Tests

```bash
# Test the new consolidated planning
python test_consolidated_planning.py

# Test the complete workflow
python test_consolidated_workflow.py
```

## Configuration

### Agent Setup for Consolidation

To maximize consolidation benefits, ensure your agents have:

1. **Comprehensive Purposes**: Cover multiple related tasks
2. **Broad Capabilities**: Handle complex, multi-step analysis
3. **Published Status**: Set `published: true` for active agents

### Example Consolidated Agent

```json
{
  "name": "Consolidated Turnover Agent",
  "role": "Inventory Turnover Analyst",
  "purpose": "Comprehensive analysis of inventory turnover rates, identifying fast and slow selling materials with complete insights and recommendations",
  "instructions": [
    "Analyze inventory turnover rates comprehensively",
    "Calculate turnover rates for all materials based on inventory levels and consumption data",
    "Identify and categorize fast-selling materials (high turnover rates)",
    "Identify and categorize slow-selling materials (low turnover rates)",
    "Provide detailed business insights and actionable recommendations"
  ],
  "capabilities": [
    "Inventory turnover calculation",
    "Material performance analysis",
    "Fast and slow selling identification",
    "Business insights generation",
    "Comprehensive reporting"
  ],
  "published": true
}
```

## Migration Notes

### Backward Compatibility
- ✅ **Existing Workflows**: Continue to work unchanged
- ✅ **API Compatibility**: No breaking changes to existing endpoints
- ✅ **Agent Configurations**: Existing agents work without modification

### Gradual Adoption
- ✅ **Automatic Detection**: System automatically detects consolidation opportunities
- ✅ **No Configuration Required**: Works out of the box
- ✅ **Fallback Support**: Falls back to multi-step approach when needed

## Future Enhancements

1. **Semantic Consolidation**: AI-driven detection of semantically similar tasks
2. **Performance Metrics**: Track consolidation effectiveness
3. **Dynamic Thresholds**: Configurable consolidation criteria
4. **Advanced Routing**: Context-aware agent selection for better consolidation

## Troubleshooting

### Common Issues

1. **Over-Consolidation**: If tasks are being consolidated when they shouldn't be
   - **Solution**: Review agent purposes and routing logic

2. **Under-Consolidation**: If similar tasks aren't being consolidated
   - **Solution**: Ensure agent purposes are comprehensive enough

3. **Routing Failures**: If agent assignment fails during consolidation check
   - **Solution**: Verify agent configurations and routing logic

### Debug Mode

Enable detailed logging to see consolidation decisions:

```python
import logging
logging.getLogger("app.agents.autogen_manager").setLevel(logging.DEBUG)
```

This will show:
- Initial plan generation
- Agent assignment decisions
- Consolidation logic
- Final plan structure
