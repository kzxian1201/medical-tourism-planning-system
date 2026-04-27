# ai_service/src/agentic/agents/travel_logistics_agent.py
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.agents.middleware import ModelCallLimitMiddleware, SummarizationMiddleware
from ..config import AppConfig
from ..tools.web_research_tool import create_web_research_tool
from ..tools.medical_knowledge_base_tool import medical_knowledge_base
from ..tools.insurance_quote_tool import create_insurance_quote_tool
from ..tools.update_profile_tool import create_update_profile_tool
from ..models import TravelLogisticsOutput
from ..utils.models_factory import get_gemini_planner

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

def create_logistics_agent(config: AppConfig):
    """
    Factory: Creates the Logistics Department Agent.
    """
    tools = [
        create_web_research_tool(config),
        medical_knowledge_base,
        create_insurance_quote_tool(config),
        create_update_profile_tool(config)
    ]

    system_prompt_text = load_prompt_content(config, "travel_logistics")
    system_prompt_text += "\nIf the user mentions any new dietary or accessibility needs, USE the `update_user_preferences` tool."

    agent = create_agent(
        model=get_gemini_planner(),
        tools=tools,
        system_prompt=system_prompt_text,
        response_format=ProviderStrategy(
            schema=TravelLogisticsOutput
        ),
        middleware=[
            ModelCallLimitMiddleware(
                run_limit=10,
                thread_limit=50,
                exit_behavior="end",
            ),
            SummarizationMiddleware(
                model=get_gemini_planner(),
                trigger=("tokens", 10000),
                keep=("messages", 20),
            )
        ]
    )
    
    return agent