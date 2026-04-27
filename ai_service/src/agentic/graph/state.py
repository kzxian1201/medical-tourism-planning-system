# ai_service/src/agentic/graph/state.py
from typing import Annotated, List, Optional, Dict, Any
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from ..models import UserProfile, MedicalPlanOption, TravelArrangementOutput, TravelLogisticsOutput, FlightOptionSummary, AccommodationOption, FinalProposal
from operator import add

def merge_user_profile(old_profile: Optional[UserProfile], new_profile_updates: Any) -> Optional[UserProfile]:
    """
    When new user preferences are passed in, they are merged into the existing user_profile.
    """
    # If there were no previous portraits, simply treat the new ones as the entirety.
    if not old_profile:
        return new_profile_updates if isinstance(new_profile_updates, UserProfile) else old_profile
        
    # If there were no new updates passed in, keep the original profile.
    if not new_profile_updates:
        return old_profile
        
    if isinstance(old_profile, dict):
        merged_data = old_profile.copy()
    else:
        merged_data = old_profile.model_dump()
    
    # assume that the updates we pass in is also a dictionary (or an object with preferences).
    if isinstance(new_profile_updates, dict):
        updates = new_profile_updates
    else:
        updates = new_profile_updates.model_dump(exclude_unset=True)

    # Merging logic: Append the newly extracted dietary_needs
    if "preferences" in updates:
        new_prefs = updates["preferences"]
        old_prefs = merged_data.get("preferences", {})
        
        if "dietary_needs" in new_prefs:
            combined = old_prefs.get("dietary_needs", []) + new_prefs["dietary_needs"]
            old_prefs["dietary_needs"] = list(set(combined))
            
        if "accessibility_needs" in new_prefs:
            combined = old_prefs.get("accessibility_needs", []) + new_prefs["accessibility_needs"]
            old_prefs["accessibility_needs"] = list(set(combined))
            
        merged_data["preferences"] = old_prefs

    return UserProfile(**merged_data)

class AgentState(TypedDict):
    """
    [Global Context] - LangChain 1.0+ Standard TypedDict State.
    """
    # Session & User
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    
    # Binding Reducer
    user_profile: Annotated[Optional[UserProfile], merge_user_profile]
    
    # Curation Queue
    data_update_queue: Annotated[List[Dict[str, Any]], add]

    # Department Outputs
    medical_plan_options: List[MedicalPlanOption]
    final_selected_medical_plan: Optional[MedicalPlanOption]
    
    travel_options: Optional[TravelArrangementOutput]
    final_selected_flight: Optional[FlightOptionSummary]
    final_selected_accommodation: Optional[AccommodationOption]

    weather_info: Optional[Any]
    
    logistics_plan: Optional[TravelLogisticsOutput]
    
    # Final Result
    final_proposal: Optional[FinalProposal]
    
    # Control Flow & Error Handling
    current_stage: str
    error_message: Optional[str]
    status: str # "active", "blocked", "completed", "error"

class GraphConfig(TypedDict):
    """
    [Runtime Configuration]
    These parameters can be passed at runtime via `configurable`.
    """
    user_id: str
    thread_id: str
    llm_model_name: str
    max_retries: int
    require_human_approval: bool