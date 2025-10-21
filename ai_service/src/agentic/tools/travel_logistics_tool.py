# ai_service/src/agentic/tools/travel_logistics_tool.py
import sys
import json
import asyncio
import re
from typing import Type, List, Dict, Any
from .base_async_tool import BaseAsyncTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage
from langchain_core.language_models.llms import BaseLLM
from pydantic import ValidationError, PrivateAttr
from ..logger import logging
from ..exception import CustomException
from ..utils.main_utils import LoadModel 
from ..models import (TravelLogisticsInput, TravelLogisticsOutput, WebResearchToolInput, WebSearchResult,LocalMedicalTransportInput, LocalMedicalTransportOutput)
from .arrange_local_medical_transport_tool import LocalMedicalTransportTool
from .web_research_tool import WebResearchTool
from pathlib import Path

# Load prompt from file
try:
    prompt_file_path = Path(__file__).parent.parent / "prompt" / "travel_logistics_prompt.txt"
    with open(prompt_file_path, 'r', encoding='utf-8') as f:
        TRAVEL_LOGISTICS_PROMPT_TEMPLATE = f.read()
except FileNotFoundError as e:
    raise RuntimeError(f"Failed to load travel logistics prompt file: {prompt_file_path}") from e

def clean_llm_output(output: str) -> str:
    """Remove markdown fences and extra whitespace from LLM output."""
    return re.sub(r"^```(?:json)?\s*|```$", "", output.strip(), flags=re.MULTILINE | re.IGNORECASE)

