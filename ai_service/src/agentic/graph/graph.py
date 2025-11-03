# ai_service/src/agentic/graph/graph.py
import json
import sys
from typing import Literal, Optional, Any
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from .state import AgentState
from ..models import (MedicalPlanningInput, TravelArrangementInput, TravelLogisticsInput, CalculateBudgetInput, AgentResponse, MedicalPlanOption, FlightOptionSummary, AccommodationOption)
from ..tools.medical_planning_tool import MedicalPlanningTool
from ..tools.travel_arrangement_tool import TravelArrangementTool
from ..tools.travel_logistics_tool import TravelLogisticsTool
from ..tools.calculate_budget_tool import CalculateBudgetTool
from ..logger import logging
from ..exception import CustomException

# --- 1. Instantiate main tool. ---
# These are the "workers" of the graph, which will be called internally within the nodes.
try:
    medical_planner = MedicalPlanningTool()
    travel_planner = TravelArrangementTool()
    logistics_planner = TravelLogisticsTool()
    budget_calculator = CalculateBudgetTool()
except Exception as e:
    logging.error(f"Failed to initialize main tools: {e}", exc_info=True)
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
    return next((item for item in item_list if hasattr(item, 'id') and item.id == item_id), None)

# --- 3. Defining the nodes of graph. ---
# Each node is a Python function that receives an AgentState object and returns a dictionary to update the state.
def node_start_planning(state: AgentState) -> dict:
    """
    Node 1: Startup Planning (Smart Start).
    Extract data from user_profile and prepare the first welcome message.
    """
    logging.info("Node: Start Planning (node_start_planning)")
    profile = state["user_profile"]
    
    # Extract the "Smart Start" logic 
    destination = profile.get("destination_country", "Destination not specified")
    purpose = profile.get("medicalPurpose", "Unspecified purpose")

    welcome_prompt = f"Hello! I see you're interested in traveling to {destination} for {purpose}. Is that correct?"
    
    # Add the user's initial input to the history.
    history = state.get("chat_history", []) + [HumanMessage(content=state.get("user_input", "Start"))]
    
    return {
        "chat_history": history,
        "last_agent_message": AgentResponse(
            message_type="text",
            content={"prompt": welcome_prompt}
        ),
        "current_stage": "medical_planning_pending" # go into the next stage
    }

def node_call_medical_planner(state: AgentState) -> dict:
    """
    Node 2: (Phase one) Call the MedicalPlanningTool.
    """
    logging.info("Node: Call medical planning tool (node_call_medical_planner)")
    profile = state["user_profile"]
    history = state.get("chat_history", []) + [HumanMessage(content=state.get("user_input", "Please begin planning."))]

    try:
        # Input from the AgentState build tool
        tool_input = MedicalPlanningInput(
            medical_purpose=profile.get("medicalPurpose"),
            patient_nationality=profile.get("nationality"),
            destination_country=profile.get("destination_country"),
            estimated_budget_usd=profile.get("estimatedBudget"),
            departure_date=profile.get("departureDate"),
            accompanying_guests=profile.get("accompanyingGuests", 0)
        )
        
        result = medical_planner._run(tool_input=tool_input)

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
            "chat_history": history + [AIMessage(content=json.dumps(agent_message.model_dump()))],
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
    options = state.get("medical_plan_options")
    
    selected_plan = _find_in_list_by_id(options, selected_id)
    
    if not selected_plan:
        return _create_error_response(f"The selected plan ID '{selected_id}' is invalid.", "Medical plan selection")
        
    history = state.get("chat_history", []) + [HumanMessage(content=f"I have selected a plan: {selected_id}")]

    return {
        "chat_history": history,
        "final_selected_medical_plan": selected_plan,
        "current_stage": "travel_planning_pending" 
    }

