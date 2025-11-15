# ai_service/src/agentic/graph/graph.py
import json
import sys
from typing import Literal, Optional, Any
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.redis import RedisSaver
from .state import AgentState
from ..models import (MedicalPlanningOutput, TravelArrangementOutput, TravelLogisticsOutput, CalculateBudgetInput, AgentResponse, MedicalPlanOption, FlightOptionSummary, AccommodationOption)
from ..agents.medical_planning_agent import MedicalPlanningAgent
from ..agents.travel_arrangement_agent import TravelArrangementAgent
from ..agents.travel_logistics_agent import TravelLogisticsAgent
from ..tools.calculate_budget_tool import CalculateBudgetTool
from ..logger import logging
from datetime import datetime

# --- 1. Instantiate agents and tool. ---
# These are the "workers" of the graph, which will be called internally within the nodes.
try:
    medical_planner = MedicalPlanningAgent()
    travel_planner = TravelArrangementAgent()
    logistics_planner = TravelLogisticsAgent()
    budget_calculator = CalculateBudgetTool()
except Exception as e:
    logging.error(f"Failed to initialize the agents and tool: {e}", exc_info=True)
    sys.exit(1) 

# --- 2. Utility functions ---
def _create_error_response(error_message: str, stage: str) -> dict:
    """Create a standardized error status update."""
    logging.error(f"An error occurred in stage '{stage}': {error_message}")
    return {
        "last_agent_message": AgentResponse(
            message_type="text",
            content={"prompt": f"Sorry, an error occurred during the {stage} stage: {error_message}"}
        ),
        "current_stage": "error"
    }

def _find_in_list_by_id(item_list: Optional[list], item_id: Optional[str]) -> Optional[Any]:
    """Safely search for an item in the list of objects by ID."""
    if not item_list or not item_id:
        return None
    for item in item_list:
        if isinstance(item, dict):
            if item.get("id") == item_id:
                return item
        elif hasattr(item, 'id') and item.id == item_id:
            return item
    return None
# --- 3. Defining the nodes of graph. ---
# Each node is a Python function that receives an AgentState object and returns a dictionary to update the state.
def node_start_planning(state: AgentState) -> dict:
    """
    Node 1: Startup Planning (Smart Start).
    Extract data from user_profile and prepare the first welcome message.
    """
    logging.info("Node: Start Planning (node_start_planning)")
    profile = state.get("user_profile", {})
    
    # Extract the "Smart Start" logic 
    destination = profile.get("destination_country", "Destination not specified")
    purpose = profile.get("medicalPurpose", "Unspecified purpose")

    welcome_prompt = f"Hello! I see you're interested in traveling to {destination} for {purpose}. Is that correct?"
    
    # Add the user's initial input to the history.
    history = list(state.get("chat_history", []))
    history.append(HumanMessage(content=state.get("user_input") or "Start"))
    
    return {
        "user_profile": profile,
        "chat_history": history,
        "last_agent_message": AgentResponse(
            message_type="text",
            content={"prompt": welcome_prompt}
        ),
        "current_stage": "medical_planning_pending" # go into the next stage
    }

async def node_call_medical_planner(state: AgentState) -> dict:
    """
    Node 2: (Phase one) Call the MedicalPlanningAgent.
    """
    logging.info("Node: Call medical planning agent (node_call_medical_planner)")
    profile = state.get("user_profile", {}) 
    history = list(state.get("chat_history", []))
    history.append(HumanMessage(content=state.get("user_input") or "Please begin planning."))

    try:
        # ensure type safety
        estimated_budget = profile.get("estimatedBudget")
        if isinstance(estimated_budget, (str, int, float)):
            try:
                estimated_budget = float(estimated_budget)
            except ValueError:
                estimated_budget = 0.0
        else:
            estimated_budget = 0.0

        departure_date = profile.get("departureDate")
        departure_date = datetime.now()
        if isinstance(departure_date, str):
            try:
                departure_date = datetime.fromisoformat(departure_date)
            except Exception:
                logging.warning(f"Invalid date format: {departure_date}, using today instead.")

        tool_input_dict = {
            "medical_purpose": profile.get("medicalPurpose"),
            "patient_nationality": profile.get("nationality"),
            "destination_country": profile.get("destination_country"),
            "estimated_budget_usd": str(estimated_budget),
            "departure_date": departure_date.isoformat(),
            "accompanying_guests": int(profile.get("accompanyingGuests", 0))
        }
        
        result: MedicalPlanningOutput = await medical_planner.ainvoke(tool_input_dict)

        if result.error:
            return _create_error_response(result.error, "Medical Planning")

        # Preparing the "summary_cards" message to be sent to the frontend
        agent_message = AgentResponse(
            message_type="summary_cards",
            content={
                "planning_type": "medical_plans",
                "payload": result.model_dump()
            }
        )
        
        return {
            "chat_history": history,
            "medical_plan_options": result.medical_plan_options,
            "last_agent_message": agent_message,
            "current_stage": "medical_selection_pending" 
        }
    except Exception as e:
        return _create_error_response(f"Error in implementing medical planning: {e}", "Medical Planning")

