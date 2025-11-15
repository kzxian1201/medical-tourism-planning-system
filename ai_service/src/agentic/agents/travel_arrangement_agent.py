# ai_service/src/agentic/agents/travel_arrangement_agent.py
import sys
import json
import asyncio
from typing import Type, List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import PrivateAttr, ValidationError
from ..logger import logging
from ..exception import CustomException
from ..utils.main_utils import LoadModel, escape_braces_except_placeholders
from ..models import (TravelArrangementInput, TravelArrangementOutput, CityToIATACodeInput, AccessibleAccommodationInput, GetWeatherDataInput, TravelArrangementLLMOutput, WeatherData, SearchFlightsInput, WebResearchToolInput)
from ..tools.city_to_iata_code_tool import CityToIATACodeTool
from ..tools.search_flights_tool import SearchFlightsTool
from ..tools.search_accessible_accommodation_tool import AccessibleAccommodationTool
from ..tools.get_weather_data_tool import GetWeatherDataTool
from ..tools.web_research_tool import WebResearchTool
from ..tools.check_visa_requirements_tool import VisaRequirementsCheckerTool

class TravelArrangementAgent(BaseTool):
    """
    A high-level agent for planning travel arrangements, including flights,
    accommodations, and optional weather information. It orchestrates
    lower-level tools and uses an internal LLM to synthesize findings.
    """
    name: str = "travel_arrangement_planning"
    description: str = (
        """Useful for generating comprehensive travel plans for medical tourism,
        including flight options, accessible accommodation suggestions, and weather information.
        Input MUST be a JSON object conforming to TravelArrangementInput schema.
        Example: '{"departure_city": "Kuala Lumpur", "estimated_return_date": "2025-08-05", "flight_preferences": ["direct"], "accommodation_requirements": ["near hospital"], "preferred_accommodation_star_rating": "4-star", "visa_assistance_needed": false, "medical_destination_city": "Singapore", "medical_destination_country": "Singapore", "medical_departure_date": "2025-07-28", "num_guests_medical_plan": 2}'
        The agent returns a JSON object conforming to TravelArrangementOutput schema,
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
        Initializes the TravelArrangementAgent, loading the internal LLM
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

            logging.info("TravelArrangementAgent initialized with internal LLM and sub-tools.")
        except Exception as e:
            logging.error("Failed to initialize TravelArrangementAgent's internal components", exc_info=True)
            raise CustomException(sys, e)

    def _calculate_nights(self, check_in: str, check_out: str) -> int:
        try:
            return (datetime.strptime(check_out, "%Y-%m-%d") - datetime.strptime(check_in, "%Y-%m-%d")).days
        except ValueError as e:
            logging.error(f"Invalid date format for nightly calculation: {e}")
            return 0
        
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

    async def _arun(self, **kwargs: Any) -> TravelArrangementOutput:
        """
        Asynchronously plans travel arrangements by orchestrating sub-tools
        and using an internal LLM *only* for synthesis, with Python handling assembly.
        """
        try:
            tool_input = self.args_schema(**kwargs)
        except ValidationError as e:
            logging.error(f"Input validation failed for TravelArrangementAgent: {e}", exc_info=True)
            return TravelArrangementOutput(message="Input validation failed", error=str(e))
        
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
        
        # --- Step 1, 2, 3, 4: Gather ALL raw data (unchanged) ---
        try:
            # 1. Concurrently fetch IATA codes
            origin_task = self._safe_call(
                self._city_to_iata_code_tool._arun(city_name=departure_city),
                "CityToIATACodeTool (Origin)", all_results, errors, "iata_codes_origin"
            )
            dest_task = self._safe_call(
                self._city_to_iata_code_tool._arun(city_name=medical_destination_city),
                "CityToIATACodeTool (Destination)", all_results, errors, "iata_codes_destination"
            )
            origin_iata_output, destination_iata_output = await asyncio.gather(origin_task, dest_task)

            # 2. Accommodation (Get all options)
            accommodation_kwargs = AccessibleAccommodationInput(
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
            ).model_dump()
            
            accommodation_output = await self._accessible_accommodation_tool._arun(**accommodation_kwargs)
            all_results["accommodation_results"] = accommodation_output.model_dump()
            
            # 3. Weather
            weather_output = await self._get_weather_data_tool._arun(
                destination=medical_destination_city, date=tool_input.check_in_date
            )
            all_results["weather_data_results"] = weather_output.model_dump()
            if weather_output.error or not (weather_output.weather_data and weather_output.weather_data.forecast):
                web_search_weather_output = await self._web_research_tool._arun(
                    query=f"long-term weather forecast for {medical_destination_city} around {tool_input.check_in_date}"
                )
                all_results["web_search_weather_results"] = web_search_weather_output.model_dump()
            
            # 4. Flights
            origin_iata_code = next((a.iata_code for a in origin_iata_output.airports), None) if origin_iata_output and origin_iata_output.airports else None
            destination_iata_code = next((a.iata_code for a in destination_iata_output.airports), None) if destination_iata_output and destination_iata_output.airports else None
            
            if origin_iata_code and destination_iata_code:
                flight_kwargs = SearchFlightsInput(
                    origin=origin_iata_code,
                    destination=destination_iata_code,
                    departure_date=tool_input.check_in_date,
                    return_date=tool_input.estimated_return_date,
                    adults=num_guests_medical_plan,
                    non_stop='direct' in (f.lower() for f in (tool_input.flight_preferences or []))
                ).model_dump(exclude_unset=True)
                
                flight_output = await self._search_flights_tool._arun(**flight_kwargs)
                all_results["flight_search_results"] = flight_output.model_dump()
            else:
                errors.append("Could not find IATA codes for flight search.")
            
            # 5. Visa (Data is already structured, just copy it)
            if tool_input.visa_assistance_needed:
                all_results["visa_information"] = tool_input.visa_information_from_medical_plan

        except Exception as e:
            logging.error(f"Critical error during data gathering: {e}", exc_info=True)
            errors.append(f"Data gathering failed: {e}")
        
        # --- Step 6. LLM Synthesis (New Strategy) ---
        # Use the NEW simple output model
        structured_llm = self._llm.with_structured_output(TravelArrangementLLMOutput)
        synthesis_chain = self._llm_synthesis_prompt | structured_llm
        
        llm_input = {
            "user_preferences": {
                "flight_preferences": tool_input.flight_preferences or [],
                "accommodation_requirements": tool_input.accommodation_requirements or [],
                "accessibility_needs": tool_input.accessibility_needs or [],
                "star_rating_min": tool_input.star_rating_min,
                "star_rating_max": tool_input.star_rating_max
            },
            # Pass only the raw results the LLM needs to synthesize
            "all_results": {
                "flight_search_results": all_results.get("flight_search_results"),
                "accommodation_results": all_results.get("accommodation_results")
            }
        }
        
        llm_output: Optional[TravelArrangementLLMOutput] = None
        try:
            llm_output = await synthesis_chain.ainvoke(llm_input)
        except Exception as e:
            logging.error(f"LLM synthesis failed: {e}", exc_info=True)
            errors.append(f"LLM synthesis failed: {e}")

        if not llm_output:
            logging.warning("LLM returned None, creating empty synthesis output.")
            llm_output = TravelArrangementLLMOutput(flight_suggestions=[], accommodation_suggestions=[])

        # --- Step 7. Python Assembly ---
        try:
            # Manually build the weather info
            weather_data = None
            if all_results.get("weather_data_results") and not all_results["weather_data_results"].get("error"):
                raw_weather = all_results["weather_data_results"].get("weather_data", {})
                if raw_weather:
                    forecast_list = raw_weather.get("forecast", {}).get("forecastday", [])
                    forecast_day = forecast_list[0] if forecast_list else {}
                    weather_data = WeatherData(
                        city=raw_weather.get("location", {}).get("name", medical_destination_city),
                        country=raw_weather.get("location", {}).get("country", medical_destination_country),
                        date=forecast_day.get("date", tool_input.check_in_date),
                        condition=forecast_day.get("day", {}).get("condition", {}).get("text", "N/A"),
                        temperature_celsius=forecast_day.get("day", {}).get("avgtemp_c"),
                        temperature_fahrenheit=forecast_day.get("day", {}).get("avgtemp_f"),
                        humidity_percent=forecast_day.get("day", {}).get("avghumidity"),
                        wind_speed_kph=forecast_day.get("day", {}).get("maxwind_kph"),
                        forecast=f"Avg {forecast_day.get('day', {}).get('avgtemp_c')}°C. {forecast_day.get('day', {}).get('condition', {}).get('text', 'N/A')}."
                    )
            
            # Manually build the final output
            final_message = "Travel arrangements planned."
            if errors:
                final_message = "Travel arrangements partially planned. See errors for details."
                
            final_output = TravelArrangementOutput(
                medical_destination_city=medical_destination_city,
                flight_suggestions=llm_output.flight_suggestions,
                accommodation_suggestions=llm_output.accommodation_suggestions,
                weather_info=weather_data,
                visa_assistance_flag=tool_input.visa_assistance_needed,
                visa_information=all_results.get("visa_information"),
                message=final_message,
                error="; ".join(errors) if errors else None
            )
            
            logging.info("TravelArrangementAgent: Successfully assembled travel plan.")
            return final_output

        except Exception as e:
            logging.error(f"Final assembly failed: {e}", exc_info=True)
            return TravelArrangementOutput(
                message="An unexpected error occurred during final plan assembly.",
                error=str(e),
                medical_destination_city=medical_destination_city
            )
        
    def _run(self, **kwargs: Any) -> Any:
        """Synchronous run method (not recommended for this async-first tool)."""
        raise NotImplementedError("This tool is async-first. Please use .ainvoke() or await ._arun()")