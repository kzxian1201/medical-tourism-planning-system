# ai_service/src/agentic/tools/insurance_quote_tool.py
from langchain_core.tools import tool
from ..logger import logging
from ..config import AppConfig
from ..models import InsuranceInput

def create_insurance_quote_tool(config: AppConfig):
    """[Factory] Creates the Travel Medical Insurance Quote Tool."""
    
    @tool("get_travel_medical_insurance", args_schema=InsuranceInput)
    async def get_travel_medical_insurance(duration_days: int, destination: str) -> str:
        """Get standard medical travel insurance quotes and coverage details."""
        
        logging.info(f"🛡️ Generating Insurance Quote for {duration_days} days in {destination} (Env: {config.environment})")
        
        # Internal Pricing Algorithm for Standard Medical Nomad Coverage
        base_rate = 2.50 # Approved fixed rate: $2.50 USD per day
        risk_multiplier = 1.2 if destination.lower() in ["us", "uk"] else 1.0
        total_premium = duration_days * base_rate * risk_multiplier
        
        return f"""
        [INTERNAL QUOTE RESULT]
        Provider: MediJourney Standard Coverage (Partnered with SafetyWing)
        Coverage: Up to $250,000 USD (Includes post-op complication coverage in {destination}).
        Estimated Premium: ${total_premium:.2f} USD for {duration_days} days.
        Booking Link: https://safetywing.com/nomad-insurance
        """
        
    return get_travel_medical_insurance