class TravelLogisticsTool(BaseAsyncTool):
    """
    A high-level tool for arranging local logistics for medical tourism,
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
        The tool returns a JSON object conforming to TravelLogisticsOutput schema,
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
            logging.info("TravelLogisticsTool initialized with internal LLM and sub-tools.")
        except Exception as e:
            logging.error(f"Failed to initialize TravelLogisticsTool's internal components: {e}", exc_info=True)
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

    async def _arun(self, tool_input: TravelLogisticsInput) -> TravelLogisticsOutput:
        """
        Asynchronously generates comprehensive local logistics arrangements.
        """
        logging.info(f"TravelLogisticsTool: Starting logistics planning for {tool_input.medical_destination_city}.")

        all_results: Dict[str, Any] = {}
        errors: List[str] = []
        
        try:
            # Airport pick-up
            if tool_input.airport_pick_up_required:
                try:
                    pick_up_input = LocalMedicalTransportInput(
                        destination_city=tool_input.medical_destination_city,
                        destination_country=tool_input.medical_destination_country,
                        transport_date=tool_input.medical_stay_start_date,
                        transport_purpose="airport transfer",
                        transport_type="medical shuttle" if tool_input.patient_accessibility_needs else "taxi",
                        accessibility_needs=tool_input.patient_accessibility_needs
                    )
                    pick_up_output: LocalMedicalTransportOutput = await self._local_medical_transport_tool._arun(pick_up_input)
                    if pick_up_output.error:
                        errors.append(f"Airport Pick-up Error: {pick_up_output.error}")
                        all_results["airport_pick_up_info"] = None
                    else:
                        all_results["airport_pick_up_info"] = pick_up_output.transport_options[0].model_dump() if pick_up_output.transport_options else None
                except Exception as e:
                    errors.append(f"Airport Pick-up Exception: {str(e)}")
                    all_results["airport_pick_up_info"] = None

            # Local transport
            if tool_input.local_transportation_needs:
                try:
                    transport_input = LocalMedicalTransportInput(
                        destination_city=tool_input.medical_destination_city,
                        destination_country=tool_input.medical_destination_country,
                        transport_date=tool_input.medical_stay_start_date,
                        transport_purpose="hospital visits",
                        transport_type=tool_input.local_transportation_needs[0],
                        accessibility_needs=tool_input.patient_accessibility_needs
                    )
                    transport_output: LocalMedicalTransportOutput = await self._local_medical_transport_tool._arun(transport_input)
                    if transport_output.error:
                        errors.append(f"Local Transport Error: {transport_output.error}")
                        all_results["local_transport_info"] = []
                    else:
                        all_results["local_transport_info"] = [t.model_dump() for t in transport_output.transport_options]
                except Exception as e:
                    errors.append(f"Local Transport Exception: {str(e)}")
                    all_results["local_transport_info"] = []

            # Additional local services
            if tool_input.additional_local_services_needed:
                service_queries = [f"{s} services in {tool_input.medical_destination_city}, {tool_input.medical_destination_country}" for s in tool_input.additional_local_services_needed]
                web_results_list = await asyncio.gather(*[
                    self._web_research_tool._arun(WebResearchToolInput(query=q)) for q in service_queries
                ])
                all_results["additional_local_services_info"] = []
                for i, web_result in enumerate(web_results_list):
                    if web_result.error:
                        errors.append(f"Web Service ({tool_input.additional_local_services_needed[i]}) Error: {web_result.error}")
                        all_results["additional_local_services_info"].append({"service_type": tool_input.additional_local_services_needed[i], "suggestions": []})
                    else:
                        suggestions = self._parse_web_snippets(web_result.organic_results[:3], category="service")
                        all_results["additional_local_services_info"].append({"service_type": tool_input.additional_local_services_needed[i], "suggestions": suggestions})

            # Dietary needs
            if tool_input.dietary_needs:
                dietary_queries = [f"{diet} restaurants in {tool_input.medical_destination_city}, {tool_input.medical_destination_country}" for diet in tool_input.dietary_needs]
                web_results_list = await asyncio.gather(*[
                    self._web_research_tool._arun(WebResearchToolInput(query=q)) for q in dietary_queries
                ])
                all_results["dietary_recommendations_info"] = []
                for i, web_result in enumerate(web_results_list):
                    if web_result.error:
                        errors.append(f"Web Diet ({tool_input.dietary_needs[i]}) Error: {web_result.error}")
                        all_results["dietary_recommendations_info"].append({"dietary_need": tool_input.dietary_needs[i], "suggestions": []})
                    else:
                        suggestions = self._parse_web_snippets(web_result.organic_results[:3], category="restaurant")
                        all_results["dietary_recommendations_info"].append({"dietary_need": tool_input.dietary_needs[i], "suggestions": suggestions})

            # SIM card assistance
            if tool_input.sim_card_assistance_needed:
                try:
                    sim_query = f"buy local SIM card {tool_input.medical_destination_country} airport OR {tool_input.medical_destination_city}"
                    sim_result: WebResearchToolInput = await self._web_research_tool._arun(WebResearchToolInput(query=sim_query))
                    if sim_result.error:
                        errors.append(f"SIM Card Error: {sim_result.error}")
                        all_results["sim_card_assistance_info"] = None
                    else:
                        all_results["sim_card_assistance_info"] = self._parse_sim_card_info(sim_result.organic_results[:5])
                except Exception as e:
                    errors.append(f"SIM Card Exception: {str(e)}")
                    all_results["sim_card_assistance_info"] = None

            # Leisure activities
            if tool_input.leisure_activities_interest:
                leisure_queries = [f"{activity} in {tool_input.medical_destination_city}, {tool_input.medical_destination_country}" for activity in tool_input.leisure_activities_interest]
                web_results_list = await asyncio.gather(*[
                    self._web_research_tool._arun(WebResearchToolInput(query=q)) for q in leisure_queries
                ])
                all_results["leisure_activity_suggestions_info"] = []
                for i, web_result in enumerate(web_results_list):
                    if web_result.error:
                        errors.append(f"Web Leisure ({tool_input.leisure_activities_interest[i]}) Error: {web_result.error}")
                        all_results["leisure_activity_suggestions_info"].append({"activity_type": tool_input.leisure_activities_interest[i], "suggestions": []})
                    else:
                        suggestions = self._parse_web_snippets(web_result.organic_results[:3], category="leisure")
                        all_results["leisure_activity_suggestions_info"].append({"activity_type": tool_input.leisure_activities_interest[i], "suggestions": suggestions})

            # Use LLM to synthesize
            synthesis_prompt = ChatPromptTemplate.from_messages([
                ("system", TRAVEL_LOGISTICS_PROMPT_TEMPLATE),
                ("human", "Please synthesize the travel logistics data into structured options.")
            ])
            synthesis_chain = synthesis_prompt | self._llm
            llm_response = await synthesis_chain.ainvoke({
                "medical_purpose": tool_input.medical_purpose,
                "airport_pick_up_required": tool_input.airport_pick_up_required,
                "local_transportation_needs": tool_input.local_transportation_needs,
                "additional_local_services_needed": tool_input.additional_local_services_needed,
                "dietary_needs": tool_input.dietary_needs,
                "sim_card_assistance_needed": tool_input.sim_card_assistance_needed,
                "leisure_activities_interest": tool_input.leisure_activities_interest,
                "medical_destination_city": tool_input.medical_destination_city,
                "medical_destination_country": tool_input.medical_destination_country,
                "medical_stay_start_date": tool_input.medical_stay_start_date,
                "medical_stay_end_date": tool_input.medical_stay_end_date,
                "patient_accessibility_needs": tool_input.patient_accessibility_needs,
                "num_guests_total": tool_input.num_guests_total,
                "all_results": json.dumps(all_results, indent=2),
                "errors": json.dumps(errors)
            })

            llm_output_str = llm_response.content if isinstance(llm_response, BaseMessage) else str(llm_response)
            cleaned_str = clean_llm_output(llm_output_str)

            try:
                parsed_json = json.loads(cleaned_str)
                validated_output = TravelLogisticsOutput(**parsed_json)
                # If any errors occurred but output is valid, mark Partial
                if errors and validated_output.status == "Completed":
                    validated_output.status = "Partial"
                    validated_output.message += " (Some sub-tools returned errors, see error field.)"
                    validated_output.error = "; ".join(errors)
                return validated_output
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                logging.error(f"LLM output invalid: {cleaned_str}. Error: {e}", exc_info=True)
                return TravelLogisticsOutput(
                    status="Failed",
                    message="Travel logistics planning failed due to invalid LLM output.",
                    error=f"LLM output was invalid or malformed: {str(e)}"
                )

        except Exception as e:
            logging.error(f"Unexpected error in TravelLogisticsTool: {e}", exc_info=True)
            return TravelLogisticsOutput(
                status="Failed",
                message="Travel logistics planning failed unexpectedly.",
                error=str(e)
            )     