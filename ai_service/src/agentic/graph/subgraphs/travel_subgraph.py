# ai_service/src/agentic/graph/subgraphs/travel_subgraph.py
import logging
import json
import re
from typing import Any, Union, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from ai_service.src.agentic.graph.state import AgentState
from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.agents.travel_arrangement_agent import create_travel_agent
from ai_service.src.agentic.agents.verification_agent import VerificationAgent
from ai_service.src.agentic.tools.update_profile_tool import profile_updates_ctx
from ai_service.src.agentic.tools.update_visa_knowledge_tool import visa_queue_ctx

def _safe_serialize(obj: Any) -> str:
    """Helper: Safely serialize Pydantic object or Dict to JSON string."""
    if obj is None:
        return "None"
    if hasattr(obj, "model_dump_json"):
        return obj.model_dump_json()
    if isinstance(obj, dict):
        return json.dumps(obj, default=str)
    return str(obj)

def _safe_dump(obj: Any) -> Union[dict, Any]:
    """Helper: Safely dump Pydantic object to dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj

def _extract_dates_from_profile(user_profile: Any) -> tuple[str, str]:
    """Safely extract departure and return dates from user profile."""
    dep_date, ret_date = "Unknown", "Unknown"
    if not user_profile:
        return dep_date, ret_date

    try:
        profile_json_str = user_profile.model_dump_json() if hasattr(user_profile, "model_dump_json") else json.dumps(user_profile, default=str)
        pure_dict = json.loads(profile_json_str)
        
        current_trip = pure_dict.get("current_trip")
        if current_trip:
            dep_date = current_trip.get("departure_date", "Unknown")
            ret_date = current_trip.get("return_date", "Unknown")
    except Exception as e:
        logging.error(f"⚠️ Profile date extraction failed: {e}")
        
    return dep_date, ret_date

def _extract_dates_from_text(user_input: str, messages: list) -> tuple[str, str]:
    """Fallback: Regex extraction from raw text inputs and messages."""
    msg_texts = []
    for m in messages:
        if hasattr(m, "content"):
            msg_texts.append(str(m.content))
        elif isinstance(m, dict) and "content" in m:
            msg_texts.append(str(m["content"]))
            
    all_text = str(user_input) + " " + " ".join(msg_texts)
    
    dates_found = re.findall(r"\d{4}-\d{2}-\d{2}", all_text)
    
    dep_date = dates_found[0] if len(dates_found) >= 1 else "Unknown"
    ret_date = dates_found[1] if len(dates_found) >= 2 else "Unknown"
    
    return dep_date, ret_date

def _build_travel_prompt(state: AgentState) -> dict:
    """Helper: Constructs inputs for the travel agent."""
    medical_plan = state.get("final_selected_medical_plan")
    user_profile = state.get("user_profile")
    user_input = state.get("user_input", "")
    messages = state.get("messages", [])
    
    dep_date, ret_date = _extract_dates_from_profile(user_profile)

    if dep_date == "Unknown" or not dep_date:
        dep_date, ret_date = _extract_dates_from_text(user_input, messages)

    logging.warning(f"🎯 [DEBUG] FINAL DATES SENT TO LLM -> DEPARTURE: {dep_date}, RETURN: {ret_date}")

    prompt_content = f"""
    ====================================================
    🚨 CRITICAL MANDATORY DATES (NO TIME TRAVEL!) 🚨
    ====================================================
    USER REQUESTED DEPARTURE DATE: {dep_date}
    USER REQUESTED RETURN DATE: {ret_date}
    
    RULE 1: You MUST begin the itinerary and flight search exactly on the DEPARTURE DATE: {dep_date}.
    RULE 2: If the medical recovery requires more time, you may push back the RETURN DATE, but NEVER change the DEPARTURE DATE.
    ====================================================
    
    [USER PROFILE]
    {_safe_serialize(user_profile)}
    
    [MEDICAL PLAN TO SUPPORT]
    {_safe_serialize(medical_plan)}
    
    Please proceed to search for flights and accommodations based ONLY on the dates specified above.
    """
    return {"messages": [HumanMessage(content=prompt_content)]}

def _extract_travel_success_data(response: Any) -> dict:
    """Helper: Parses successful travel agent response."""
    travel_output = response.get("structured_response")
    if not travel_output:
        return {"error_message": "Travel Agent returned empty response"}
    
    flight = None
    hotel = None
    if hasattr(travel_output, "flight_suggestions") and travel_output.flight_suggestions:
        flight = travel_output.flight_suggestions[0]
    if hasattr(travel_output, "accommodation_suggestions") and travel_output.accommodation_suggestions:
        hotel = travel_output.accommodation_suggestions[0]

    weather_info = getattr(travel_output, "weather_info", None)

    new_queue = []

    return {
        "travel_options": travel_output,
        "final_selected_flight": flight,
        "final_selected_accommodation": hotel,
        "weather_info": weather_info,
        "data_update_queue": new_queue,
        "current_stage": "travel_completed"
    }

def _prepare_verification_data(state: AgentState) -> tuple[dict, dict] | None:
    """Helper: Prepares data for verification. Returns None if missing critical data."""
    flight = state.get("final_selected_flight")
    hotel = state.get("final_selected_accommodation")
    
    if not flight and not hotel:
        return None
        
    plan_snapshot = {
        "flight": _safe_dump(flight),
        "hotel": _safe_dump(hotel)
    }
    profile_dict = _safe_dump(state.get("user_profile"))
    return plan_snapshot, profile_dict

def _merge_profile_updates(state: AgentState, current_profile_updates: dict) -> dict:
    """Helper: Safely merges new preferences into the existing user profile."""
    existing_profile = state.get("user_profile", {})
    p_dict = existing_profile.model_dump() if hasattr(existing_profile, "model_dump") else dict(existing_profile)
    
    if "preferences" not in p_dict:
        p_dict["preferences"] = {}
    p_dict["preferences"].update(current_profile_updates)
    
    return p_dict

async def _run_travel_plan(state: AgentState, travel_agent: Any) -> dict:
    """Core logic for travel planning execution."""
    logging.info("✈️ Planning Travel...")
    agent_input = _build_travel_prompt(state)
    
    # Allocate thread-safe memory space
    current_profile_updates = {}
    current_visa_queue = []
    
    token_profile = profile_updates_ctx.set(current_profile_updates)
    token_visa = visa_queue_ctx.set(current_visa_queue)
    
    try:
        response = await travel_agent.ainvoke(agent_input)
        result_payload = _extract_travel_success_data(response)
        
        # Merge new data retrieved by tools into the State
        if current_profile_updates:
            result_payload["user_profile"] = _merge_profile_updates(state, current_profile_updates)
        
        if current_visa_queue:
            result_payload["data_update_queue"] = current_visa_queue
            
        return result_payload
        
    except Exception as e:
        logging.error(f"Travel Agent Failed: {e}", exc_info=True)
        return {"error_message": str(e), "current_stage": "travel_failed"}
        
    finally:
        # Ultimate memory management cleanup
        profile_updates_ctx.reset(token_profile)
        visa_queue_ctx.reset(token_visa)

async def _run_verify_travel(state: AgentState, verifier: VerificationAgent) -> Command[Literal["__end__"]]:
    """Core logic for travel verification execution."""
    logging.info("🔍 Verifying Travel Plan...")
    
    data = _prepare_verification_data(state)
    if not data:
        logging.warning("Skipping verification: Missing flight and hotel.")
        return Command(goto=END)
        
    plan_snapshot, profile_dict = data
    
    try:
        result = await verifier.verify_plan(
            user_profile=profile_dict,
            plan_data=plan_snapshot,
            scope="travel"
        )
        
        if result.is_valid:
            logging.info("✅ Travel Plan Approved")
            return Command(goto=END)
        
        logging.warning(f"❌ Travel Verification Failed: {result.feedback}")
        return Command(
            update={"error_message": f"Travel plan invalid: {result.feedback}"},
            goto=END
        )
            
    except Exception as e:
        logging.error(f"Verification Logic Error: {e}")
        return Command(goto=END)

def create_travel_subgraph(config: AppConfig):
    """
    [Factory] Creates the Travel Arrangement Subgraph.
    """
    travel_agent = create_travel_agent(config)
    verifier = VerificationAgent(config)

    # Clean wrapper nodes using standard delegation
    async def node_travel_plan(state: AgentState):
        return await _run_travel_plan(state, travel_agent)

    async def node_verify_travel(state: AgentState) -> Command[Literal["__end__"]]:
        return await _run_verify_travel(state, verifier)

    workflow = StateGraph(AgentState)
    workflow.add_node("planner", node_travel_plan)
    workflow.add_node("verifier", node_verify_travel)
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "verifier")
    
    return workflow.compile()