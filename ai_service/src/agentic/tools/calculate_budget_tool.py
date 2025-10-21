# ai_service/src/agentic/tools/calculate_budget_tool.py
import json
import logging
from typing import Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from datetime import datetime
from ai_service.src.agentic.models import CalculateBudgetInput

# Configure logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

class CalculateBudgetTool(BaseTool):
    """
    A tool to calculate the total estimated budget for the entire medical tourism plan
    based on data stored in the session state.
    """
    name: str = "calculate_budget_tool"
    description: str = "Use this tool to calculate the total estimated budget for the plan. It requires the entire `session_state` as input to access all costs (medical, flight, accommodation, etc.)."
    args_schema: Type[BaseModel] = CalculateBudgetInput

    def _run(self, **kwargs) -> str:
        """
        Synchronous run method to calculate the total budget.
        """
        logger.info("CalculateBudgetTool called.")
        
        try:
            if "session_state" in kwargs:
                session_state = kwargs.get("session_state", {})
            elif "tool_input" in kwargs and isinstance(kwargs["tool_input"], CalculateBudgetInput):
                session_state = kwargs["tool_input"].session_state
            else:
                session_state = {}

            plan_params = session_state.get("plan_parameters", {})
            
            # Extract costs from the session state
            medical_plan = plan_params.get("medical_plan", {})
            flight_plan = plan_params.get("flight", {})
            accommodation_plan = plan_params.get("accommodation", {})
            logistics_plan = plan_params.get("local_logistics", {})
            
            # Check for local services and leisure activities
            local_services_list = logistics_plan.get('local_services', [])
            leisure_activities_list = logistics_plan.get('leisure_activities', [])

            medical_cost = medical_plan.get('estimated_cost_usd', 0)
            flight_cost = flight_plan.get('price', {}).get('amount', 0)
            accommodation_cost_per_night = accommodation_plan.get('price', {}).get('amount', 0)
            airport_pickup_cost = logistics_plan.get('airport_pickup', {}).get('price', {}).get('amount', 0)

            # Calculate total cost for local services and leisure activities
            local_services_cost = sum(item.get('price', {}).get('amount', 0) for item in local_services_list)
            leisure_activities_cost = sum(item.get('price', {}).get('amount', 0) for item in leisure_activities_list)

            # Calculate number of nights
            num_nights = 0
            check_in_date_str = plan_params.get('check_in_date')
            check_out_date_str = plan_params.get('check_out_date')
            if check_in_date_str and check_out_date_str:
                start_date = datetime.strptime(check_in_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(check_out_date_str, '%Y-%m-%d').date()
                num_nights = (end_date - start_date).days

            # Calculate total budget, now including all costs
            total_estimated_budget = (
                medical_cost + 
                flight_cost + 
                (accommodation_cost_per_night * num_nights) + 
                airport_pickup_cost +
                local_services_cost +
                leisure_activities_cost
            )
            
            # Return the result as a JSON string
            return json.dumps({
                "total_estimated_budget_usd": total_estimated_budget,
                "breakdown": {
                    "medical_cost": medical_cost,
                    "flight_cost": flight_cost,
                    "accommodation_cost": accommodation_cost_per_night * num_nights,
                    "airport_pickup_cost": airport_pickup_cost,
                    "local_services_cost": local_services_cost,
                    "leisure_activities_cost": leisure_activities_cost
                }
            })

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Budget calculation failed. Error: {e}", exc_info=True)
            return json.dumps({
                "total_estimated_budget_usd": 0,
                "error": f"Failed to calculate budget due to missing or invalid data: {str(e)}"
            })

    async def _arun(self, tool_input: CalculateBudgetInput) -> str:
        return self._run(session_state=tool_input.session_state)