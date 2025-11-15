# ai_service/src/agentic/agents/travel_logistics_agent.py
import sys
import json
import asyncio
import re
from typing import Type, List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.llms import BaseLLM
from pydantic import PrivateAttr, ValidationError
from ..logger import logging
from ..exception import CustomException
from ..utils.main_utils import LoadModel 
from ..models import (TravelLogisticsInput, TravelLogisticsOutput, WebResearchToolInput, WebSearchResult, LocalMedicalTransportInput, LocalMedicalTransportOutput, TravelLogisticsLLMOutput)
from ..tools.arrange_local_medical_transport_tool import LocalMedicalTransportTool
from ..tools.web_research_tool import WebResearchTool
from pathlib import Path

# Load prompt from file
try:
    prompt_file_path = Path(__file__).parent.parent / "prompt" / "travel_logistics_prompt.txt"
    with open(prompt_file_path, 'r', encoding='utf-8') as f:
        TRAVEL_LOGISTICS_PROMPT_TEMPLATE = f.read()
except FileNotFoundError as e:
    raise RuntimeError(f"Failed to load travel logistics prompt file: {prompt_file_path}") from e

class TravelLogisticsAgent(BaseTool):
    """
    A high-level agent for arranging local logistics for medical tourism,
    including airport pick-up, local transportation, additional local services,
    dietary needs, SIM card assistance, and leisure activities.
    It orchestrates lower-level tools and uses an internal LLM to synthesize findings.
    """
    name: str = "travel_logistics_planning"
    description: str = (
        """Useful for generating comprehensive local logistics plans for medical tourism,
        after initial travel arrangements (flights, accommodation) are made.
        It covers airport pick-up, local transportation during stay, additional local services
        (e.g., interpreter), dietary needs, SIM card assistance, and leisure activity suggestions.
        Input MUST be a JSON object conforming to TravelLogisticsInput schema.
        Example: '{"medical_destination_city": "Singapore", "medical_destination_country": "Singapore", "medical_stay_start_date": "2025-07-29", "medical_stay_end_date": "2025-08-04", "num_guests_total": 2, "airport_pick_up_required": true, "local_transportation_needs": ["wheelchair-accessible taxi"], "additional_local_services_needed": ["interpreter"], "dietary_needs": ["halal"], "sim_card_assistance_needed": true, "leisure_activities_interest": ["city tours"], "patient_accessibility_needs": "wheelchair accessible"}'
        The agent returns a JSON object conforming to TravelLogisticsOutput schema,
        containing structured suggestions for various local services."""
    )
    args_schema: Type[TravelLogisticsInput] = TravelLogisticsInput

    _llm: BaseLLM = PrivateAttr()
    _local_medical_transport_tool: LocalMedicalTransportTool = PrivateAttr()
    _web_research_tool: WebResearchTool = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self._llm = LoadModel.load_llm_model()
            self._local_medical_transport_tool = LocalMedicalTransportTool()
            self._web_research_tool = WebResearchTool()
            logging.info("TravelLogisticsAgent initialized with internal LLM and sub-tools.")
        except Exception as e:
            logging.error(f"Failed to initialize TravelLogisticsAgent's internal components: {e}", exc_info=True)
            raise CustomException(sys, e)

    def _parse_web_snippets(self, web_results: List[WebSearchResult], category: str = "general") -> List[Dict[str, Any]]:
        """Generic parser for web search snippets."""
        processed_results = []
        for result in web_results:
            data = {
                "name": result.title,
                "description": result.snippet,
                "source_url": result.link
            }
            if category in ["service", "leisure"]:
                phone_match = re.search(r'\+?\d{1,3}[\s-]?\d{3}[\s-]?\d{4,}', result.snippet)
                if phone_match:
                    data["contact"] = phone_match.group(0)
            if category == "restaurant":
                address_match = re.search(r'\d+\s+[\w\s,.-]+(Rd|St|Ave|Blvd|Street|Road)', result.snippet, re.IGNORECASE)
                if address_match:
                    data["location"] = address_match.group(0)
            processed_results.append(data)
        return processed_results

    def _parse_sim_card_info(self, web_results: List[WebSearchResult]) -> Dict[str, Any]:
        info = {"general_info": []}
        for result in web_results:
            entry = {"snippet": result.snippet, "source_url": result.link}
            snippet_lower = result.snippet.lower()
            if "airport" in snippet_lower:
                info.setdefault("airport_purchase_info", []).append(entry)
            elif any(k in snippet_lower for k in ["store", "provider", "shop"]):
                info.setdefault("store_info", []).append(entry)
            else:
                info["general_info"].append(entry)
        return info

    async def _arun(self, **kwargs: Any) -> TravelLogisticsOutput:
        """
        Asynchronously generates comprehensive local logistics arrangements.
        Uses LLM *only* to synthesize web results. Python assembles the final plan.
        """
        try:
            tool_input = self.args_schema(**kwargs)
        except ValidationError as e:
            logging.error(f"Input validation failed for TravelLogisticsAgent: {e}", exc_info=True)
            return TravelLogisticsOutput(status="Failed", message="Input validation failed", error=str(e))
        
        logging.info(f"TravelLogisticsAgent: Starting logistics planning for {tool_input.medical_destination_city}.")

        all_results: Dict[str, Any] = {}
        errors: List[str] = []
        
        # --- Step 1: Gather ALL raw data (unchanged) ---
        try:
            tasks_to_run = []
            
            # Airport pick-up
            if tool_input.airport_pick_up_required:
                pick_up_kwargs = LocalMedicalTransportInput(
                    destination_city=tool_input.medical_destination_city,
                    destination_country=tool_input.medical_destination_country,
                    transport_date=tool_input.medical_stay_start_date,
                    transport_purpose="airport transfer",
                    transport_type="medical shuttle" if tool_input.patient_accessibility_needs else "taxi",
                    accessibility_needs=tool_input.patient_accessibility_needs
                ).model_dump(exclude_unset=True)
                tasks_to_run.append(self._local_medical_transport_tool._arun(**pick_up_kwargs))
            else:
                tasks_to_run.append(asyncio.sleep(0, result=None)) # Placeholder

            # Local transport
            if tool_input.local_transportation_needs:
                transport_kwargs = LocalMedicalTransportInput(
                    destination_city=tool_input.medical_destination_city,
                    destination_country=tool_input.medical_destination_country,
                    transport_date=tool_input.medical_stay_start_date,
                    transport_purpose="hospital visits",
                    transport_type=tool_input.local_transportation_needs[0],
                    accessibility_needs=tool_input.patient_accessibility_needs
                ).model_dump(exclude_unset=True)
                tasks_to_run.append(self._local_medical_transport_tool._arun(**transport_kwargs))
            else:
                tasks_to_run.append(asyncio.sleep(0, result=None)) # Placeholder

            # Web search tasks
            service_queries = [f"{s} services in {tool_input.medical_destination_city}, {tool_input.medical_destination_country}" for s in tool_input.additional_local_services_needed]
            dietary_queries = [f"{diet} restaurants in {tool_input.medical_destination_city}, {tool_input.medical_destination_country}" for diet in tool_input.dietary_needs]
            leisure_queries = [f"{activity} in {tool_input.medical_destination_city}, {tool_input.medical_destination_country}" for activity in tool_input.leisure_activities_interest]
            
            web_search_tasks = [self._web_research_tool._arun(query=q) for q in service_queries + dietary_queries + leisure_queries]
            
            if tool_input.sim_card_assistance_needed:
                sim_query = f"buy local SIM card {tool_input.medical_destination_country} airport OR {tool_input.medical_destination_city}"
                web_search_tasks.append(self._web_research_tool._arun(query=sim_query))
            
            # Run all tasks concurrently
            all_task_results = await asyncio.gather(*tasks_to_run, *web_search_tasks, return_exceptions=True)
            
            # --- Process Structured Tool Results ---
            pick_up_output = all_task_results[0]
            if isinstance(pick_up_output, LocalMedicalTransportOutput) and not pick_up_output.error:
                all_results["airport_pick_up_info"] = pick_up_output.transport_options[0].model_dump() if pick_up_output.transport_options else None
            elif isinstance(pick_up_output, Exception):
                errors.append(f"Airport Pick-up Exception: {str(pick_up_output)}")

            transport_output = all_task_results[1]
            if isinstance(transport_output, LocalMedicalTransportOutput) and not transport_output.error:
                all_results["local_transport_info"] = [t.model_dump() for t in transport_output.transport_options]
            elif isinstance(transport_output, Exception):
                 errors.append(f"Local Transport Exception: {str(transport_output)}")

            # --- Process Web Search Results (for LLM) ---
            web_results_raw = all_task_results[2:]
            
            all_web_results_for_llm = {
                "additional_local_services_info": [],
                "dietary_recommendations_info": [],
                "leisure_activity_suggestions_info": [],
                "sim_card_assistance_info": None
            }
            
            current_idx = 0
            for i, service in enumerate(tool_input.additional_local_services_needed):
                all_web_results_for_llm["additional_local_services_info"].append({"service_type": service, "results": web_results_raw[current_idx].organic_results[:3]})
                current_idx += 1
            for i, diet in enumerate(tool_input.dietary_needs):
                all_web_results_for_llm["dietary_recommendations_info"].append({"dietary_need": diet, "results": web_results_raw[current_idx].organic_results[:3]})
                current_idx += 1
            for i, activity in enumerate(tool_input.leisure_activities_interest):
                all_web_results_for_llm["leisure_activity_suggestions_info"].append({"activity_type": activity, "results": web_results_raw[current_idx].organic_results[:3]})
                current_idx += 1
            if tool_input.sim_card_assistance_needed:
                all_web_results_for_llm["sim_card_assistance_info"] = self._parse_sim_card_info(web_results_raw[current_idx].organic_results[:5])

        except Exception as e:
            logging.error(f"Critical error during data gathering: {e}", exc_info=True)
            errors.append(f"Data gathering failed: {e}")

        # --- Step 2: Use LLM to synthesize *only* web results ---
        synthesis_prompt = ChatPromptTemplate.from_messages([
            ("system", TRAVEL_LOGISTICS_PROMPT_TEMPLATE),
            ("human", "Please synthesize the travel logistics data into structured options.")
        ])
        
        # Use the NEW simple output model
        structured_llm = self._llm.with_structured_output(TravelLogisticsLLMOutput)
        synthesis_chain = synthesis_prompt | structured_llm
        
        llm_input = {
            "patient_accessibility_needs": tool_input.patient_accessibility_needs,
            "all_results": json.dumps(all_web_results_for_llm, indent=2)
        }

        llm_output: Optional[TravelLogisticsLLMOutput] = None
        try:
            llm_output = await synthesis_chain.ainvoke(llm_input)
        except Exception as e:
            logging.error(f"LLM output invalid: {e}", exc_info=True)
            errors.append(f"LLM synthesis failed: {str(e)}")

        if not llm_output:
            logging.warning("LLM returned None, creating empty synthesis output.")
            llm_output = TravelLogisticsLLMOutput()

        # --- Step 3: Python Assembly (New Strategy) ---
        status = "Completed"
        message = "Travel logistics planned."
        if errors:
            status = "Partial"
            message = "Travel logistics partially planned. See errors for details."

        try:
            final_output = TravelLogisticsOutput(
                status=status,
                # Get structured data directly from tool results
                airport_pick_up_details=all_results.get("airport_pick_up_info"),
                local_transport_suggestions=all_results.get("local_transport_info", []),
                # Get synthesized data from LLM output
                additional_local_services_suggestions=llm_output.additional_local_services_suggestions,
                dietary_recommendations=llm_output.dietary_recommendations,
                sim_card_assistance_info=llm_output.sim_card_assistance_info,
                leisure_activity_suggestions=llm_output.leisure_activity_suggestions,
                message=message,
                error="; ".join(errors) if errors else None
            )
            logging.info("TravelLogisticsAgent: Successfully assembled logistics plan.")
            return final_output
            
        except Exception as e:
            logging.error(f"Final assembly failed: {e}", exc_info=True)
            return TravelLogisticsOutput(
                status="Failed",
                message="Travel logistics planning failed unexpectedly during final assembly.",
                error=str(e)
            )
        
    def _run(self, **kwargs: Any) -> Any:
        """Synchronous run method (not recommended for this async-first tool)."""
        raise NotImplementedError("This tool is async-first. Please use .ainvoke() or await ._arun()")