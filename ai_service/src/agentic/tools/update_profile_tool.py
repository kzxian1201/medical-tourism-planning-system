# ai_service/src/agentic/tools/update_profile_tool.py
import contextvars
from typing import List, Optional
from langchain_core.tools import tool
from ..logger import logging
from ..config import AppConfig
from ..models import UpdateProfileInput

# Define thread-safe/asynchronous-safe context variables
profile_updates_ctx = contextvars.ContextVar("profile_updates", default=None)

def create_update_profile_tool(config: AppConfig):
    @tool("update_user_preferences", args_schema=UpdateProfileInput)
    def update_user_preferences(
        dietary_needs: Optional[List[str]] = None,
        accessibility_needs: Optional[List[str]] = None,
        medical_allergies: Optional[List[str]] = None,
        preferred_language: Optional[str] = None,
        travel_class_preference: Optional[str] = None
    ) -> str:
        """Use this to extract and save new user preferences, allergies, or travel habits permanently."""
        
        logging.info(f"🧠 Updating User Profile [Env: {config.environment}]...")
        
        state_dict = profile_updates_ctx.get()
        if state_dict is not None:
            if dietary_needs: state_dict["dietary_needs"] = dietary_needs
            if accessibility_needs: state_dict["accessibility_needs"] = accessibility_needs
            if medical_allergies: state_dict["medical_allergies"] = medical_allergies
            if preferred_language: state_dict["preferred_language"] = preferred_language
            if travel_class_preference: state_dict["travel_class_preference"] = travel_class_preference
            
            logging.info(f"   ↳ Captured updates: {list(state_dict.keys())}")
                
        return "Preferences and medical constraints noted. The system memory will be updated for all departments."
        
    return update_user_preferences