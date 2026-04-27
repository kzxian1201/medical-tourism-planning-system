# ai_service/src/agentic/agents/travel_arrangement_agent.py
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.agents.middleware import ModelCallLimitMiddleware, SummarizationMiddleware
from ..config import AppConfig
from ..tools.search_flights_tool import create_search_flights_tool
from ..tools.city_to_iata_code_tool import create_city_to_iata_code_tool
from ..tools.get_weather_data_tool import create_get_weather_data_tool
from ..tools.medical_knowledge_base_tool import medical_knowledge_base
from ..tools.update_visa_knowledge_tool import create_update_visa_knowledge_tool
from ..tools.web_research_tool import create_web_research_tool
from ..tools.currency_converter_tool import create_currency_converter_tool
from ..models import TravelArrangementOutput
from ..utils.models_factory import get_gemini_planner
from datetime import datetime

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

def create_travel_agent(config: AppConfig):
    """
    Factory: Creates the Travel Arrangement Department Agent.
    """
    tools = [
        create_search_flights_tool(config),
        create_city_to_iata_code_tool(config),
        create_get_weather_data_tool(config),
        medical_knowledge_base,
        create_web_research_tool(config),
        create_update_visa_knowledge_tool(config),
        create_currency_converter_tool(config)
    ]

    raw_prompt = load_prompt_content(config, "travel_arrangement")
    
    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt_text = f"Today's date is {today}. \n\n" + raw_prompt

    agent = create_agent(
        model=get_gemini_planner(),
        tools=tools,
        system_prompt=system_prompt_text,
        response_format=ProviderStrategy(
            schema=TravelArrangementOutput
        ),
        middleware=[
            ModelCallLimitMiddleware(
                run_limit=10,
                thread_limit=50,
                exit_behavior="end"
            ),
            SummarizationMiddleware(
                model=get_gemini_planner(),
                trigger=("tokens", 12000),
                keep=("messages", 20)
            )
        ]
    )
    
    return agent