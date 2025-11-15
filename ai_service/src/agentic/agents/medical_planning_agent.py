# ai_service/src/agentic/agents/medical_planning_agent.py
import sys
import json
import asyncio
import os
import re
from typing import Type, Optional, Dict, Any, List
from pathlib import Path
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import PrivateAttr, ValidationError
from ..logger import logging
from ..exception import CustomException
from ..utils.main_utils import LoadModel
from ..models import (MedicalPlanningInput, MedicalPlanningOutput, MedicalPlanningLLMOutput, MedicalPlanOption)
from ..tools.medical_db_search_tool import MedicalDBSearchTool
from ..tools.medical_cost_estimator_tool import MedicalCostEstimatorTool
from ..tools.check_visa_requirements_tool import VisaRequirementsCheckerTool
from ..tools.web_research_tool import WebResearchTool

try:
    prompt_file_path = Path(__file__).parent.parent / "prompt" / "medical_planning_prompt.txt"
    with open(prompt_file_path, 'r', encoding='utf-8') as f:
        MEDICAL_PLANNING_PROMPT_TEMPLATE = f.read()
except FileNotFoundError as e:
    raise RuntimeError(f"Failed to load prompt file: {prompt_file_path}") from e

class MedicalPlanningAgent(BaseTool):
    """
    A high-level agent for comprehensive medical planning. It orchestrates
    lower-level tools and uses an internal LLM to synthesize findings into structured medical plan options.
    This version simplifies the orchestration logic to delegate all synthesis to the LLM.
    """
    name: str = "medical_planning"
    description: str = (
        """Useful for generating comprehensive medical travel plans, including treatment options,
        estimated costs, recommended clinics, and visa requirements.
        Input MUST be a JSON object conforming to MedicalPlanningInput schema,
        including 'medical_purpose', 'patient_nationality', 'destination_country', and other optional details.
        Example: '{"medical_purpose": "knee replacement", "patient_nationality": "Malaysian Citizen", "destination_country": "Singapore", "estimated_budget_usd": "$15000 - $25000"}'
        The agent returns a JSON object conforming to MedicalPlanningOutput schema,
        containing a list of structured medical plan options."""
    )
    args_schema: Type[MedicalPlanningInput] = MedicalPlanningInput

    _llm: Optional[Any] = PrivateAttr()
    _medical_db_search_tool: Optional[MedicalDBSearchTool] = PrivateAttr()
    _medical_cost_estimator_tool: Optional[MedicalCostEstimatorTool] = PrivateAttr()
    _visa_requirements_checker_tool: Optional[VisaRequirementsCheckerTool] = PrivateAttr()
    _web_research_tool: Optional[WebResearchTool] = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self._llm = kwargs.get("_llm_tool") or LoadModel.load_llm_model()
            self._medical_db_search_tool = kwargs.get("_medical_db_search_tool") or MedicalDBSearchTool()
            self._medical_cost_estimator_tool = kwargs.get("_medical_cost_estimator_tool") or MedicalCostEstimatorTool(
                db_searcher=self._medical_db_search_tool
            )
            self._visa_requirements_checker_tool = kwargs.get("_visa_requirements_checker_tool") or VisaRequirementsCheckerTool(
                visa_rules_file_path=os.path.join(
                    os.path.dirname(__file__), '..', '..', 'data', 'visa_rules.json'
                )
            )
            self._web_research_tool = kwargs.get("_web_research_tool") or WebResearchTool()

            logging.info("MedicalPlanningAgent initialized with internal LLM and sub-tools.")
        except Exception as e:
            logging.error("Failed to initialize MedicalPlanningAgent's internal components", exc_info=True)
            raise CustomException(sys, e)

    async def _invoke_subtool_safe(self, tool: BaseTool, **kwargs) -> Dict[str, Any]:
        """
        Safely invokes a sub-tool by passing **kwargs.
        """
        try:
            logging.info(f"Calling sub-tool: {tool.name} with kwargs.")
            output = await tool._arun(**kwargs)

            # --- Normalization ---
            if hasattr(output, "model_dump") and callable(output.model_dump):
                return output.model_dump()
            if isinstance(output, dict):
                return output
            if isinstance(output, str):
                try:
                    return json.loads(output)
                except Exception:
                    return {"error": f"Tool {tool.name} returned non-JSON string", "raw": output}
            if hasattr(output, "dict") and callable(output.dict):
                return output.dict()
            if hasattr(output, "json") and callable(output.json):
                try:
                    return json.loads(output.json())
                except Exception:
                    pass
            return {"error": f"Tool {tool.name} returned unsupported type: {type(output).__name__}"}
        except Exception as e:
            logging.error(f"Error invoking sub-tool {tool.name}: {str(e)}", exc_info=True)
            return {"error": f"Failed to execute tool: {tool.name}. Details: {str(e)}"}
    
    def _extract_visa_info(self, visa_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return a dict suitable for MedicalPlanningOutput.visa_information field.
        Accepts various shapes and degrades gracefully.
        """
        if not isinstance(visa_results, dict):
            return {}

        vi = visa_results.get("visa_info")
        if isinstance(vi, dict):
            return vi

        data = visa_results.get("data")
        if isinstance(data, dict) and isinstance(data.get("visa_info"), dict):
            return data["visa_info"]

        possible_keys = ["visa_required", "visa_type", "stay_duration_notes",
                        "required_documents", "processing_time_days", "notes"]
        if any(k in visa_results for k in possible_keys):
            return {k: visa_results.get(k) for k in possible_keys if k in visa_results}

        return {}
    
    @staticmethod
    def sanitize_llm_output(raw_output: str) -> List[Dict[str, Any]]:
        """
        Ensure LLM output is a valid JSON array, replacing Python-style items.
        """
        try:
            return json.loads(raw_output)
        except Exception:
            fixed = (
                raw_output.replace("None", "null")
                        .replace("'", '"')
            )
            fixed = re.sub(r'MedicalPlanOption\((.*?)\)', r'{\1}', fixed)
            return json.loads(fixed)
    
    async def _arun(self, **kwargs: Any) -> MedicalPlanningOutput:
        """
        Generate structured medical plan options using sub-tools and internal LLM.
        """
        try:
            tool_input = self.args_schema(**kwargs)
        except ValidationError as e:
            logging.error(f"Input validation failed for MedicalPlanningAgent: {e}", exc_info=True)
            return MedicalPlanningOutput(message="Input validation failed", error=str(e))

        medical_purpose = tool_input.medical_purpose
        patient_nationality = tool_input.patient_nationality
        destination_country = tool_input.destination_country
        estimated_budget_usd = tool_input.estimated_budget_usd
        
        logging.info(f"Starting medical planning for '{medical_purpose}' in '{destination_country}'")

        # --- Step 1: Gather ALL raw data concurrently ---
        treatment_task = self._invoke_subtool_safe(
            self._medical_db_search_tool, type="treatment", name=medical_purpose
        )
        hospital_task = self._invoke_subtool_safe(
            self._medical_db_search_tool, type="hospital", location=destination_country, specialty=medical_purpose
        )
        cost_task = self._invoke_subtool_safe(
            self._medical_cost_estimator_tool, procedure_name=medical_purpose, location=destination_country
        )
        visa_task = self._invoke_subtool_safe(
            self._visa_requirements_checker_tool,
            nationality=patient_nationality,
            destination_country=destination_country,
            purpose="medical"
        )
        web_task = self._invoke_subtool_safe(
            self._web_research_tool,
            query=f"medical travel {medical_purpose} {destination_country} patient reviews costs"
        )

        all_results_list = await asyncio.gather(treatment_task, hospital_task, cost_task, visa_task, web_task)
        treatment_results, hospital_results, cost_results, visa_results, web_results = all_results_list

        all_results_dict = {
            "treatment_results": treatment_results,
            "hospital_results": hospital_results,
            "cost_estimation_results": cost_results,
            "visa_check_results": visa_results,
            "web_search_results": web_results
        }
        
        # --- Step 2: Synthesize a simplified plan with LLM  ---
        structured_llm = self._llm.with_structured_output(MedicalPlanningLLMOutput) 

        structured_llm_chain = (
            ChatPromptTemplate.from_template(MEDICAL_PLANNING_PROMPT_TEMPLATE) 
            | structured_llm
        )

        llm_input = {
            "medical_purpose": medical_purpose,
            "patient_nationality": patient_nationality,
            "destination_country": destination_country,
            "estimated_budget_usd": estimated_budget_usd,
            "all_results": json.dumps(all_results_dict, ensure_ascii=False),
            "errors": "No errors in previous attempts."
        }
        
        logging.info(f"--- DEBUG: LLM INPUT ---")
        logging.info(json.dumps(llm_input, indent=2, ensure_ascii=False))

        llm_output: Optional[MedicalPlanningLLMOutput] = None
        try:
            llm_output = await structured_llm_chain.ainvoke(llm_input) 
        except Exception as e:
            logging.error(f"LLM synthesis failed: {e}", exc_info=True)
            llm_output = None 

        # get the list of MedicalPlanOption from the LLM output
        generated_options_list: Optional[List[MedicalPlanOption]] = []
        if llm_output:
            generated_options_list = llm_output.medical_plan_options

        # Check if LLM failed or returned an empty list
        if not generated_options_list:
            logging.warning("LLM returned None or empty list. Attempting fallback.")
            
            # --- Fallback Logic ---
            if isinstance(web_results, dict) and web_results.get("organic_results"):
                logging.info("Falling back to web research results...")
                generated_options_list = [
                    MedicalPlanOption(
                        id="MP_OPT_FALLBACK_001", 
                        treatment_name="Web Researched Option",
                        estimated_cost_usd="Unknown",
                        clinic_name=web_results["organic_results"][0].get("title", "Unknown"), 
                        clinic_location=destination_country, 
                        brief_description=web_results["organic_results"][0].get("snippet", ""),
                        image_url=None,
                    )
                ]
            else:
                generated_options_list = [] # Ensure it's an empty list if fallback also fails

        # --- Step 3: Populate full details ---
        final_options_list = []
        raw_hospital_details = hospital_results.get("hospital_results", [])
        raw_treatment_details = treatment_results.get("treatment_results", [])

        hospitals_by_name = {h.get("name"): h for h in raw_hospital_details if isinstance(h, dict)}
        treatments_by_name = {t.get("name"): t for t in raw_treatment_details if isinstance(t, dict)}

        for opt_model in generated_options_list:
            opt_model.full_hospital_details = hospitals_by_name.get(opt_model.clinic_name) or {}
            opt_model.full_treatment_details = treatments_by_name.get(opt_model.treatment_name) or {}
            final_options_list.append(opt_model)

        # --- Step 4: Manually construct the final output object ---
        subtool_errors = []
        for res in [treatment_results, hospital_results, cost_results, visa_results, web_results]:
            if "error" in res and res["error"]:
                subtool_errors.append(res["error"])
        error_message = "; ".join(subtool_errors) if subtool_errors else None
        
        final_message = "Medical planning completed successfully."
        if not final_options_list:
            final_message = "LLM synthesis failed, no data available."

        return MedicalPlanningOutput(
            medical_plan_options=final_options_list,
            message=final_message,
            error=error_message,
            visa_information=self._extract_visa_info(visa_results)
        )
    
    def _run(self, **kwargs: Any) -> Any:
        """Synchronous run method (not recommended for this async-first tool)."""
        raise NotImplementedError("This tool is async-first. Please use .ainvoke() or await ._arun()")