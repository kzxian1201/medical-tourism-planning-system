# ai_service/src/agentic/agents/planning_agent.py
# ===================== Entrypoint =====================
from ai_service.src.agentic.utils.main_utils import setup_proto_warnings
setup_proto_warnings()

import os
import sys
import logging
import json
from typing import Optional, Any, Dict
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from ai_service.src.agentic.utils.main_utils import LoadModel
from ai_service.src.agentic.tools.medical_planning_tool import MedicalPlanningTool
from ai_service.src.agentic.tools.travel_arrangement_tool import TravelArrangementTool
from ai_service.src.agentic.tools.travel_logistics_tool import TravelLogisticsTool
from ai_service.src.agentic.tools.update_session_state_tool import UpdateSessionStateTool
from ai_service.src.agentic.tools.calculate_budget_tool import CalculateBudgetTool

# ===================== Logging =====================
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# ===================== Prompt Loader =====================
def load_prompt(prompt_path: Optional[str] = None) -> str:
    if prompt_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.normpath(os.path.join(base_dir, "../prompt/planning_agent_prompt.txt"))
    logger.info(f"Loading prompt template from: {prompt_path}")

    if not os.path.isfile(prompt_path):
        raise RuntimeError(f"Prompt file not found at {prompt_path}. Please ensure it exists.")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
    
# ===================== Departure City Consistency Check =====================
def check_departure_city_consistency(agent_output: dict, session_state: dict) -> Optional[dict]:
    """Ensure the departure city in agent_output matches session_state."""
    try:
        plan_params = session_state.get("plan_parameters", {})
        session_departure = plan_params.get("departure_city")
        output_departure = (
            agent_output.get("content", {})
            .get("travel_arrangement_response", {})
            .get("departure_city")
        )

        if session_departure and output_departure:
            if session_departure.lower().strip() != output_departure.lower().strip():
                return {
                    "message_type": "text",
                    "content": {
                        "prompt": (
                            f"⚠️ I noticed a mismatch: your profile says departure city is **{session_departure}**, "
                            f"but the plan suggests **{output_departure}**.\n"
                            "Which one should I use to continue planning?"
                        )
                    }
                }
    except Exception as e:
        logger.warning(f"Departure city consistency check failed: {e}")
    return None

# ===================== Agent Executor Factory =====================
async def get_planning_agent_executor(prompt_template_str: Optional[str] = None) -> AgentExecutor:
    if prompt_template_str is None:
        prompt_template_str = load_prompt()

    try:
        llm = LoadModel.load_llm_model()
    except Exception as e:
        logger.error(f"Failed to load LLM model: {e}", exc_info=True)
        sys.exit(1)

    tools = [
        MedicalPlanningTool(),
        TravelArrangementTool(),
        TravelLogisticsTool(),
        UpdateSessionStateTool(),
        CalculateBudgetTool(),
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=40)
    logger.info("Planning AgentExecutor created successfully.")
    return agent_executor

# ===================== Output Handlers =====================
def _handle_agent_output(agent_output: Any, session_state: Dict) -> Dict:
    """
    Normalize agent output to always return:
    {
        "message_type": str,
        "content": { "prompt": str, ... }
    }
    """
    try:
        if isinstance(agent_output, str):
            cleaned = agent_output.strip()
            if cleaned.startswith("```json") and cleaned.endswith("```"):
                cleaned = cleaned[len("```json"):-3].strip()
            try:
                parsed = json.loads(cleaned)
                agent_output = parsed if isinstance(parsed, dict) else {"message_type": "text", "content": {"prompt": parsed}}
            except json.JSONDecodeError:
                agent_output = {"message_type": "text", "content": {"prompt": cleaned}}

        if isinstance(agent_output, dict):
            city_check = check_departure_city_consistency(agent_output, session_state)
            if city_check:
                return city_check

            message_type = agent_output.get("message_type", "text")
            content = agent_output.get("content", {"prompt": ""})

            if isinstance(content, str) or content is None or not isinstance(content, dict):
                content = {"prompt": str(content or "")}

            return {"message_type": message_type, "content": content}

        # fallback
        return {"message_type": "text", "content": {"prompt": str(agent_output)}}

    except Exception as e:
        logging.error(f"Error handling agent output: {e}", exc_info=True)
        return {"message_type": "text", "content": {"prompt": "Sorry, something went wrong."}}      
