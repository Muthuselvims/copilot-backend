import logging
import os
import time
import requests
import json as _json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.services.agent_servies import load_agent_config, GET_ALL_AGENTS_URL
from app.agents.autogen_orchestrator import run_autogen_orchestration

logger = logging.getLogger("app.agents.autogen_manager")
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class AgentManager:
    SIMPLE_TASK_KEYWORDS = ["simple", "quick", "basic", "single", "only"]

    _agents_cache: Optional[List[Dict[str, Any]]] = None
    _agents_cache_time: Optional[float] = None
    _agents_cache_ttl: int = 300

    def _is_simple_task(self, task: str) -> bool:
        return any(keyword in task.lower() for keyword in self.SIMPLE_TASK_KEYWORDS)

    def _format_task_with_context(self, task: str, context: Dict[str, Any]) -> str:
        if not context:
            return task
        context_str = "\n\nContext from previous agents:\n"
        for key, value in context.items():
            context_str += f"{key}: {str(value)[:200]}...\n"
        return f"{task}{context_str}"

    def discover_all_agents(self) -> List[Dict[str, Any]]:
        now = time.time()
        if (
            self._agents_cache is not None
            and self._agents_cache_time is not None
            and (now - self._agents_cache_time) < self._agents_cache_ttl
        ):
            logger.info("Returning cached agent list")
            return self._agents_cache

        try:
            logger.info(f"Attempting to fetch all agents from API: {GET_ALL_AGENTS_URL}")
            resp = requests.get(GET_ALL_AGENTS_URL, timeout=20)
            resp.raise_for_status() # CHANGED: Raise an exception for bad status codes

            table = resp.json().get("Table", [])
            if not table:
                logger.warning("API returned no agent records in the 'Table' field.")
                return []
            
            logger.info(f"API returned {len(table)} raw agent records")
            names = sorted(list({row.get("Name") for row in table if row.get("Name")}))
            logger.info(f"Found {len(names)} unique agent names: {names}")

            configs = []
            for name in names:
                cfg = load_agent_config(name)
                if cfg:
                    configs.append(cfg.dict())
                else:
                    logger.warning(f"Failed to load config for agent: {name}")

            # NEW: Added more informative logging
            logger.info(f"Successfully loaded {len(configs)} agent configs out of {len(names)} unique names.")
            self._agents_cache = configs
            self._agents_cache_time = now

            return configs

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching agent list from API: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error("Error discovering all agents", exc_info=True, extra={"error": str(e)})
            return []

    def discover_agents(self, names: List[str]) -> List[Dict[str, Any]]:
        all_agents = self.discover_all_agents()
        logger.info("Filtering agents", extra={"input_names": names, "available_names": [a.get("name") for a in all_agents]})

        if not names:
            return all_agents

        return [
            a for a in all_agents
            if a.get("name", "").strip().lower() in [n.strip().lower() for n in names]
        ]

    def route(self, task: str, agents: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not agents:
            logger.warning("Routing failed: No agents provided to the router.")
            return {}

        try:
            agent_descriptions = "\n".join([
                f"- Agent Name: {a['name']}\n  Purpose: {a.get('purpose', 'No purpose defined.')}" for a in agents
            ])
            # CHANGED: Improved prompt for more reliable routing
            prompt = (
                f"You are an intelligent routing assistant. Your job is to select the best agent for a specific task based on the agent's stated purpose.\n\n"
                f"Here are the available agents:\n{agent_descriptions}\n\n"
                f"Review the following task and choose the  most appropriate agent or agents and work sequentially based on the task.\n"
                f"Task: \"{task}\"\n\n"
                f"Respond with ONLY the name of the chosen agent from the list. Do not add any explanation or other text."
            )

            resp = _client.chat.completions.create(
                model=os.getenv("AUTOGEN_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            chosen_name = (resp.choices[0].message.content or "").strip().replace("\"", "")
            logger.info("LLM selected agent", extra={"chosen": chosen_name, "task": task})

            for agent in agents:
                if agent.get("name", "").strip().lower() == chosen_name.lower():
                    logger.info("LLM-based routing successful", extra={"agent": chosen_name})
                    return agent

            logger.warning("LLM-selected agent not found in list, falling back to default.", extra={"chosen": chosen_name})

        except Exception as e:
            logger.error("LLM-based routing failed", exc_info=True, extra={"error": str(e)})

        logger.warning("Routing fallback: defaulting to first available agent")
        return agents[0]

    def _run_single(self, task: str, agent_name: Optional[str]) -> Dict[str, Any]:
        logger.info("manager: executing", extra={"agent": agent_name, "task": task})
        try:
            return run_autogen_orchestration(task, agent_name=agent_name)
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}", extra={"agent": agent_name, "task": task})
            return {
                "error": f"Agent execution failed: {str(e)}",
                "agent": agent_name,
                "task": task,
                "answer": f"Sorry, I encountered an error while processing your request: {str(e)}. Please check your database connection and try again."
            }

    def _maybe_evaluate(self, result: Dict[str, Any], criteria: Optional[str]) -> bool:
        if not criteria:
            return True
        return True

    def _group_steps_by_agent(self, plan: List[Dict[str, Any]], agents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group steps by the agent that would handle them"""
        grouped = {}
        
        for step in plan:
            task = step.get("task", "").strip()
            if not task:
                continue
                
            agent = self.route(task, agents)
            if not agent:
                logger.warning(f"No suitable agent found for task: '{task}'. Skipping.")
                continue
                
            agent_name = agent.get("name")
            if agent_name not in grouped:
                grouped[agent_name] = []
            grouped[agent_name].append(step)
            
        return grouped

    def _consolidate_tasks(self, steps: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
        """Consolidate multiple tasks for the same agent into a single comprehensive task"""
        if not steps:
            return ""
            
        # Extract all tasks and format them with context
        formatted_tasks = []
        for step in steps:
            task = step.get("task", "").strip()
            if not task:
                continue
                
            try:
                if context:
                    formatted_task = task.format(**context)
                else:
                    formatted_task = task
                formatted_tasks.append(formatted_task)
            except KeyError as e:
                logger.warning(f"Could not format task '{task}' due to missing key: {e}")
                formatted_tasks.append(task)
            except Exception:
                logger.warning(f"Could not format task '{task}', using original")
                formatted_tasks.append(task)
        
        if not formatted_tasks:
            return ""
            
        # If only one task, return it as-is
        if len(formatted_tasks) == 1:
            return formatted_tasks[0]
            
        # Consolidate multiple tasks into a comprehensive request
        consolidated = "Please perform the following analysis tasks comprehensively:\n\n"
        for i, task in enumerate(formatted_tasks, 1):
            consolidated += f"{i}. {task}\n"
        
        consolidated += "\nPlease provide a complete analysis covering all the above tasks in a single comprehensive response."
        
        return consolidated

    def _consolidate_plan_if_needed(self, plan: List[Dict[str, Any]], candidate_agents: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Check if all steps would go to the same agent and consolidate if needed"""
        if len(plan) <= 1:
            return plan
            
        # Get available agents
        agent_list = candidate_agents if candidate_agents else None
        agents = self.discover_agents(agent_list) if agent_list else self.discover_all_agents()
        
        if not agents:
            logger.warning("No agents available for consolidation check")
            return plan
        
        # Check which agent each step would go to
        agent_assignments = []
        for step in plan:
            task = step.get("task", "").strip()
            agent = self.route(task, agents)
            agent_name = agent.get("name") if agent else "unknown"
            agent_assignments.append(agent_name)
        
        # If all steps go to the same agent, consolidate them
        if len(set(agent_assignments)) == 1 and len(agent_assignments) > 1:
            agent_name = agent_assignments[0]
            logger.info(f"All {len(plan)} steps would go to {agent_name}, consolidating into single task")
            
            # Create consolidated task
            consolidated_task = "Please perform the following analysis tasks comprehensively:\n\n"
            for i, step in enumerate(plan, 1):
                consolidated_task += f"{i}. {step['task']}\n"
            consolidated_task += "\nPlease provide a complete analysis covering all the above tasks in a single comprehensive response."
            
            # Return single consolidated step
            return [{
                "task": consolidated_task,
                "output_key": "consolidated_analysis"
            }]
        
        return plan

    def run_workflow(self, plan: List[Dict[str, Any]], candidate_agents: Optional[List[str]] = None) -> Dict[str, Any]:
        logger.info("Starting workflow execution")

        agent_list = candidate_agents if candidate_agents else None
        agents = self.discover_agents(agent_list) if agent_list else self.discover_all_agents()
        
        # CHANGED: More explicit check and logging for agent availability
        if not agents:
            logger.error("Aborting workflow: No agents were discovered or loaded.")
            return {"error": "No agents available for workflow execution", "steps": []}
        
        logger.info(f"Discovered {len(agents)} agents for workflow execution: {[a.get('name') for a in agents]}")

        context: Dict[str, Any] = {}
        results = []

        # NEW: Group related tasks by agent type to consolidate calls
        grouped_steps = self._group_steps_by_agent(plan, agents)
        
        for group_idx, (agent_name, steps_group) in enumerate(grouped_steps.items(), 1):
            logger.info(f"Processing agent group {group_idx}: {agent_name} with {len(steps_group)} tasks")
            
            if len(steps_group) == 1:
                # Single task - process normally
                step = steps_group[0]
                task = step.get("task", "").strip()
                if not task:
                    continue
                
                original_task = task
                try:
                    if context:
                        task = task.format(**context)
                    logger.info(f"Executing single task: Original: '{original_task}', Formatted: '{task}'")
                except KeyError as e:
                    logger.error(f"Failed to format task. Missing key: {e}. Skipping.", exc_info=True)
                    results.append({"agent": "N/A", "task": original_task, "result": {"error": f"Formatting failed, missing context key: {e}"}})
                    continue
                except Exception:
                    logger.warning("Could not format task, using original task string.")
                    pass

                evaluate_criteria = step.get("evaluate_criteria")
                r = self._run_single(task, agent_name)
                ok = self._maybe_evaluate(r, evaluate_criteria)
                if not ok:
                    refine_task = task + "\nPlease revise to satisfy: " + evaluate_criteria
                    r = self._run_single(refine_task, agent_name)
                step_result = {"agent": agent_name, "task": task, "result": r}
                results.append(step_result)

                if isinstance(step_result, dict):
                    res = step_result.get("result") or {}
                    if "error" not in res and res.get("answer"):
                        output_key = step.get("output_key", f"answer_{len(results)}")
                        context[output_key] = res.get("answer")
            else:
                # Multiple tasks for same agent - consolidate
                consolidated_task = self._consolidate_tasks(steps_group, context)
                if not consolidated_task:
                    logger.error(f"Failed to consolidate tasks for agent {agent_name}")
                    continue
                
                logger.info(f"Executing consolidated task for {agent_name}: '{consolidated_task}'")
                r = self._run_single(consolidated_task, agent_name)
                
                # Create result for each original step
                for step in steps_group:
                    step_result = {"agent": agent_name, "task": step.get("task", ""), "result": r}
                    results.append(step_result)
                    
                    # Update context for each output key
                    if isinstance(step_result, dict):
                        res = step_result.get("result") or {}
                        if "error" not in res and res.get("answer"):
                            output_key = step.get("output_key", f"answer_{len(results)}")
                            context[output_key] = res.get("answer")
                            logger.info(f"Context updated. Key: '{output_key}', Value: '{str(res.get('answer'))[:100]}...'")

        return {"steps": results}
    
    # The plan_from_task method remains the same as the previous fix
    def plan_from_task(self, task: str) -> List[Dict[str, Any]]:
        default = [{"task": task.strip(), "output_key": "answer"}]
        try:
            model = os.getenv("AUTOGEN_MODEL", "gpt-4o-mini")
            logger.info("Generating task plan from GPT", extra={"task": task, "model": model})
            prompt = (
                "You are an intelligent assistant that creates a JSON plan to solve a user's task. "
                "Break the main task into 2-4 sequential steps, BUT if all steps would likely be handled by the same type of agent, create a single comprehensive task instead.\n\n"
                "RULES:\n"
                "- Return a valid JSON array of objects. Do not add comments or any other text.\n"
                "- Each object must have a 'task' and an 'output_key'.\n"
                "- The 'task' for a later step MUST use the 'output_key' from a previous step as a placeholder in curly braces if it needs that data. For example: 'Analyze the sales data for {product_name}'.\n"
                "- The first task should address the first logical part of the original user's question.\n"
                "- Ensure 'output_key' is a simple, valid variable name (e.g., 'understocked_materials', 'sales_summary').\n"
                "- IMPORTANT: If all steps would be handled by the same agent type (e.g., all inventory analysis, all turnover analysis), consolidate them into ONE comprehensive task.\n\n"
                "EXAMPLE (Multiple Agents):\n"
                "User Task: 'For the top-selling product, find its supplier.'\n"
                "JSON Plan: "
                '[\n'
                '  {"task": "Identify the top-selling product.", "output_key": "top_product"},\n'
                '  {"task": "Find the supplier for {top_product}.", "output_key": "supplier_info"}\n'
                ']\n\n'
                "EXAMPLE (Same Agent - Consolidate):\n"
                "User Task: 'Check inventory and turnover rate. Find which Materials are selling fast and which are slow'\n"
                "Consolidated JSON Plan: "
                '[{"task": "Perform comprehensive inventory turnover analysis including checking current inventory levels, calculating turnover rates for all materials, and identifying both fast-selling and slow-selling materials with detailed insights and recommendations.", "output_key": "turnover_analysis"}]\n\n'
                "Now, generate the plan for this task:\n"
                f"Task: {task}"
            )
            resp = _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            txt = (resp.choices[0].message.content or "").strip()
            logger.info("Raw plan response from GPT", extra={"response": txt})
            if not txt:
                logger.warning("Empty plan returned by GPT. Falling back to default plan.")
                return default
            plan = _json.loads(txt)
            if isinstance(plan, list) and all(isinstance(step, dict) for step in plan):
                logger.info("Parsed valid plan from GPT", extra={"steps": len(plan)})
                return plan
            else:
                logger.warning("Invalid plan format returned by GPT", extra={"raw_response": txt})
                return default
        except Exception as e:
            logger.error("Failed to generate plan from task", exc_info=True, extra={"error": str(e), "task": task})
            return default

    def plan_and_run(self, task: str, candidate_agents: Optional[List[str]] = None) -> Dict[str, Any]:
        plan = self.plan_from_task(task)
        logger.info("Plan from GPT", extra={"plan": plan})
        
        # Post-process plan to consolidate steps that would go to the same agent
        plan = self._consolidate_plan_if_needed(plan, candidate_agents)
        logger.info("Final plan after consolidation", extra={"plan": plan})
        
        result = self.run_workflow(plan, candidate_agents)
        return {
            "plan": plan,
            "steps": result.get("steps", [])
        }