def node_call_travel_planner(state: AgentState) -> dict:
    """
    Node 4: (Phase two) Call the TravelArrangementTool
    """
    logging.info("Node: Call travel planning (node_call_travel_planner)")
    profile = state["user_profile"]
    medical_plan = state["final_selected_medical_plan"]
    
    # Safely extract data from Pydantic models
    medical_plan_obj = MedicalPlanOption.model_validate(medical_plan)
    
    # Assume the user's next input is to confirm and provide a return date
    return_date = state.get("user_input", profile.get("departureDate")) # Temporary rollback
    
    try:
        # Input from the AgentState build tool
        tool_input = TravelArrangementInput(
            departure_city=profile.get("departureCity"),
            estimated_return_date=return_date,
            medical_destination_city=medical_plan_obj.clinic_location.split(",")[0].strip(),
            medical_destination_country=medical_plan_obj.clinic_location.split(",")[-1].strip(),
            check_in_date=profile.get("departureDate"),
            check_out_date=return_date,
            num_guests_medical_plan=profile.get("accompanyingGuests", 0) + 1,
            visa_information_from_medical_plan=medical_plan_obj.full_hospital_details.get("visa_information"),
            accessibility_needs=profile.get("accessibilityNeeds", []),
        )
        
        result = travel_planner._run(tool_input=tool_input)
        
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
            "chat_history": state.get("chat_history", []) + [AIMessage(content=json.dumps(agent_message.model_dump()))],
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
    options = state.get("travel_options") 
    
    if not options:
         return _create_error_response("No travel options found.。", "Travel options")

    selected_flight = _find_in_list_by_id(options.flight_suggestions, flight_id)
    selected_accom = _find_in_list_by_id(options.accommodation_suggestions, accom_id)
    
    if not selected_flight or not selected_accom:
        return _create_error_response(f"The selected flight ID '{flight_id}' or accommodation ID '{accom_id}' is invalid.", "Travel options")

    history = state.get("chat_history", []) + [HumanMessage(content=f"I have selected flight: {flight_id} and accommodation: {accom_id}")]
    
    return {
        "chat_history": history,
        "final_selected_flight": selected_flight,
        "final_selected_accommodation": selected_accom,
        "current_stage": "logistics_planning_pending" 
    }

def node_call_logistics_planner(state: AgentState) -> dict:
    """
    Node 6: (Phase three) Call the TravelLogisticsTool
    """
    logging.info("Node: Call local logistics (node_call_logistics_planner)")
    profile = state["user_profile"]
    medical_plan = MedicalPlanOption.model_validate(state["final_selected_medical_plan"])
    flight = FlightOptionSummary.model_validate(state["final_selected_flight"])
    accom = AccommodationOption.model_validate(state["final_selected_accommodation"])
    
    try:
        # Input from the AgentState build tool
        tool_input = TravelLogisticsInput(
            medical_purpose=medical_plan.treatment_name,
            medical_destination_city=medical_plan.clinic_location.split(",")[0].strip(),
            medical_destination_country=medical_plan.clinic_location.split(",")[-1].strip(),
            medical_stay_start_date=profile.get("departureDate"),
            medical_stay_end_date=flight.segments[-1].arrival_date, 
            medical_stay_end_date=TravelArrangementInput.model_validate(
                state["travel_options"]
            ).estimated_return_date, 
            num_guests_total=profile.get("accompanyingGuests", 0) + 1,
            airport_pick_up_required=True, 
            patient_accessibility_needs=profile.get("accessibilityNeeds", None)
        )

        result = logistics_planner._run(tool_input=tool_input)
        
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
            "chat_history": state.get("chat_history", []) + [AIMessage(content=json.dumps(agent_message.model_dump()))],
            "logistics_plan": result,
            "final_selected_logistics": result, 
            "last_agent_message": agent_message,
            "current_stage": "budget_planning_pending" 
        }
    except Exception as e:
        return _create_error_response(f"An error occurred while executing the local logistics plan: {e}", "local logistics")

def node_call_budget_calculator(state: AgentState) -> dict:
    """
    Node 7: (Phase two) Call the CalculateBudgetTool
    """
    logging.info("Node: Call budget calculation (node_call_budget_calculator)")
    
    # Prepare CalculateBudgetInput, which requires the entire session state.
    plan_params = {
        "medical_plan": state.get("final_selected_medical_plan"),
        "flight": state.get("final_selected_flight"),
        "accommodation": state.get("final_selected_accommodation"),
        "local_logistics": state.get("final_selected_logistics"),
        "check_in_date": state["user_profile"].get("departureDate"),
        "check_out_date": state["travel_options"].estimated_return_date, 
    }
    
    # CalculateBudgetInput expects a 'session_state' key.
    tool_input = CalculateBudgetInput(session_state={"plan_parameters": plan_params})

    try:
        result_str = budget_calculator._run(tool_input=tool_input)
        result_json = json.loads(result_str)
        
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
    
    final_plan_content = {
        "medical_plan": state.get("final_selected_medical_plan").model_dump(),
        "travel_arrangement": {
            "flight": state.get("final_selected_flight").model_dump(),
            "accommodation": state.get("final_selected_accommodation").model_dump(),
        },
        "local_logistics": state.get("final_selected_logistics").model_dump(),
        "total_budget": state.get("final_budget")
    }
    
    agent_message = AgentResponse(
        message_type="final_plan",
        content=final_plan_content
    )
    
    return {
        "chat_history": state.get("chat_history", []) + [AIMessage(content=json.dumps(agent_message.model_dump()))],
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
        "chat_history": state.get("chat_history", []) + [AIMessage(content=json.dumps(agent_message.model_dump()))],
        "last_agent_message": agent_message,
        "current_stage": "final_confirmation_pending" 
    }

