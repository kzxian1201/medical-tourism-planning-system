# ai_service/src/agentic/graph/subgraphs/medical_subgraph.py
import logging
import asyncio
import re
from typing import Any, Dict
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from ai_service.src.agentic.graph.state import AgentState
from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.agents.medical_planning_agent import create_medical_agent
from ai_service.src.agentic.tools.update_profile_tool import profile_updates_ctx

def _parse_cost(value: Any) -> float:
    """Robust string to cost parser."""
    if value is None: return 0.0
    if isinstance(value, (int, float)): return float(value)
    s = str(value).strip().lower().replace(',', '')
    matches = re.findall(r'\d+(?:\.\d+)?', s)
    if matches:
        nums = [float(m) for m in matches]
        return sum(nums) / len(nums)
    return 0.0

def _prepare_medical_inputs(state: AgentState) -> dict:
    """Helper: Extracts state and builds the prompt message."""
    user_profile = state.get("user_profile")
    if not user_profile:
        raise ValueError("Missing User Profile")

    # Robust User Input Extraction
    user_input = state.get("user_input")
    if not user_input and state.get("messages"):
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "content"):
            user_input = last_msg.content
    
    if not user_input:
        user_input = "Plan a general medical checkup based on my profile."

    # Safe Serialization
    profile_json = (
        user_profile.model_dump_json(indent=2)
        if hasattr(user_profile, "model_dump_json")
        else str(user_profile)
    )
    
    prompt_content = f"""
    [USER REQUEST]
    {user_input}
    
    [USER PROFILE CONTEXT]
    {profile_json}
    """
    return {"messages": [HumanMessage(content=prompt_content)]}

def _apply_financial_circuit_breaker(result_payload: Dict[str, Any], state: AgentState) -> None:
    """
    Helper: Evaluates the cost against the budget. 
    Mutates result_payload in-place if a circuit breaker is triggered.
    """
    med_plan = result_payload.get("final_selected_medical_plan")
    if not med_plan:
        return

    # Extract user profile and budget
    user_profile = state.get("user_profile", {})
    if hasattr(user_profile, "model_dump"):
        user_profile = user_profile.model_dump()
        
    budget_str = (user_profile.get("current_trip") or {}).get("estimated_budget_usd", "0")
    budget_val = _parse_cost(budget_str)
    
    # Extract medical cost safely
    if isinstance(med_plan, dict):
        med_cost_str = med_plan.get("estimated_cost_usd", "0")
    else:
        med_cost_str = getattr(med_plan, "estimated_cost_usd", "0")
        
    med_cost_val = _parse_cost(med_cost_str)

    # Circuit Breaker Condition: Cost exceeds budget by 150%
    if budget_val > 0 and med_cost_val > (budget_val * 1.5):
        logging.warning(f"🚨 FINANCIAL CIRCUIT BREAKER TRIGGERED: Medical cost (${med_cost_val}) exceeds budget (${budget_val}) limit.")
        
        # Update routing status
        result_payload["status"] = "budget_insufficient"
        
        # Inject warning into the description for the user
        warning_msg = f"🚨 [BUDGET INSUFFICIENT] Your budget is ${budget_val}, but this procedure costs approx ${med_cost_val}. We have halted travel/logistics bookings to prevent severe overspending. Please revise your budget or consult for alternative treatments."
        
        if isinstance(med_plan, dict):
            med_plan["brief_description"] = warning_msg + " " + str(med_plan.get("brief_description", ""))
        else:
            med_plan.brief_description = warning_msg + " " + str(getattr(med_plan, "brief_description", ""))

async def _execute_medical_agent_with_retry(agent, agent_input: dict, max_retries: int) -> dict:
    """Helper: Handles the retry loop and response parsing."""
    attempt = 0
    backoff_delay = 1

    while attempt < max_retries:
        try:
            attempt += 1
            response = await agent.ainvoke(agent_input)
            
            # Check Structured Output
            if "structured_response" in response:
                output_obj = response["structured_response"]
                if output_obj.medical_plan_options:
                    logging.info(f"✅ Medical Plan Generated (Attempt {attempt})")
                    return {
                        "medical_plan_options": output_obj.medical_plan_options,
                        "final_selected_medical_plan": output_obj.medical_plan_options[0],
                        "current_stage": "medical_completed",
                        "error_message": None
                    }
            logging.warning(f"⚠️ Attempt {attempt}: No structured response.")
            
        except Exception as e:
            logging.error(f"❌ Attempt {attempt} Failed: {str(e)}")
            if attempt >= max_retries:
                return {
                    "final_selected_medical_plan": None,
                    "current_stage": "medical_failed",
                    "error_message": f"Medical planning failed: {str(e)}"
                }
        
        # Exponential Backoff
        if attempt < max_retries:
            await asyncio.sleep(backoff_delay * (2 ** (attempt - 1)))

    return {"current_stage": "medical_failed", "error_message": "Max retries exceeded"}

def create_medical_subgraph(config: AppConfig):
    """
    [Factory] Creates the Medical Planning Subgraph.
    """
    medical_agent = create_medical_agent(config)

    async def node_medical_planner(state: AgentState, config: RunnableConfig) -> dict:
        """Node Logic: Plans medical treatment based on user profile and input."""
        logging.info("🏥 Planning Medical Treatment...")
        
        configurable = config.get("configurable", {})
        max_retries = configurable.get("max_retries", 3)
        
        try:
            agent_input = _prepare_medical_inputs(state)
        except ValueError as e:
            return {"error_message": str(e), "current_stage": "medical_failed"}

        # Context of mounted image update
        current_profile_updates = {}
        token = profile_updates_ctx.set(current_profile_updates)

        try:
            # Execute Agent with Retry
            result_payload = await _execute_medical_agent_with_retry(medical_agent, agent_input, max_retries)

            # Apply Financial Circuit Breaker (Mutates result_payload safely)
            _apply_financial_circuit_breaker(result_payload, state)

            # Inject new user preferences if captured
            if current_profile_updates:
                existing_profile = state.get("user_profile", {})
                p_dict = existing_profile.model_dump() if hasattr(existing_profile, "model_dump") else dict(existing_profile)
                
                if "preferences" not in p_dict:
                    p_dict["preferences"] = {}
                p_dict["preferences"].update(current_profile_updates)
                
                result_payload["user_profile"] = p_dict
                
            return result_payload
        
        finally:
            # Release memory context
            profile_updates_ctx.reset(token)

    workflow = StateGraph(AgentState)
    workflow.add_node("planner", node_medical_planner)
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", END)

    return workflow.compile()