def node_process_medical_selection(state: AgentState) -> dict:
    """
    Node 3: Processing the user's medical treatment plan selection.
    """
    logging.info("Node: Handling medical choices (node_process_medical_selection)")
    selected_id = state.get("selected_medical_plan_id")
    options = state.get("medical_plan_options", [])
    
    selected_plan = _find_in_list_by_id(options, selected_id)
    
    if not selected_plan:
        return _create_error_response(f"The selected plan ID '{selected_id}' is invalid.", "Medical plan selection")
        
    history = list(state.get("chat_history", []))
    history.append(HumanMessage(content=f"I have selected a plan: {selected_id}"))

    return {
        "chat_history": history,
        "final_selected_medical_plan": selected_plan,
        "current_stage": "travel_planning_pending" 
    }

async def node_call_travel_planner(state: AgentState) -> dict:
    """
    Node 4: (Phase two) Call the TravelArrangementAgent
    """
    logging.info("Node: Call travel planning agent (node_call_travel_planner)")
    profile = state.get("user_profile", {})
    medical_plan = state.get("final_selected_medical_plan")
    
    if not medical_plan:
        return _create_error_response("Medical plan not selected.", "Travel Arrangement")
    
    check_in_date = profile.get("departureDate")
    return_date = profile.get("returnDate")

    if not check_in_date or not return_date:
        error_msg = f"Missing 'departureDate' ({check_in_date}) or 'returnDate' ({return_date}) in user_profile. Cannot proceed."
        logging.error(error_msg)
        return _create_error_response(error_msg, "Travel Arrangement")
        
    try:
        # Input from the AgentState build tool
        tool_input_kwargs = {
            "departure_city": profile.get("departureCity"),
            "estimated_return_date": return_date, 
            "medical_destination_city": medical_plan.clinic_location.split(",")[0].strip(),
            "medical_destination_country": medical_plan.clinic_location.split(",")[-1].strip(),
            "check_in_date": check_in_date, 
            "check_out_date": return_date, 
            "num_guests_medical_plan": profile.get("accompanyingGuests", 0) + 1,
            "visa_information_from_medical_plan": medical_plan.full_hospital_details.get("visa_information") if hasattr(medical_plan, 'full_hospital_details') and medical_plan.full_hospital_details else None, 
            "accessibility_needs": profile.get("accessibilityNeeds", []),
        }
        
        result: TravelArrangementOutput = await travel_planner.ainvoke(tool_input_kwargs)
        
        if result.error:
            return _create_error_response(result.error, "Travel Arrangement")

        agent_message = AgentResponse(
            message_type="summary_cards",
            content={
                "planning_type": "travel_arrangements",
                "payload": result.model_dump()
            }
        )
        
        return {
            "chat_history": list(state.get("chat_history", [])), 
            "travel_options": result, 
            "last_agent_message": agent_message,
            "current_stage": "travel_selection_pending" 
        }
    except Exception as e:
        return _create_error_response(f"Error while executing travel planning: {e}", "Travel Arrangement")