def node_handle_error(state: AgentState) -> dict:
    """
    Node: Error handling.
    """
    logging.info("Node: Error handling. (node_handle_error)")
    return {"current_stage": "error_handled"} 

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
    stage = state.get("current_stage", "start")
    logging.info(f"Router: Current Stage '{stage}'")
    
    # check for error first
    if stage == "error":
        return "node_handle_error"
    if stage == "error_handled":
        return END
        
    # stage one: medical planning
    if stage == "start":
        return "node_start_planning"
    if stage == "medical_planning_pending":
        return "node_call_medical_planner"
    if stage == "medical_selection_pending":
        if state.get("selected_medical_plan_id"):
            return "node_process_medical_selection"
        else:
            return END 
            
    # stage two: travel planning
    if stage == "travel_planning_pending":
        return "node_call_travel_planner"
    if stage == "travel_selection_pending":
        if state.get("selected_flight_id") and state.get("selected_accommodation_id"):
            return "node_process_travel_selection"
        else:
            return END
            
    # stage three: logistics planning
    if stage == "logistics_planning_pending":
        return "node_call_logistics_planner"
        
    # stage four: budget calculation & finalization
    if stage == "budget_planning_pending":
        return "node_call_budget_calculator"
    if stage == "final_plan_generation_pending":
        return "node_generate_final_plan"
    if stage == "final_plan_confirmation_pending":
        if state.get("user_input", "").lower() in ["confirm", "yes", "确认"]:
            return END 
        else:
            return END
            
    return END 

# --- 5. Building and compiling graphs ---
def create_graph():
    """
    Create and compile the LangGraph workflow.
    """
    workflow = StateGraph(AgentState)

    # add nodes
    workflow.add_node("node_start_planning", node_start_planning)
    workflow.add_node("node_call_medical_planner", node_call_medical_planner)
    workflow.add_node("node_process_medical_selection", node_process_medical_selection)
    workflow.add_node("node_call_travel_planner", node_call_travel_planner)
    workflow.add_node("node_process_travel_selection", node_process_travel_selection)
    workflow.add_node("node_call_logistics_planner", node_call_logistics_planner)
    workflow.add_node("node_call_budget_calculator", node_call_budget_calculator)
    workflow.add_node("node_generate_final_plan", node_generate_final_plan)
    workflow.add_node("node_ask_final_confirmation", node_ask_final_confirmation)
    workflow.add_node("node_handle_error", node_handle_error)

    # set entry point
    workflow.set_entry_point("node_start_planning")

    # add edges
    workflow.add_edge("node_start_planning", "node_call_medical_planner")
    
    # stage one -> interrupt
    workflow.add_conditional_edges(
        "node_call_medical_planner",
        lambda s: END if s["current_stage"] == "medical_selection_pending" else "node_handle_error",
        {END: END, "node_handle_error": "node_handle_error"}
    )
    
    # (from interrupt resume) -> stage two
    workflow.add_edge("node_process_medical_selection", "node_call_travel_planner")
    
    # stage two -> interrupt
    workflow.add_conditional_edges(
        "node_call_travel_planner",
        lambda s: END if s["current_stage"] == "travel_selection_pending" else "node_handle_error",
        {END: END, "node_handle_error": "node_handle_error"}
    )
    
    # (from interrupt resume) -> stage three
    workflow.add_edge("node_process_travel_selection", "node_call_logistics_planner")
    
    # stage three -> stage four
    workflow.add_edge("node_call_logistics_planner", "node_call_budget_calculator")
    workflow.add_edge("node_call_budget_calculator", "node_generate_final_plan")
    workflow.add_edge("node_generate_final_plan", "node_ask_final_confirmation")

    # final confirmation -> END
    workflow.add_edge("node_ask_final_confirmation", END)
    
    # error handling
    workflow.add_edge("node_handle_error", END)

    # --- Compile the graph and add persistence. ---
    try:
        memory = RedisSaver.from_conn_string("redis://localhost:6379")
        logging.info("Redis checkpointer (persistent memory) connection successful.")
    except Exception as e:
        logging.warning(f"Unable to connect to Redis: {e}. The graph will not be able to persist its state! Please ensure that Redis is running.")
        memory = None

    app = workflow.compile(checkpointer=memory, interrupt_before=["*"])
    
    logging.info("The LangGraph manager has been compiled.")
    return app

app = create_graph()