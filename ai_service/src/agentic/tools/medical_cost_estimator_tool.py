# ai_service/src/agentic/tools/medical_cost_estimator_tool.py
from typing import Type, Any
from ..logger import logging 
from ..models import (MedicalCostEstimatorInput, MedicalCostEstimatorOutput, MedicalCost,MedicalDBSearchInput, MedicalDBSearchOutput, TreatmentDetails)
from .medical_db_search_tool import MedicalDBSearchTool
from langchain_core.tools import BaseTool
from pydantic import ValidationError, PrivateAttr

class MedicalCostEstimatorTool(BaseTool):
    """
    A tool to estimate the cost of various medical procedures by querying 
    the local medical database through a MedicalDBSearchTool instance.
    """
    name: str = "medical_cost_estimator"
    description: str = (
        """Useful for estimating the cost of medical procedures by querying the database.
        Input MUST be a JSON object conforming to MedicalCostEstimatorInput schema with a 'procedure_name' key and optional 'location'.
        Example: {"procedure_name": "Dental Implants", "location": "Kuala Lumpur"}
        The tool will return a JSON object conforming to MedicalCostEstimatorOutput schema with the estimated cost information."""
    )
    args_schema: Type[MedicalCostEstimatorInput] = MedicalCostEstimatorInput

    _db_searcher: MedicalDBSearchTool = PrivateAttr()

    def __init__(self, db_searcher: MedicalDBSearchTool, **kwargs):
        super().__init__(**kwargs)
        if not isinstance(db_searcher, MedicalDBSearchTool):
            logging.error("MedicalCostEstimatorTool requires an instance of MedicalDBSearchTool.")
            raise TypeError("db_searcher must be an instance of MedicalDBSearchTool.")
        
        self._db_searcher = db_searcher
        logging.info("MedicalCostEstimatorTool initialized with MedicalDBSearchTool instance.")

    async def _arun(self, **kwargs: Any) -> MedicalCostEstimatorOutput:
        """
        Asynchronously estimates the cost for a medical procedure by querying the database.
        """
        try:
            tool_input = self.args_schema(**kwargs)
        except ValidationError as e:
            logging.error(f"Input validation failed for MedicalCostEstimatorTool: {e}", exc_info=True)
            return MedicalCostEstimatorOutput(
                cost_estimation=MedicalCost(procedure_name="N/A", estimated_cost_range_usd="N/A", notes=f"Input validation failed: {e}"),
                error=f"Input validation failed: {e}"
            )
        
        procedure_name = tool_input.procedure_name
        location = tool_input.location
        
        logging.info(f"Executing cost estimation for procedure: '{procedure_name}', location: '{location}'.")

        try:
            if not procedure_name:
                return MedicalCostEstimatorOutput(
                    cost_estimation=MedicalCost(
                        procedure_name="N/A", 
                        estimated_cost_range_usd="N/A", 
                        notes="Please provide a 'procedure_name' to estimate cost."
                    ), 
                    error="Missing 'procedure_name'."
                )
            
            db_search_results: MedicalDBSearchOutput = await self._db_searcher._arun(
                type="treatment", name=procedure_name
            )

            cost_result_data = {
                "procedure_name": procedure_name,
                "estimated_cost_range_usd": "N/A", 
                "notes": "Cost information not found in the database for the exact procedure.",
                "associated_specialties": []
            }

            if db_search_results.treatment_results:
                found_exact_match_cost = False
                for t_model in db_search_results.treatment_results:
                    if isinstance(t_model, TreatmentDetails): 
                        if t_model.name.lower() == procedure_name.lower():
                            if t_model.estimated_market_cost_range_usd_min is not None or t_model.estimated_market_cost_range_usd_max is not None:
                                if t_model.estimated_market_cost_range_usd_min is not None and t_model.estimated_market_cost_range_usd_max is not None:
                                    cost_result_data["estimated_cost_range_usd"] = f"${t_model.estimated_market_cost_range_usd_min:.0f} - ${t_model.estimated_market_cost_range_usd_max:.0f}"
                                elif t_model.estimated_market_cost_range_usd_min is not None:
                                    cost_result_data["estimated_cost_range_usd"] = f"${t_model.estimated_market_cost_range_usd_min:.0f}"
                                else:
                                    cost_result_data["estimated_cost_range_usd"] = "N/A"
                                
                                cost_result_data["notes"] = f"Based on '{t_model.name}' from database."
                            else: 
                                cost_result_data["estimated_cost_range_usd"] = "N/A"
                                cost_result_data["notes"] = f"No specific cost information available for '{t_model.name}'."
                            
                            cost_result_data["associated_specialties"] = t_model.associated_specialties
                            found_exact_match_cost = True
                            break
                
                # Fallback to first result if no exact name match, but still has cost info
                if not found_exact_match_cost and db_search_results.treatment_results:
                    first_treatment = db_search_results.treatment_results[0]
                    if isinstance(first_treatment, TreatmentDetails):
                        if first_treatment.estimated_market_cost_range_usd_min is not None or first_treatment.estimated_market_cost_range_usd_max is not None:
                            if first_treatment.estimated_market_cost_range_usd_min is not None and first_treatment.estimated_market_cost_range_usd_max is not None:
                                cost_result_data["estimated_cost_range_usd"] = f"${first_treatment.estimated_market_cost_range_usd_min:.0f} - ${first_treatment.estimated_market_cost_range_usd_max:.0f}"
                            elif first_treatment.estimated_market_cost_range_usd_min is not None:
                                cost_result_data["estimated_cost_range_usd"] = f"${first_treatment.estimated_market_cost_range_usd_min:.0f}"
                            else:
                                cost_result_data["estimated_cost_range_usd"] = "N/A"
                            
                            cost_result_data["notes"] = f"Closest match found: '{first_treatment.name}'. Cost is an estimate."
                        else: 
                            cost_result_data["estimated_cost_range_usd"] = "N/A"
                            cost_result_data["notes"] = f"Closest match found: '{first_treatment.name}'. No specific cost information available."
                        
                        cost_result_data["associated_specialties"] = first_treatment.associated_specialties
            
            cost_estimation = MedicalCost(**cost_result_data)
            return MedicalCostEstimatorOutput(cost_estimation=cost_estimation)

        except ValidationError as ve:
            logging.error(f"MedicalCostEstimatorTool: Pydantic validation error: {ve}", exc_info=True)
            return MedicalCostEstimatorOutput(
                cost_estimation=MedicalCost(
                    procedure_name=procedure_name, 
                    estimated_cost_range_usd="N/A", 
                    notes=f"Data validation failed: {ve}"
                ), 
                error=f"Pydantic validation error: {ve}"
            )
        except Exception as e:
            logging.error(f"An error occurred during medical_cost_estimator execution: {e}", exc_info=True)
            return MedicalCostEstimatorOutput(
                cost_estimation=MedicalCost(
                    procedure_name=procedure_name, 
                    estimated_cost_range_usd="N/A", 
                    notes=f"An internal error occurred: {e}"
                ), 
                error=f"An internal error occurred: {str(e)}"
            )
        
    def _run(self, **kwargs: Any) -> Any:
        """Synchronous run method (not recommended for this async-first tool)."""
        raise NotImplementedError("This tool is async-first. Please use .ainvoke() or await ._arun()")