def node_process_travel_selection(state: AgentState) -> dict:
    """
    Node 5: Processing the user's travel plan selections (flights and accommodation).
    """
    logging.info("Node: Processing travel choices (node_process_travel_selection)")
    flight_id = state.get("selected_flight_id") 
    accom_id = state.get("selected_accommodation_id") 
    options: Optional[TravelArrangementOutput] = state.get("travel_options")
    
    if not options:
         return _create_error_response("No travel options found.", "Travel options")

    selected_flight = _find_in_list_by_id(options.flight_suggestions, flight_id)
    selected_accom = _find_in_list_by_id(options.accommodation_suggestions, accom_id)
    
    if not selected_flight or not selected_accom:
        return _create_error_response(f"The selected flight ID '{flight_id}' or accommodation ID '{accom_id}' is invalid.", "Travel options")

    history = list(state.get("chat_history", []))
    history.append(HumanMessage(content=f"I have selected flight: {flight_id} and accommodation: {accom_id}"))
    
    return {
        "chat_history": history,
        "final_selected_flight": selected_flight,
        "final_selected_accommodation": selected_accom,
        "current_stage": "logistics_planning_pending" 
    }

async def node_call_logistics_planner(state: AgentState) -> dict:
    """
    Node 6: (Phase three) Call the TravelLogisticsAgent
    """
    logging.info("Node: Call local logistics agent (node_call_logistics_planner)")
    profile = state.get("user_profile", {}) 
    medical_plan = state.get("final_selected_medical_plan") 
    flight = state.get("final_selected_flight") 
    accom = state.get("final_selected_accommodation") 
    travel_options = state.get("travel_options") 
    
    if not all([profile, medical_plan, flight, accom, travel_options]):
         return _create_error_response("Missing data from previous steps (plan, flight, accom).", "Logistics Planning")
    
    try:
        return_date = profile.get("returnDate")

        tool_input_kwargs = {
            "medical_purpose": medical_plan.treatment_name,
            "medical_destination_city": medical_plan.clinic_location.split(",")[0].strip(),
            "medical_destination_country": medical_plan.clinic_location.split(",")[-1].strip(),
            "medical_stay_start_date": profile.get("departureDate"),
            "medical_stay_end_date": return_date, 
            "num_guests_total": profile.get("accompanyingGuests", 0) + 1,
            "airport_pick_up_required": True, 
            "patient_accessibility_needs": profile.get("accessibilityNeeds", None)
        }

        result: TravelLogisticsOutput = await logistics_planner.ainvoke(tool_input_kwargs)
        
        if result.error:
            return _create_error_response(result.error, "local logistics")
        
        agent_message = AgentResponse(
            message_type="summary_cards", 
            content={
                "planning_type": "travel_logistics",
                "payload": result.model_dump()
            }
        )

        return {
            "chat_history": list(state.get("chat_history", [])), 
            "logistics_plan": result, 
            "final_selected_logistics": result, 
            "last_agent_message": agent_message,
            "current_stage": "budget_planning_pending" 
        }
    except Exception as e:
        return _create_error_response(f"An error occurred while executing the local logistics plan: {e}", "local logistics")

async def node_call_budget_calculator(state: AgentState) -> dict:
    """
    Node 7: (Phase two) Call the CalculateBudgetTool
    """
    logging.info("Node: Call budget calculation (node_call_budget_calculator)")
    
    travel_options = state.get("travel_options")
    if not travel_options:
        return _create_error_response("Missing travel options state for date calculation.", "Calculate Budget")

    plan_params = {
        "medical_plan": state.get("final_selected_medical_plan"),
        "flight": state.get("final_selected_flight"),
        "accommodation": state.get("final_selected_accommodation"), 
        "local_logistics": state.get("final_selected_logistics"), 
        "check_in_date": state.get("user_profile", {}).get("departureDate"), 
        "check_out_date": travel_options.estimated_return_date, 
    }
    
    tool_input_kwargs = {"session_state": {"plan_parameters": plan_params}}
    
    try:
        result_str = await budget_calculator.ainvoke(tool_input_kwargs)
        
        if isinstance(result_str, str):
            result_json = json.loads(result_str)
        else:
            result_json = result_str 
        
        if result_json.get("error"):
            return _create_error_response(result_json["error"], "Calculate Budget")

        return {
            "final_budget": result_json,
            "current_stage": "final_plan_generation_pending" 
        }
    except Exception as e:
        return _create_error_response(f"Error during budget calculation: {e}", "Calculate Budget")

