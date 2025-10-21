# ai_service/src/agentic/tools/search_accessible_accommodation_tool.py
import sys
import json
import asyncio
import nest_asyncio
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Type
from ..logger import logging
from ..exception import CustomException
from ..models import AccessibleAccommodationInput, AccessibleAccommodationOutput, AccommodationOption
from langchain_core.tools import BaseTool

class AccessibleAccommodationTool(BaseTool):
    """
    A tool to search for accommodations that are accessible
    and suitable for individuals with specific medical or mobility needs.
    It retrieves structured data from a local JSON file.
    """
    name: str = "accessible_accommodation_search"
    description: str = (
        """Useful for searching for accommodations that are accessible and suitable for individuals with specific medical or mobility needs.
        Input MUST be a JSON object conforming to AccessibleAccommodationInput schema.
        Required fields: 'destination_city' (string), 'destination_country' (string), 'check_in_date' (YYYY-MM-DD), 'check_out_date' (YYYY-MM-DD).
        Optional fields: 'num_guests', 'accommodation_type' (list of strings, e.g., ['hotel', 'serviced_apartment']),
        'accessibility_needs' (list of strings, e.g., ['wheelchair accessible room']), 'nearby_landmarks',
        'star_rating_min' (integer), 'star_rating_max' (integer), 'with_kitchen_req' (boolean), 'pet_friendly_req' (boolean).
        Example: '{"destination_city": "Singapore", "destination_country": "Singapore", "check_in_date": "2025-07-25", "check_out_date": "2025-07-30", "accessibility_needs": ["wheelchair accessible room"], "star_rating_min": 4, "with_kitchen_req": true}'
        The tool returns a JSON object conforming to AccessibleAccommodationOutput schema, containing a list of matching accommodation options."""
    )
    args_schema: Type[AccessibleAccommodationInput] = AccessibleAccommodationInput

    _accommodation_data_file: str = ""
    _accommodation_options_db: List[Dict[str, Any]] = []

    def __init__(self, accommodation_data_file_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if accommodation_data_file_path:
            self._accommodation_data_file = accommodation_data_file_path
        else:
            _current_script_dir = os.path.dirname(os.path.abspath(__file__))
            self._accommodation_data_file = os.path.join(_current_script_dir, '..', '..', 'data', 'accommodations.json') 

        self._accommodation_options_db = self._load_accommodation_data()
        logging.info(f"AccessibleAccommodationTool initialized with data from: {self._accommodation_data_file}")

    def _load_accommodation_data(self) -> List[Dict[str, Any]]:
        """
        Loads accessible accommodation data from the specified JSON file.
        """
        if not os.path.exists(self._accommodation_data_file):
            logging.error(f"Accommodation data file not found at: {self._accommodation_data_file}. Please ensure it exists.")
            raise FileNotFoundError(f"Accommodation data file not found at: {self._accommodation_data_file}")
        
        try:
            with open(self._accommodation_data_file, 'r', encoding='utf-8') as f:
                # flatten the 'accommodations' list for easier searching
                raw_data = json.load(f)
                flattened_accommodations = []
                for country_city_block in raw_data:
                    country = country_city_block.get("country")
                    city = country_city_block.get("city")
                    for acc in country_city_block.get("accommodations", []):
                        acc["country"] = country 
                        acc["city"] = city
                        flattened_accommodations.append(acc)
                logging.info("Accessible accommodation data loaded and flattened successfully.")
                return flattened_accommodations
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from accommodation data file {self._accommodation_data_file}: {e}")
            raise ValueError(f"Invalid JSON format in accommodation data file: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading accommodation data: {e}")
            raise CustomException(sys, e)
        
    def _build_accommodation_option(self, option_data: dict, check_in_date: str, check_out_date: str) -> Optional[AccommodationOption]:
        """
        Build an AccommodationOption object from raw dictionary data.
        Ensures cost calculation for stay duration is correct.
        """
        try:
            min_cost = option_data.get("min_cost_per_night_usd")
            max_cost = option_data.get("max_cost_per_night_usd")

            if min_cost is None or max_cost is None:
                logging.warning(f"Accommodation {option_data.get('id')} skipped due to missing cost fields.")
                return None

            num_nights = (datetime.strptime(check_out_date, "%Y-%m-%d") - datetime.strptime(check_in_date, "%Y-%m-%d")).days
            if num_nights <= 0:
                logging.warning(f"Accommodation {option_data.get('id')} skipped due to invalid date range: {check_in_date} -> {check_out_date}")
                return None

            est_min = min_cost * num_nights
            est_max = max_cost * num_nights
            total_cost_estimate = f"${est_min:.2f}" if est_min == est_max else f"${est_min:.2f} - ${est_max:.2f}"

            option_data = option_data.copy()
            option_data.pop("total_cost_estimate_usd", None)

            return AccommodationOption(**option_data, total_cost_estimate_usd=total_cost_estimate)
        except Exception as e:
            logging.warning(f"Failed to build AccommodationOption: {option_data}, error: {e}")
            return None
        
    async def _arun(self, tool_input: AccessibleAccommodationInput) -> AccessibleAccommodationOutput:
        """
        Asynchronously searches for accessible accommodations based on the provided input.
        """
        destination_city = tool_input.destination_city
        destination_country = tool_input.destination_country
        check_in_date = tool_input.check_in_date
        check_out_date = tool_input.check_out_date
        num_guests = tool_input.num_guests
        accommodation_type = tool_input.accommodation_type
        accessibility_needs = tool_input.accessibility_needs
        nearby_landmarks = tool_input.nearby_landmarks
        star_rating_min = tool_input.star_rating_min
        star_rating_max = tool_input.star_rating_max
        with_kitchen_req = tool_input.with_kitchen_req
        pet_friendly_req = tool_input.pet_friendly_req

        norm_city = destination_city.lower()
        norm_country = destination_country.lower()
        norm_types = [t.lower() for t in accommodation_type] if accommodation_type else []
        norm_needs = [n.lower() for n in accessibility_needs] if accessibility_needs else []
        norm_landmark = nearby_landmarks.lower() if nearby_landmarks else None

        matching_options: List[AccommodationOption] = []

        try:
            for option in self._accommodation_options_db:
                if not (option.get("country", "").lower() == norm_country and option.get("city", "").lower() == norm_city):
                    continue
                if norm_types and not any(t in option.get("accommodation_type", "").lower() for t in norm_types):
                    continue
                if norm_needs and not all(n in [f.lower() for f in option.get("accessibility_features", [])] for n in norm_needs):
                    continue
                if norm_landmark:
                    if norm_landmark not in option.get("location", "").lower() and not any(norm_landmark in lm.lower() for lm in option.get("nearby_landmarks", [])):
                        continue
                if star_rating_min is not None and option.get("star_rating") is not None and option["star_rating"] < star_rating_min:
                    continue
                if star_rating_max is not None and option.get("star_rating") is not None and option["star_rating"] > star_rating_max:
                    continue
                if with_kitchen_req is not None and bool(option.get("with_kitchen")) != with_kitchen_req:
                    continue
                if pet_friendly_req is not None and bool(option.get("pet_friendly")) != pet_friendly_req:
                    continue

                acc_obj = self._build_accommodation_option(option, check_in_date, check_out_date)
                if acc_obj:
                    matching_options.append(acc_obj)

            message = f"Found {len(matching_options)} accommodation options." if matching_options else "Search completed, but no options found."
            error = None if matching_options else f"No accessible accommodation options found for {tool_input.destination_city}, {tool_input.destination_country}."

            return AccessibleAccommodationOutput(
                accommodation_options=matching_options,
                message=message,
                error=error
            )
        except Exception as e:
            logging.error(f"Error during search: {e}", exc_info=True)
            return AccessibleAccommodationOutput(
                accommodation_options=[],
                message="Search failed due to unexpected error.",
                error=f"Exception: {str(e)}"
            )

    def _run(self, tool_input: AccessibleAccommodationInput) -> AccessibleAccommodationOutput:
        """Synchronous wrapper for asynchronous execution with error handling."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            nest_asyncio.apply()

        try:
            return loop.run_until_complete(self._arun(tool_input))
        except Exception as e:
            logging.error(f"Sync wrapper error: {e}")
            return AccessibleAccommodationOutput(
                accommodation_options=[],
                message="Search failed in sync wrapper.",
                error=f"Exception in _run: {str(e)}"
            )