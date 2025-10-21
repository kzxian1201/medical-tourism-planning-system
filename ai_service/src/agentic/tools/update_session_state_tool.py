# ai_service/src/agentic/tools/update_session_state_tool.py
import logging
from typing import Type, Any, Dict
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from ai_service.src.agentic.models import UpdateSessionStateInput

# Configure logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

class UpdateSessionStateTool(BaseTool):
    """
    A tool to save a user's selected option into the session state.
    """
    name: str = "update_session_state_tool"
    description: str = "Use this tool to update the session state with a user's selected plan or option. This tool is CRITICAL for saving choices from `summary_cards`."
    args_schema: Type[BaseModel] = UpdateSessionStateInput

    def _run(self, **kwargs: Any) -> Dict[str, Any]:
        """
        The synchronous run method. It accepts the full session state as an argument
        and returns the modified state.
        """
        logger.info(f"UpdateSessionStateTool called with kwargs: {kwargs}")

        # Extract session_state from kwargs; default to an empty dict if not present
        session_state = kwargs.pop("session_state", {})

        # The remaining kwargs should match the args_schema
        tool_input = self.args_schema(**kwargs)
        
        logger.info(f"UpdateSessionStateTool processed with type: '{tool_input.type}' and id: '{tool_input.id}'.")

        new_session_state = session_state.copy()
        if "plan_parameters" not in new_session_state:
            new_session_state["plan_parameters"] = {}
        if "user_profile" not in new_session_state:
            new_session_state["user_profile"] = {}
        
        # Now, your existing logic can proceed as intended
        if tool_input.type in new_session_state["plan_parameters"]:
            new_session_state["plan_parameters"][tool_input.type] = {"id": tool_input.id}
        elif tool_input.type in new_session_state["user_profile"]:
            new_session_state["user_profile"][tool_input.type] = tool_input.id
        else:
            new_session_state[tool_input.type] = tool_input.id

        logger.info(f"Session state updated: {new_session_state}")

        return new_session_state
    
    async def _arun(self, **kwargs: Any) -> str:
        """Asynchronous run method."""
        return self._run(**kwargs)