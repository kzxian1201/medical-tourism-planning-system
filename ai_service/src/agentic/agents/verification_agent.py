# ai_service/src/agentic/agents/verification_agent.py
import json
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from ..models import VerificationOutput
from ..utils.models_factory import get_gemini_planner
from ..config import AppConfig
from ..logger import logging

class VerificationAgent:
    """
    [Quality Assurance Layer]
    Task: Audit plan vs user profile.
    Pattern: Dynamic Single-step Chain.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm = get_gemini_planner()
        self._load_base_prompt()
        self.agents = {}
        for scope in ["medical", "travel", "logistics"]:
            self.agents[scope] = self._build_agent_for_scope(scope)

    def _load_base_prompt(self) -> str:
        """Helper: Load the base system prompt template for verification."""
        path = self.config.prompts.get_prompt_path("verification")
        
        if not path.exists():
            raise FileNotFoundError(f"CRITICAL: Required system prompt file missing at {path}")

        with open(path, "r", encoding="utf-8") as f:
            self.base_template = f.read()

        return self.base_template
    
    def _build_agent_for_scope(self, scope: str):
        """Internal helper functions: Generate corresponding single-step Agents for different verification scopes."""
        additional_rules = ""
        if scope == "medical":
            additional_rules = """
            🔹 SPECIAL MEDICAL CHECKS:
            1. Does the 'clinic_location' exist and match the target country?
            2. Is the estimated cost present?
            """
        elif scope == "travel":
            additional_rules = """
            🔹 SPECIAL TRAVEL CHECKS:
            1. Do flights connect Origin to Medical Destination?
            2. EXCEPTION: If cities are adjacent, empty flight list is OK.
            """
        elif scope == "logistics":
            additional_rules = """
            🔹 SPECIAL LOGISTICS CHECKS:
            1. Are local transport options provided?
            2. Do dietary recommendations match user preferences?
            """
        
        # Construct the full System Prompt
        full_system_prompt = f"{self.base_template}\n\n{additional_rules}"
        
        # Return the compiled Agent graph
        return create_agent(
            model=self.llm,
            tools=[],
            system_prompt=full_system_prompt,
            response_format=ProviderStrategy(
                schema=VerificationOutput
            )
        )

    async def verify_plan(self, user_profile: dict, plan_data: dict, scope: str = "travel") -> VerificationOutput:
        """
        Verification logic: The pre-compiled Agent is directly extracted from the memory dictionary for execution, which greatly improves the speed.
        """
        # fallback checks to prevent input into unknown scopes
        if scope not in self.agents:
            logging.error(f"Unknown verification scope: {scope}. Falling back to 'travel'.")
            scope = "travel"
            
        agent = self.agents[scope]

        try:
            # Construct user input content
            input_content = f"""
            Please verify this plan.
            
            User Profile: {json.dumps(user_profile, indent=2)}
            Plan Data: {json.dumps(plan_data, indent=2)}
            """
            
            result = await agent.ainvoke({
                "messages": [{"role": "user", "content": input_content}]
            })
            
            # Extract structured output
            return result["structured_response"]

        except Exception as e:
            logging.error(f"Verification Agent Failed for scope '{scope}': {e}")
            return VerificationOutput(is_valid=False, feedback=f"System Error: {str(e)}")