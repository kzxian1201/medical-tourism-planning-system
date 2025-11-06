# ai_service/src/agentic/graph/state.py
from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from ..models import (MedicalPlanOption, TravelArrangementOutput, TravelLogisticsOutput, FlightOptionSummary, AccommodationOption, AgentResponse)

class AgentState(TypedDict):
    """
    Defines the central state (or "context") of agent.
    This dictionary will be passed, checked, and updated at each step of the graph.
    This follows the core idea of ​​Thinking in LangGraph.
    """ 
    # --- 1. Session and user input ---
    chat_history: List[BaseMessage]
    user_input: str
    user_profile: Dict[str, Any]

    # --- 2. Phased outputs ---
    medical_plan_options: Optional[List[MedicalPlanOption]]
    travel_options: Optional[TravelArrangementOutput]
    logistics_plan: Optional[TravelLogisticsOutput]
    final_budget: Optional[Dict[str, Any]]

    # --- 3. The user's final choice (used for state transition) ---
    selected_medical_plan_id: Optional[str]
    selected_flight_id: Optional[str]
    selected_accommodation_id: Optional[str]
    
    # --- 4. finalize the plan ---
    final_selected_medical_plan: Optional[MedicalPlanOption]    
    final_selected_flight: Optional[FlightOptionSummary]    
    final_selected_accommodation: Optional[AccommodationOption]
    
    # --- 5. Process control and output ---
    current_stage: str
    last_agent_message: Optional[AgentResponse]
    error_message: Optional[str]