def node_generate_final_plan(state: AgentState) -> dict:
    """
    Node 8: (Final) Generate the complete plan report.
    """
    logging.info("Node: Generate final plan (node_generate_final_plan)")
    
    medical_plan = state.get("final_selected_medical_plan") 
    flight = state.get("final_selected_flight") 
    accom = state.get("final_selected_accommodation")
    local_logistics = state.get("final_selected_logistics") 

    def safe_model_dump(model):
        if hasattr(model, "model_dump"):
            return model.model_dump()
        elif isinstance(model, dict):
            return model
        return {}

    final_plan_content = {
        "medical_plan": safe_model_dump(medical_plan),
        "travel_arrangement": {
            "flight": safe_model_dump(flight),
            "accommodation": safe_model_dump(accom),
        },
        "local_logistics": safe_model_dump(local_logistics),
        "total_budget": state.get("final_budget") 
    }
    
    agent_message = AgentResponse(
        message_type="final_plan",
        content=final_plan_content
    )
    
    return {
        "chat_history": list(state.get("chat_history", [])), 
        "last_agent_message": agent_message,
        "current_stage": "final_confirmation_pending" 
    }
    
def node_ask_final_confirmation(state: AgentState) -> dict:
    """
    Node 9: Ask the user for final confirmation.
    """
    logging.info("Node: Request for final confirmation (node_ask_final_confirmation)")
    
    agent_message = AgentResponse(
        message_type="question",
        content={
            "id": "final_confirm_q",
            "prompt": "Your complete plan is ready. Do you confirm this complete plan?",
            "type": "single_select_pill"
        }
    )
    
    return {
        "chat_history": state.get("chat_history", []),
        "last_agent_message": agent_message,
        "current_stage": "final_confirmation_pending" 
    }

def node_finish_plan(state: AgentState) -> dict:
    """
    Node 10: (Final) Send a concluding message to the user.
    This node ensures 'last_agent_message' is set before the graph ends.
    """
    logging.info("Node: Finish Plan (node_finish_plan)")
    
    agent_message = AgentResponse(
        message_type="text",
        content={"prompt": "Your plan is confirmed! Thank you for using our service."}
    )
    
    return {
        "chat_history": list(state.get("chat_history", [])), 
        "last_agent_message": agent_message,
        "current_stage": "finished" 
    }

def node_handle_error(state: AgentState) -> dict:
    """
    Node: Error handling.
    """
    logging.info("Node: Error handling. (node_handle_error)")
    return {"current_stage": "error_handled"} 

def node_router_junction(state: AgentState) -> dict:
    """
    A simple node that just passes the state through.
    It acts as a junction point for the router logic to attach to.
    This node MUST return a dict (even empty) to satisfy LangGraph's node requirements.
    """
    logging.info(f"Router Junction: Passing state with stage '{state.get('current_stage')}'") 
    return {}

# --- 4. Define Conditional Edge ---
def router(state: AgentState) -> Literal[
    "node_start_planning",
    "node_call_medical_planner",
    "node_process_medical_selection",
    "node_call_travel_planner",
    "node_process_travel_selection",
    "node_call_logistics_planner",
    "node_call_budget_calculator",
    "node_generate_final_plan",
    "node_ask_final_confirmation",
    "node_handle_error",
    "__end__"
]:
    """
    Conditional routing node:
    Determines the next step in the graph based on `current_stage`.
    """
    stage = state.get("current_stage") or "start"  
    user_input = (state.get("user_input") or "").lower().strip() 
    logging.info(f"Router: Current Stage = '{stage}' | User Input = '{user_input}'")

    if "restart" in user_input:
        logging.warning("Router: User requested to restart entire plan.")
        return "node_start_planning"

    if stage == "error":
        return "node_handle_error"
    if stage == "error_handled":
        return END

    if stage == "start":
        return "node_start_planning"

    if stage == "medical_planning_pending":
        return "node_call_medical_planner"

    if stage == "medical_selection_pending":
        if any(keyword in user_input for keyword in ["edit", "change", "modify", "regenerate"]):
            logging.info("Router: User requested to edit medical plan. Re-enter medical planner.")
            return "node_call_medical_planner"
        elif state.get("selected_medical_plan_id"): 
            return "node_process_medical_selection"
        else:
            logging.info("Router: Awaiting user medical plan selection... INTERRUPTING.")
            return END

    if stage == "travel_planning_pending":
        return "node_call_travel_planner"

    if stage == "travel_selection_pending":
        if any(keyword in user_input for keyword in ["edit", "change", "modify", "regenerate"]):
            logging.info("Router: User requested to edit travel plans. Re-enter travel planner.")
            return "node_call_travel_planner"
        elif state.get("selected_flight_id") and state.get("selected_accommodation_id"): 
            return "node_process_travel_selection"
        else:
            logging.info("Router: Awaiting user travel selection... INTERRUPTING.")
            return END

    if stage == "logistics_planning_pending":
        if any(keyword in user_input for keyword in ["edit", "change", "modify", "regenerate"]):
            logging.info("Router: User requested to edit local logistics. Re-enter logistics planner.")
            return "node_call_logistics_planner"
        return "node_call_logistics_planner"

    if stage == "budget_planning_pending":
        if any(keyword in user_input for keyword in ["edit", "change", "modify", "recalculate", "adjust"]):
            logging.info("Router: User requested to recalculate budget. Rerun budget calculator.")
        return "node_call_budget_calculator"

    if stage == "final_plan_generation_pending":
        return "node_generate_final_plan"

    if stage == "final_confirmation_pending":
        if any(keyword in user_input for keyword in ["edit", "change", "modify", "regenerate"]):
            logging.info("Router: User requested to modify final plan. Restart from medical stage.")
            return "node_call_medical_planner"
        elif any(keyword in user_input for keyword in ["confirm", "yes", "ok"]):
            logging.info("Router: User confirmed final plan. Routing to node_finish_plan.")
            return "node_finish_plan"
        else:
            logging.warning("Router: No valid confirmation received, ending flow.")
            return END

    logging.warning(f"Router: Unrecognized stage '{stage}', ending flow.")
    return END

