# ai_service/src/agentic/tools/travel_arrangement_tool.py
import sys
import json
import asyncio
from typing import Type, List, Dict, Any
from datetime import datetime
import re
from pathlib import Path
from .base_async_tool import BaseAsyncTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage
from pydantic import PrivateAttr
from ..logger import logging
from ..exception import CustomException
from ..utils.main_utils import LoadModel, escape_braces_except_placeholders
from ..models import (TravelArrangementInput, TravelArrangementOutput, CityToIATACodeInput, AccessibleAccommodationInput, GetWeatherDataInput)
from .city_to_iata_code_tool import CityToIATACodeTool
from .search_flights_tool import SearchFlightsTool
from .search_accessible_accommodation_tool import AccessibleAccommodationTool
from .get_weather_data_tool import GetWeatherDataTool
from .web_research_tool import WebResearchTool
from .check_visa_requirements_tool import VisaRequirementsCheckerTool

class TravelArrangementTool(BaseAsyncTool):
    """
    A high-level tool for planning travel arrangements, including flights,
    accommodations, and optional weather information. It orchestrates
    lower-level tools and uses an internal LLM to synthesize findings.
    """
    name: str = "travel_arrangement_planning"
    description: str = (
        """Useful for generating comprehensive travel plans for medical tourism,
        including flight options, accessible accommodation suggestions, and weather information.
        Input MUST be a JSON object conforming to TravelArrangementInput schema.
        Example: '{"departure_city": "Kuala Lumpur", "estimated_return_date": "2025-08-05", "flight_preferences": ["direct"], "accommodation_requirements": ["near hospital"], "preferred_accommodation_star_rating": "4-star", "visa_assistance_needed": false, "medical_destination_city": "Singapore", "medical_destination_country": "Singapore", "medical_departure_date": "2025-07-28", "num_guests_medical_plan": 2}'
        The tool returns a JSON object conforming to TravelArrangementOutput schema,
        containing lists of structured flight and accommodation suggestions."""
    )
    args_schema: Type[TravelArrangementInput] = TravelArrangementInput

    _llm: Any = PrivateAttr()
    _city_to_iata_code_tool: CityToIATACodeTool = PrivateAttr()
    _search_flights_tool: SearchFlightsTool = PrivateAttr()
    _accessible_accommodation_tool: AccessibleAccommodationTool = PrivateAttr()
    _get_weather_data_tool: GetWeatherDataTool = PrivateAttr()
    _web_research_tool: WebResearchTool = PrivateAttr()
    _visa_requirements_checker_tool: VisaRequirementsCheckerTool = PrivateAttr()

    def __init__(self, **kwargs):
        """
        Initializes the TravelArrangementTool, loading the internal LLM
        and instantiating all necessary sub-tools.
        """
        super().__init__(**kwargs)
        try:
            self._llm = LoadModel.load_llm_model()
            self._city_to_iata_code_tool = CityToIATACodeTool()
            self._search_flights_tool = SearchFlightsTool()
            self._accessible_accommodation_tool = AccessibleAccommodationTool()
            self._get_weather_data_tool = GetWeatherDataTool()
            self._web_research_tool = WebResearchTool()
            self._visa_requirements_checker_tool = VisaRequirementsCheckerTool()
            
            # Load and escape prompt template
            prompt_file_path = Path(__file__).parent.parent / "prompt" / "travel_arrangement_prompt.txt"
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read().strip()
            escaped_prompt_template = escape_braces_except_placeholders(prompt_content)

            self._llm_synthesis_prompt = ChatPromptTemplate.from_messages([
                ("system", escaped_prompt_template),
                ("human", "Please synthesize the travel arrangement data into structured JSON output.")
            ])

            logging.info("TravelArrangementTool initialized with internal LLM and sub-tools.")
        except Exception as e:
            logging.error("Failed to initialize TravelArrangementTool's internal components", exc_info=True)
            raise CustomException(sys, e)

    def _calculate_nights(self, check_in: str, check_out: str) -> int:
        try:
            return (datetime.strptime(check_out, "%Y-%m-%d") - datetime.strptime(check_in, "%Y-%m-%d")).days
        except ValueError as e:
            logging.error(f"Invalid date format for nightly calculation: {e}")
            return 0
        
    def _fill_missing_fields(self, parsed_output: dict) -> dict:
        """
        Recursively fill missing fields in the parsed LLM output
        to ensure full compliance with TravelArrangementOutput schema.
        """

        # Top-level fields
        parsed_output.setdefault("medical_destination_city", parsed_output.get("medical_destination_city") or "N/A")
        parsed_output.setdefault("medical_destination_country", parsed_output.get("medical_destination_country") or "N/A")
        parsed_output.setdefault("flight_suggestions", [])
        parsed_output.setdefault("accommodation_suggestions", [])
        parsed_output.setdefault("weather_info", None)
        parsed_output.setdefault("visa_assistance_flag", parsed_output.get("visa_assistance_flag", False))
        parsed_output.setdefault("visa_information", None)
        parsed_output.setdefault("message", "Your travel plan has been successfully arranged.")
        parsed_output.setdefault("error", None)

        # Flights
        for flight in parsed_output["flight_suggestions"]:
            flight.setdefault("id", "UNKNOWN")
            flight.setdefault("total_cost", 0)
            flight.setdefault("currency", "USD")
            flight.setdefault("duration", "PT0H0M")
            flight.setdefault("layovers", 0)
            flight.setdefault("segments", [])
            flight.setdefault("airline_names", "UNKNOWN")
            flight.setdefault("segments_summary", "")
            flight.setdefault("notes", "")
            for seg in flight["segments"]:
                seg.setdefault("departure_iata", "UNKNOWN")
                seg.setdefault("arrival_iata", "UNKNOWN")
                seg.setdefault("departure_time", "00:00")
                seg.setdefault("arrival_time", "00:00")
                seg.setdefault("duration", "PT0H0M")
                seg.setdefault("carrier_code", "UNKNOWN")
                seg.setdefault("number", "UNKNOWN")
                seg.setdefault("number_of_stops", 0)

        # Accommodations
        for acc in parsed_output["accommodation_suggestions"]:
            acc.setdefault("id", "UNKNOWN")
            acc.setdefault("name", "UNKNOWN")
            acc.setdefault("location", "UNKNOWN")
            acc.setdefault("country", parsed_output.get("medical_destination_country", "UNKNOWN"))
            acc.setdefault("city", parsed_output.get("medical_destination_city", "UNKNOWN"))
            acc.setdefault("min_cost_per_night_usd", 0)
            acc.setdefault("max_cost_per_night_usd", 0)
            acc.setdefault("total_cost_estimate_usd", 0)
            acc.setdefault("accessibility_features", [])
            acc.setdefault("availability", "")
            acc.setdefault("notes", "")
            acc.setdefault("nearby_landmarks", [])
            acc.setdefault("image_url", None)
            acc.setdefault("star_rating", None)
            acc.setdefault("accommodation_type", None)
            acc.setdefault("with_kitchen", 0)
            acc.setdefault("pet_friendly", 0)

        # Weather
        if parsed_output["weather_info"] is None or not isinstance(parsed_output["weather_info"], dict):
            parsed_output["weather_info"] = {}
        weather = parsed_output["weather_info"]
        weather.setdefault("city", parsed_output.get("medical_destination_city", "UNKNOWN"))
        weather.setdefault("country", parsed_output.get("medical_destination_country", "UNKNOWN"))
        weather.setdefault("date", "")
        weather.setdefault("condition", "")
        weather.setdefault("forecast", "")
        weather.setdefault("temperature_celsius", None)
        weather.setdefault("temperature_fahrenheit", None)
        weather.setdefault("humidity_percent", None)
        weather.setdefault("wind_speed_kph", None)

        # Visa
        if parsed_output["visa_information"] is None or not isinstance(parsed_output["visa_information"], dict):
            parsed_output["visa_information"] = {}
        visa = parsed_output["visa_information"]
        visa.setdefault("visa_required", False)
        visa.setdefault("visa_type", None)
        visa.setdefault("stay_duration_notes", None)
        visa.setdefault("processing_time_days", None)
        visa.setdefault("notes", None)
        visa.setdefault("required_documents", [])

        return parsed_output

    def _clean_llm_json_output(self, raw_output: str) -> str:
        s = raw_output.strip()
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"```$", "", s)
        s = s.replace("\uFEFF", "").replace("\u200b", "")
        s = s.replace("\\'", "'").replace("'", '"')
        s = s.replace("None", "null")
        if not s.startswith("{"):
            i = s.find("{")
            if i >= 0: s = s[i:]
        if not s.endswith("}"):
            j = s.rfind("}")
            if j >= 0: s = s[:j+1]
        return s
        
    async def _safe_call(self, coro, tool_name: str, all_results: dict, errors: list, result_key: str):
        """
        Helper to safely call a sub-tool and capture exceptions without breaking the whole flow.
        """
        try:
            result = await coro
            if hasattr(result, "model_dump"):
                all_results[result_key] = result.model_dump()
            else:
                all_results[result_key] = result
            if getattr(result, "error", None):
                errors.append(f"{tool_name} Error: {result.error}")
            return result
        except Exception as e:
            logging.error(f"{tool_name} failed: {e}", exc_info=True)
            all_results[result_key] = {"error": str(e)}
            errors.append(f"{tool_name} Exception: {str(e)}")
            return None
        
    @staticmethod
    def _parse_date_to_iso_safe(date_str: str, errors: list, field_name: str) -> str | None:
        """
        Tries to parse date string in multiple formats and return ISO YYYY-MM-DD.
        If parsing fails, log error and return None (will be converted to null in JSON).
        """
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        errors.append(f"Invalid date format for {field_name}: '{date_str}'")
        return None

    async def _arun(self, tool_input: TravelArrangementInput) -> TravelArrangementOutput:
        """
        Asynchronously plans travel arrangements by orchestrating sub-tools and an internal LLM.
        """
        errors: List[str] = []
        departure_city = tool_input.departure_city
        medical_destination_city = tool_input.medical_destination_city
        medical_destination_country = tool_input.medical_destination_country
        num_guests_medical_plan = tool_input.num_guests_medical_plan

        if not medical_destination_city or medical_destination_city.upper() == 'N/A':
            error_msg = "Travel planning requires a specific destination city."
            logging.error(error_msg)
            return TravelArrangementOutput(
                message="Unable to continue planning the trip. Please provide a specific destination city.",
                error=error_msg,
                medical_destination_city=medical_destination_city
            )

        logging.info(f"Starting travel planning from {departure_city} to {medical_destination_city}.")

        all_results: Dict[str, Any] = {}

        try:
            # 1. Concurrently fetch IATA codes
            origin_task = self._safe_call(
                self._city_to_iata_code_tool._arun(CityToIATACodeInput(city_name=departure_city)),
                "CityToIATACodeTool (Origin)", all_results, errors, "iata_codes_origin"
            )
            dest_task = self._safe_call(
                self._city_to_iata_code_tool._arun(CityToIATACodeInput(city_name=medical_destination_city)),
                "CityToIATACodeTool (Destination)", all_results, errors, "iata_codes_destination"
            )
            origin_iata_output, destination_iata_output = await asyncio.gather(origin_task, dest_task)

            # 2. Accommodation
            accommodation_output = await self._accessible_accommodation_tool._arun(
                AccessibleAccommodationInput(
                    destination_city=medical_destination_city,
                    destination_country=medical_destination_country,
                    check_in_date=tool_input.check_in_date,
                    check_out_date=tool_input.check_out_date,
                    num_guests=num_guests_medical_plan,
                    accessibility_needs=tool_input.accessibility_needs,
                    star_rating_min=tool_input.star_rating_min,
                    star_rating_max=tool_input.star_rating_max,
                    with_kitchen_req=tool_input.with_kitchen_req,
                    pet_friendly_req=tool_input.pet_friendly_req,
                    nearby_landmarks=tool_input.nearby_landmarks
                )
            )
            all_results["accommodation_results"] = accommodation_output.model_dump()

            # 3. Weather
            weather_output = await self._get_weather_data_tool._arun(
                GetWeatherDataInput(destination=medical_destination_city, date=tool_input.check_in_date)
            )
            all_results["weather_data_results"] = weather_output.model_dump()
            if weather_output.error or not (weather_output.weather_data and weather_output.weather_data.forecast):
                web_search_weather_output = await self._web_research_tool._arun(
                    query=f"long-term weather forecast for {medical_destination_city} around {tool_input.check_in_date}"
                )
                all_results["web_search_weather_results"] = web_search_weather_output.model_dump()

            # 4. Flights
            origin_iata_code = next((a.iata_code for a in origin_iata_output.airports), None)
            destination_iata_code = next((a.iata_code for a in destination_iata_output.airports), None)
            if origin_iata_code and destination_iata_code:
                flight_output = await self._search_flights_tool._arun(
                    origin=origin_iata_code,
                    destination=destination_iata_code,
                    departure_date=tool_input.check_in_date,
                    return_date=tool_input.estimated_return_date,
                    adults=num_guests_medical_plan,
                    non_stop='direct' in (f.lower() for f in (tool_input.flight_preferences or []))
                )
                all_results["flight_search_results"] = flight_output.model_dump()

            # 5. Visa
            if tool_input.visa_assistance_needed:
                all_results["visa_information"] = tool_input.visa_information_from_medical_plan

            # 6. LLM synthesis
            llm_input = {
                "departure_city": departure_city,
                "estimated_return_date": tool_input.estimated_return_date,
                "check_in_date": tool_input.check_in_date,
                "check_out_date": tool_input.check_out_date,
                "user_preferences": {
                    "flight_preferences": tool_input.flight_preferences or [],
                    "accommodation_requirements": tool_input.accommodation_requirements or [],
                    "accessibility_needs": tool_input.accessibility_needs or [],
                    "star_rating_min": tool_input.star_rating_min,
                    "star_rating_max": tool_input.star_rating_max,
                    "nearby_landmarks": tool_input.nearby_landmarks,
                    "with_kitchen_req": tool_input.with_kitchen_req,
                    "pet_friendly_req": tool_input.pet_friendly_req
                },
                "medical_destination_city": medical_destination_city,
                "medical_destination_country": medical_destination_country,
                "num_guests_medical_plan": num_guests_medical_plan,
                "visa_assistance_needed": tool_input.visa_assistance_needed,
                "all_results": all_results,
                "errors": errors
            }

            synthesis_chain = self._llm_synthesis_prompt | self._llm
            llm_response = await synthesis_chain.ainvoke(llm_input)
            raw_output = llm_response.content if isinstance(llm_response, BaseMessage) else str(llm_response)
            try:
                parsed_output = json.loads(raw_output)
            except json.JSONDecodeError:
                cleaned = self._clean_llm_json_output(raw_output)
                parsed_output = json.loads(cleaned)

            parsed_output = self._fill_missing_fields(parsed_output)
            validated_output = TravelArrangementOutput(**parsed_output)
            logging.info("TravelArrangementTool: Successfully generated travel plan.")
            return validated_output

        except Exception as e:
            logging.error(f"Unexpected error: {e}", exc_info=True)
            return TravelArrangementOutput(
                message="An unexpected error occurred during travel planning.",
                error=str(e),
                medical_destination_city=medical_destination_city
            )     
