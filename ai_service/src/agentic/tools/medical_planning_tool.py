# ai_service/src/agentic/tools/medical_planning_tool.py
import sys
import json
import asyncio
import os
import re
from typing import Type, Optional, Dict, Any, List
from pathlib import Path
from .base_async_tool import BaseAsyncTool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import PrivateAttr
from ..logger import logging
from ..exception import CustomException
from ..utils.main_utils import LoadModel
from ..models import (MedicalPlanningInput, MedicalPlanningOutput, MedicalPlanOptionList, MedicalPlanOption)
from .medical_db_search_tool import MedicalDBSearchTool
from .medical_cost_estimator_tool import MedicalCostEstimatorTool
from .check_visa_requirements_tool import VisaRequirementsCheckerTool
from .web_research_tool import WebResearchTool
from langchain.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda

try:
    prompt_file_path = Path(__file__).parent.parent / "prompt" / "medical_planning_prompt.txt"
    with open(prompt_file_path, 'r', encoding='utf-8') as f:
        MEDICAL_PLANNING_PROMPT_TEMPLATE = f.read()
except FileNotFoundError as e:
    raise RuntimeError(f"Failed to load prompt file: {prompt_file_path}") from e

class MedicalPlanningTool(BaseAsyncTool):
    """
    A high-level tool for comprehensive medical planning. It orchestrates
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
        The tool returns a JSON object conforming to MedicalPlanningOutput schema,
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

            logging.info("MedicalPlanningTool initialized with internal LLM and sub-tools.")
        except Exception as e:
            logging.error("Failed to initialize MedicalPlanningTool's internal components", exc_info=True)
            raise CustomException(sys, e)

    async def _invoke_subtool_safe(self, tool: Any, **kwargs) -> Dict[str, Any]:
        """
        Safely invokes a sub-tool by correctly packaging a single Pydantic input object.
        """
        try:
            logging.info(f"Preparing input for sub-tool: {tool.name}")
            
            # Use the tool's own args_schema to create the correct input model
            tool_input_model = tool.args_schema(**kwargs)

            logging.info(f"Calling sub-tool: {tool.name} with structured input.")
            output = await tool._arun(tool_input=tool_input_model)

            # --- Normalization ---
            # 1) Pydantic model
            if hasattr(output, "model_dump") and callable(output.model_dump):
                return output.model_dump()

            # 2) dict
            if isinstance(output, dict):
                return output

            # 3) JSON string → dict
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
    
    def sanitize_llm_output(raw_output: str) -> List[Dict[str, Any]]:
        """
        Ensure LLM output is a valid JSON array, replacing Python-style items.
        """
        import json
        try:
            return json.loads(raw_output)
        except Exception:
            fixed = (
                raw_output.replace("None", "null")
                        .replace("'", '"')
            )
            fixed = re.sub(r'MedicalPlanOption\((.*?)\)', r'{\1}', fixed)
            return json.loads(fixed)

    
    async def _arun(self, tool_input: Optional[MedicalPlanningInput] = None, **kwargs) -> MedicalPlanningOutput:
        """
        Generate structured medical plan options using sub-tools and internal LLM.
        """
        if tool_input is None:
            tool_input = self.args_schema(**kwargs)

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
        parser = PydanticOutputParser(pydantic_object=MedicalPlanOptionList)

        structured_llm_chain = (
            ChatPromptTemplate.from_messages([
                ("system", MEDICAL_PLANNING_PROMPT_TEMPLATE),
                ("human", "{llm_input}")
            ])
            | RunnableLambda(self._llm.ainvoke) 
            | parser
        )

        llm_input = {
            "medical_purpose": medical_purpose,
            "patient_nationality": patient_nationality,
            "destination_country": destination_country,
            "estimated_budget_usd": estimated_budget_usd,
            "all_results": json.dumps(all_results_dict, ensure_ascii=False),
            "errors": "No errors in previous attempts."
        }
        
        # Run LLM once 
        validated_options_list: MedicalPlanOptionList = None
        try:
            validated_options_list = await structured_llm_chain.ainvoke({"llm_input": llm_input})
        except Exception as e:
            logging.error(f"LLM synthesis failed: {e}")
            validated_options_list = MedicalPlanOptionList(root=[])

        if not validated_options_list.root:
            logging.info("Falling back to web research results...")
            if web_results and "organic_results" in web_results:
                validated_options_list = MedicalPlanOptionList(root=[
                    MedicalPlanOption(
                        treatment_name="Web Researched Option",
                        estimated_cost_usd="Unknown",
                        clinic_name=web_results["organic_results"][0].get("title", "Unknown"),
                        clinic_location="Unknown",
                        brief_description=web_results["organic_results"][0].get("snippet", ""),
                        image_url=None,
                    )
                ])

        # --- Step 3: Populate full details ---
        final_options = []
        raw_hospital_details = hospital_results.get("data", [])
        raw_treatment_details = treatment_results.get("data", [])

        # fast lookup maps
        hospitals_by_name = {h.get("name"): h for h in raw_hospital_details if isinstance(h, dict)}
        treatments_by_name = {t.get("name"): t for t in raw_treatment_details if isinstance(t, dict)}

        # collect subtool errors
        subtool_errors = []
        for res in [treatment_results, hospital_results, cost_results, visa_results, web_results]:
            if "error" in res and res["error"]:
                subtool_errors.append(res["error"])

        # check each option and fill in details
        for opt in validated_options_list.root:
            # ensure the full details has correct type
            opt.full_hospital_details = hospitals_by_name.get(opt.clinic_name) or {}
            opt.full_treatment_details = treatments_by_name.get(opt.treatment_name) or {}
            final_options.append(opt.model_dump())

        # collect all subtool errors
        error_message = None
        if subtool_errors:
            error_message = "; ".join(subtool_errors)

        # --- Step 4: Return final structured output ---
        return MedicalPlanningOutput(
            medical_plan_options=final_options,
            message="Medical planning completed successfully.",
            error=error_message,
            visa_information=self._extract_visa_info(visa_results)
        )
        