# --- 5. Building and compiling graphs ---
def create_graph(checkpointer: InMemorySaver | RedisSaver):    
    """
    Create and compile the LangGraph workflow.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("node_start_planning", node_start_planning)
    workflow.add_node("node_call_medical_planner", node_call_medical_planner)
    workflow.add_node("node_process_medical_selection", node_process_medical_selection)
    workflow.add_node("node_call_travel_planner", node_call_travel_planner)
    workflow.add_node("node_process_travel_selection", node_process_travel_selection)
    workflow.add_node("node_call_logistics_planner", node_call_logistics_planner)
    workflow.add_node("node_call_budget_calculator", node_call_budget_calculator)
    workflow.add_node("node_generate_final_plan", node_generate_final_plan)
    workflow.add_node("node_ask_final_confirmation", node_ask_final_confirmation)
    workflow.add_node("node_finish_plan", node_finish_plan)
    workflow.add_node("node_handle_error", node_handle_error)
    workflow.add_node("router_junction", node_router_junction)

    workflow.set_entry_point("router_junction")

    workflow.add_edge("node_start_planning", "router_junction")
    workflow.add_edge("node_call_medical_planner", "router_junction")
    workflow.add_edge("node_process_medical_selection", "router_junction")
    workflow.add_edge("node_call_travel_planner", "router_junction")
    workflow.add_edge("node_process_travel_selection", "router_junction")
    workflow.add_edge("node_call_logistics_planner", "router_junction")
    workflow.add_edge("node_call_budget_calculator", "router_junction")
    workflow.add_edge("node_generate_final_plan", "router_junction")
    workflow.add_edge("node_ask_final_confirmation", "router_junction")
    workflow.add_edge("node_finish_plan", END)
    workflow.add_edge("node_handle_error", END) 

    node_map = {
        "node_start_planning": "node_start_planning",
        "node_call_medical_planner": "node_call_medical_planner",
        "node_process_medical_selection": "node_process_medical_selection",
        "node_call_travel_planner": "node_call_travel_planner",
        "node_process_travel_selection": "node_process_travel_selection",
        "node_call_logistics_planner": "node_call_logistics_planner",
        "node_call_budget_calculator": "node_call_budget_calculator",
        "node_generate_final_plan": "node_generate_final_plan",
        "node_ask_final_confirmation": "node_ask_final_confirmation",
        "node_finish_plan": "node_finish_plan",
        "node_handle_error": "node_handle_error",
        "__end__": END
    }
    
    workflow.add_conditional_edges("router_junction", router, node_map)

    try:
        app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=[
                "node_process_medical_selection", 
                "node_process_travel_selection",
                "node_call_budget_calculator",  
                "node_ask_final_confirmation" 
            ]
        )

        logging.info("LangGraph 1.0 graph compiled successfully.")
    except Exception as e:
        logging.error(f"Failed to compile LangGraph workflow: {e}", exc_info=True)
        raise

    return app

