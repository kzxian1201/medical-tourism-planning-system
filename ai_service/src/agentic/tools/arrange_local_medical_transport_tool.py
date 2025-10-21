# ai_service/src/agentic/tools/arrange_local_medical_transport_tool.py
import sys
import json
import asyncio
import nest_asyncio
import os
from typing import Dict, Any, Optional, List, Type
from ..logger import logging
from ..exception import CustomException
from ..models import LocalMedicalTransportInput, LocalMedicalTransportOutput, TransportOption
from langchain_core.tools import BaseTool
from pydantic import ValidationError

class LocalMedicalTransportTool(BaseTool):
    """
    A tool to search for local medical transport services at a destination,
    such as wheelchair-accessible taxis, medical shuttles, or ambulance services.
    It retrieves structured data from a local JSON file.
    """
    name: str = "local_medical_transport_search"
    description: str = (
        """Useful for finding local medical transport options (e.g., wheelchair-accessible taxis, medical shuttles, ambulances) at a specific destination.
        Input MUST be a JSON object conforming to LocalMedicalTransportInput schema.
        Required fields: 'destination_city' (string) and 'destination_country' (string).
        Optional fields: 'transport_date' (YYYY-MM-DD), 'transport_purpose', 'transport_type', 'accessibility_needs'.
        Example: '{"destination_city": "Singapore", "destination_country": "Singapore", "transport_purpose": "hospital visits", "accessibility_needs": "wheelchair accessible"}'
        The tool returns a JSON object conforming to LocalMedicalTransportOutput schema, containing a list of matching transport options."""
    )
    args_schema: Type[LocalMedicalTransportInput] = LocalMedicalTransportInput

    _transport_data_file: str = ""
    _transport_options_db: List[Dict[str, Any]] = []

    def __init__(self, transport_data_file_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if transport_data_file_path:
            self._transport_data_file = transport_data_file_path
        else:
            _current_script_dir = os.path.dirname(os.path.abspath(__file__))
            self._transport_data_file = os.path.join(_current_script_dir, '..', '..', 'data', 'local_transport_options.json')

        self._transport_options_db = self._load_transport_data()
        logging.info(f"LocalMedicalTransportTool initialized with data from: {self._transport_data_file}")

    def _load_transport_data(self) -> List[Dict[str, Any]]:
        """
        Loads local medical transport data from the specified JSON file.
        """
        if not os.path.exists(self._transport_data_file):
            logging.error(f"Transport data file not found at: {self._transport_data_file}. Please ensure it exists.")
            raise FileNotFoundError(f"Transport data file not found at: {self._transport_data_file}")
        
        try:
            with open(self._transport_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logging.info("Local transport data loaded successfully.")
            return data
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from transport data file {self._transport_data_file}: {e}")
            raise ValueError(f"Invalid JSON format in transport data file: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading transport data: {e}")
            raise CustomException(sys, e)

    async def _arun(self, tool_input: LocalMedicalTransportInput) -> LocalMedicalTransportOutput:
        """
        Asynchronously searches for local medical transport options from the loaded data.
        """
        destination_city = tool_input.destination_city
        destination_country = tool_input.destination_country
        transport_date = tool_input.transport_date
        transport_purpose = tool_input.transport_purpose
        transport_type = tool_input.transport_type
        accessibility_needs = tool_input.accessibility_needs

        logging.info(f"Searching local medical transport for: {destination_city}, {destination_country} with needs: {accessibility_needs}.")
        
        matching_options: List[TransportOption] = []
        error_message: Optional[str] = None

        try:
            if not destination_city or not destination_country:
                return LocalMedicalTransportOutput(
                    transport_options=[],
                    message="Missing required parameters.",
                    error="Both destination_city and destination_country are required."
                )

            norm_city = destination_city.lower()
            norm_country = destination_country.lower()
            norm_transport_type = transport_type.lower() if transport_type else None
            norm_accessibility_needs = accessibility_needs.lower() if accessibility_needs else None

            for country_data in self._transport_options_db:
                if norm_country in country_data.get("country", "").lower() and norm_city in country_data.get("city", "").lower():
                    for option_data in country_data.get("options", []):
                        match = True
                        if norm_transport_type and norm_transport_type not in option_data.get("type", "").lower():
                            match = False
                        if norm_accessibility_needs:
                            found_accessibility_match = any(
                                norm_accessibility_needs in feature.lower()
                                for feature in option_data.get("accessibility_features", [])
                            )
                            if not found_accessibility_match:
                                match = False
                        if match:
                            try:
                                clean_data = {k: v for k, v in option_data.items() if k not in ("country", "city")}
                                matching_options.append(
                                    TransportOption(**clean_data, country=country_data["country"], city=country_data["city"])
                                )
                            except ValidationError as ve:
                                logging.warning(f"Skipping malformed transport option: {option_data}. Validation error: {ve}")
                                continue
            
            if not matching_options:
                error_message = f"No transport options found for {destination_city}, {destination_country} with your criteria."
                message = "Search completed but no results."
            else:
                message = f"Found {len(matching_options)} matching transport options."

            return LocalMedicalTransportOutput(
                transport_options=matching_options,
                message=message,
                error=error_message
            )

        except Exception as e:
            logging.error(f"Transport tool encountered error: {e}", exc_info=True)
            return LocalMedicalTransportOutput(
                transport_options=[],
                message="Search failed.",
                error=f"Internal error during search: {str(e)}"
            )
        
    def _run(self, tool_input: LocalMedicalTransportInput) -> LocalMedicalTransportOutput:
        """
        Synchronous wrapper for async _arun() with event loop fallback.
        """
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                nest_asyncio.apply()

            return loop.run_until_complete(self._arun(tool_input))

        except Exception as e:
            logging.error(f"Error occurred in synchronous run: {e}", exc_info=True)
            return LocalMedicalTransportOutput(
                transport_options=[],
                message="Synchronous execution failed.",
                error=f"Exception during _run(): {str(e)}"
            )
