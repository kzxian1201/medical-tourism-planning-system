# ai_service/src/agentic/graph/subgraphs/logistics_subgraph.py
import logging
from typing import Any, List
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from ai_service.src.agentic.graph.state import AgentState
from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.agents.travel_logistics_agent import create_logistics_agent
from ai_service.src.agentic.tools.update_profile_tool import profile_updates_ctx

def _safe_dump(obj: Any) -> Any:
    """Securely extract the representation of objects or dictionaries."""
    if not obj:
        return "None"
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)

def _extract_hospital_name(medical_plan: Any) -> str:
    """Safe extraction of hospital name"""
    if not medical_plan:
        return "Unknown"
    if isinstance(medical_plan, dict):
        return medical_plan.get("clinic_name", "Unknown")
    return getattr(medical_plan, "clinic_name", "Unknown")

def _extract_accessibility(user_profile: Any) -> List[str]:
    """Safe extraction of accessibility needs"""
    if not user_profile:
        return []
    if isinstance(user_profile, dict):
        prefs = user_profile.get("preferences", {})
        if isinstance(prefs, dict):
            return prefs.get("accessibility_needs", [])
        return []
    if hasattr(user_profile, "preferences"):
        return getattr(user_profile.preferences, "accessibility_needs", [])
    return []

def create_logistics_subgraph(config: AppConfig):
    """[Factory] Creates the Logistics Subgraph."""
    logistics_agent = create_logistics_agent(config)

    async def node_logistics_plan(state: AgentState):
        """Node Logic: Plans local logistics based on the final medical plan, user profile, and weather context."""
        logging.info("🚕 Planning Logistics...")
        
        safe_flight = _safe_dump(state.get("final_selected_flight"))
        safe_hotel = _safe_dump(state.get("final_selected_accommodation"))
        hospital_name = _extract_hospital_name(state.get("final_selected_medical_plan"))
        accessibility_needs = _extract_accessibility(state.get("user_profile"))
        weather_context = state.get("weather_info", "Weather unknown.")

        travel_context = f"Flight: {safe_flight}\nHotel: {safe_hotel}\nHospital: {hospital_name}"

        # Construct the weather-aware Prompt
        prompt_content = f"""
        Plan local logistics based on this itinerary:
        
        [TRAVEL CONTEXT]
        {travel_context}
        
        [CRITICAL WEATHER FORECAST]
        {weather_context}
        
        =========================================================
        [SINGLE SOURCE OF TRUTH: SPECIAL NEEDS]
        Accessibility & Dietary: {accessibility_needs}
        
        ⚠️ CRITICAL INSTRUCTION: The needs listed above are the absolute Single Source of Truth derived from the latest user profile. 
        You MUST adhere to these accessibility and dietary needs strictly. Do NOT make assumptions outside of these parameters.
        =========================================================
        
        *** ACTION REQUIRED ***: If the forecast shows RAIN, explicitly recommend indoor malls (like Gurney Paragon) and door-to-door transport (GrabAssist) to prevent slipping hazards for wheelchair/post-op users.
        """
        
        agent_input = {"messages": [HumanMessage(content=prompt_content)]}

        # Context of mounted image update
        current_profile_updates = {}
        token = profile_updates_ctx.set(current_profile_updates)
        
        try:
            response = await logistics_agent.ainvoke(agent_input)
            logistics_output = response.get("structured_response")
            
            result_payload = {"logistics_plan": logistics_output}
            
            # If a new profile is captured during settlement, it is sent back to the State's Reducer
            if current_profile_updates:
                existing_profile = state.get("user_profile", {})
                p_dict = existing_profile.model_dump() if hasattr(existing_profile, "model_dump") else dict(existing_profile)
                
                if "preferences" not in p_dict:
                    p_dict["preferences"] = {}
                p_dict["preferences"].update(current_profile_updates)
                
                result_payload["user_profile"] = p_dict
                
            return result_payload
            
        except Exception as e:
            logging.error(f"Logistics Agent Failed: {e}", exc_info=True)
            return {"error_message": f"Logistics failed: {str(e)}"}
        finally:
            # Cleanup Context
            profile_updates_ctx.reset(token)

    # Compile Graph
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", node_logistics_plan)
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", END)
    
    return workflow.compile()