# ai_service/src/agentic/agents/medical_planning_agent.py
from ..config import AppConfig
from ..utils.models_factory import get_gemini_planner
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.agents.middleware import ModelCallLimitMiddleware, SummarizationMiddleware
from ..tools.medical_knowledge_base_tool import medical_knowledge_base
from ..tools.update_profile_tool import create_update_profile_tool
from ..models import MedicalPlanningOutput

class PromptNotFoundError(Exception):
    """Custom exception for missing mission-critical prompt files."""
    pass

def load_prompt_content(config: AppConfig, agent_name: str) -> str:
    """Helper: Load raw prompt text from file based on experiment config."""
    path = config.prompts.get_prompt_path(agent_name)
    if not path.exists():
        raise PromptNotFoundError(f"CRITICAL: Required system prompt file missing at {path}")
        
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def create_medical_agent(config: AppConfig):
    """
    Factory: Creates the Medical Planning Department Agent.
    Refactored for LangChain 1.0+.
    """
    # init Tools
    tools = [medical_knowledge_base, create_update_profile_tool(config)]

    # load Prompt
    system_prompt_text = load_prompt_content(config, "medical_planning")
    system_prompt_text += """
    IMPORTANT: You MUST convert the raw data from `medical_knowledge_base` into the `full_hospital_details` object.
    Specifically, look for 'medical_professionalism' and 'international_patient_services' in the tool output and nest them inside `full_hospital_details`. 
    NEVER return an empty object {} if the hospital info is found.
    If the user mentions any dietary or accessibility needs, USE the `update_user_preferences` tool.
    """

    # create Agent
    llm = get_gemini_planner()
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt_text,
        response_format=ProviderStrategy(
            schema=MedicalPlanningOutput
        ),
        middleware=[
            ModelCallLimitMiddleware(
                run_limit=10,
                thread_limit=50,
                exit_behavior="end",
            ),
            SummarizationMiddleware(
                model=llm,
                trigger=("tokens", 10000),
                keep=("messages", 20),
            )
        ]
    )
    
    return agent