# ai_service/src/agentic/graph/state.py
from typing import List, Dict, Any
from typing_extensions import TypedDict, NotRequired
from langchain_core.messages import BaseMessage
from ..models import (MedicalPlanOption, TravelArrangementOutput, TravelLogisticsOutput, FlightOptionSummary, AccommodationOption, AgentResponse)

class AgentState(TypedDict):
    """
    Defines the central state (or "context") of agent.
    This dictionary will be passed, checked, and updated at each step of the graph.
    This follows the core idea of ​​Thinking in LangGraph.
    """ 
    # --- 1. Session and user input ---
    chat_history: NotRequired[List[BaseMessage]]
    user_input: NotRequired[str]
    user_profile: NotRequired[Dict[str, Any]]

    # --- 2. Phased outputs ---
    medical_plan_options: NotRequired[List[MedicalPlanOption]]
    travel_options: NotRequired[TravelArrangementOutput]
    logistics_plan: NotRequired[TravelLogisticsOutput]
    final_budget: NotRequired[Dict[str, Any]]

    # --- 3. The user's final choice ---
    selected_medical_plan_id: NotRequired[str]
    selected_flight_id: NotRequired[str]
    selected_accommodation_id: NotRequired[str]

    # --- 4. finalize the plan ---
    final_selected_medical_plan: NotRequired[MedicalPlanOption]
    final_selected_flight: NotRequired[FlightOptionSummary]
    final_selected_accommodation: NotRequired[AccommodationOption]

    # --- 5. Process control and output ---
    current_stage: NotRequired[str]
    last_agent_message: NotRequired[AgentResponse]
    error_message: NotRequired[str]