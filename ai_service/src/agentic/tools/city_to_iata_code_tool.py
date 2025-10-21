# ai_service/src/agentic/tools/city_to_iata_code_tool.py
import sys
import asyncio
import nest_asyncio
import os
import requests
from pydantic import ValidationError
from typing import Optional, List, Type
from ..logger import logging
from ..exception import CustomException
from ..models import CityToIATACodeInput, CityToIATACodeOutput, AirportInfo 
from langchain_core.tools import BaseTool 

class CityToIATACodeTool(BaseTool):
    """
    A tool to convert city names to IATA airport codes using the Amadeus Airport & City Search API.
    This is crucial for flight search tools that require IATA codes.
    """
    name: str = "city_to_iata_code_converter"
    description: str = (
        """Useful for converting a city name into its corresponding IATA airport code(s) using Amadeus API.
        This tool is essential before calling flight search tools which require IATA codes.
        Input MUST be a JSON object conforming to CityToIATACodeInput schema with a 'city_name' key.
        Example: '{"city_name": "Kuala Lumpur"}'
        The tool returns a JSON object conforming to CityToIATACodeOutput schema, containing a list of AirportInfo objects (city_name, airport_name, iata_code, country_code).
        If multiple airports (including city codes) are found for a city, all relevant ones will be returned.
        """
    )
    args_schema: Type[CityToIATACodeInput] = CityToIATACodeInput

    _AMADEUS_API_KEY: Optional[str] = None
    _AMADEUS_API_SECRET: Optional[str] = None
    _AMADEUS_ACCESS_TOKEN: Optional[str] = None
    _TOKEN_EXPIRY_TIME: Optional[int] = None
    
    AMADEUS_AUTH_URL: str = "https://test.api.amadeus.com/v1/security/oauth2/token"
    AMADEUS_AIRPORT_SEARCH_URL: str = "https://test.api.amadeus.com/v1/reference-data/locations"

    def __init__(self, amadeus_api_key: Optional[str] = None, amadeus_api_secret: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        try:
            self._AMADEUS_API_KEY = amadeus_api_key if amadeus_api_key else os.getenv("AMADEUS_API_KEY")
            self._AMADEUS_API_SECRET = amadeus_api_secret if amadeus_api_secret else os.getenv("AMADEUS_API_SECRET")

            if not self._AMADEUS_API_KEY or not self._AMADEUS_API_SECRET:
                logging.error("AMADEUS_API_KEY or AMADEUS_API_SECRET environment variables not set or not provided.")
                raise ValueError("Amadeus API credentials not set or not provided for CityToIATACodeTool.")
            
            logging.info("CityToIATACodeTool initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize CityToIATACodeTool: {e}", exc_info=True)
            raise CustomException(sys, e)

    async def _get_amadeus_access_token(self) -> str:
        """
        Fetches or refreshes the Amadeus access token.
        This is a shared utility, similar to SearchFlightsTool.
        """
        if self._AMADEUS_ACCESS_TOKEN and self._TOKEN_EXPIRY_TIME and self._TOKEN_EXPIRY_TIME > (asyncio.get_event_loop().time() + 60):
            logging.info("Using existing Amadeus access token for CityToIATACodeTool.")
            return self._AMADEUS_ACCESS_TOKEN

        logging.info("Fetching new Amadeus access token for CityToIATACodeTool.")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "client_credentials",
            "client_id": self._AMADEUS_API_KEY,
            "client_secret": self._AMADEUS_API_SECRET
        }

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self.AMADEUS_AUTH_URL, headers=headers, data=data, timeout=10)
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._AMADEUS_ACCESS_TOKEN = token_data["access_token"]
            self._TOKEN_EXPIRY_TIME = asyncio.get_event_loop().time() + token_data["expires_in"]
            
            logging.info("Successfully fetched Amadeus access token for CityToIATACodeTool.")
            return self._AMADEUS_ACCESS_TOKEN
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to get Amadeus access token for CityToIATACodeTool: {e}", exc_info=True)
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_msg = e.response.json() if e.response is not None and e.response.content else str(e)
            raise CustomException(sys, f"Amadeus authentication failed for CityToIATACodeTool: Status {status_code}, Details: {error_msg}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during Amadeus token fetch for CityToIATACodeTool: {e}", exc_info=True)
            raise CustomException(sys, f"Unexpected error during Amadeus token fetch for CityToIATACodeTool: {e}")

    async def _arun(self, tool_input: CityToIATACodeInput) -> CityToIATACodeOutput:
        """
        Asynchronously converts a city name to its IATA airport code(s) using Amadeus API.
        """
        city_name = tool_input.city_name
        logging.info(f"Converting city name '{city_name}' to IATA code(s) via Amadeus API.")

        try:
            access_token = await self._get_amadeus_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            params = {
                "keyword": city_name,
                "subType": "CITY,AIRPORT", # Search for both cities and airports
                "view": "FULL", # Get full details
                "page[limit]": 10 # Limit results
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.AMADEUS_AIRPORT_SEARCH_URL, headers=headers, params=params, timeout=15)
            )
            response.raise_for_status()
            json_data = response.json()

            airports_info: List[AirportInfo] = []
            if "data" in json_data:
                for item in json_data["data"]:
                    # Filter for actual airports or cities with IATA codes
                    if item.get("iataCode") and (item.get("subType") == "AIRPORT" or item.get("subType") == "CITY"):
                        airports_info.append(
                            AirportInfo(
                                city_name=item.get("address", {}).get("cityName", item.get("name", "N/A")), # Use city name from address or item name
                                airport_name=item.get("name", "N/A"),
                                iata_code=item["iataCode"],
                                country_code=item.get("address", {}).get("countryCode", "N/A")
                            )
                        )
            
            if not airports_info:
                return CityToIATACodeOutput(
                    airports=[], 
                    error=f"No IATA codes found for city: '{city_name}' via Amadeus API. Please check the city name."
                )
            
            logging.info(f"Found {len(airports_info)} IATA codes for '{city_name}' via Amadeus API.")
            return CityToIATACodeOutput(airports=airports_info, error=None)

        except ValidationError as ve:
            logging.error(f"CityToIATACodeTool output validation failed: {ve}. Raw data: {json_data}", exc_info=True)
            return CityToIATACodeOutput(
                airports=[], 
                error=f"Amadeus API returned malformed data. Details: {ve}"
            )
        except requests.exceptions.RequestException as e:
            logging.error(f"HTTP request failed for CityToIATACodeTool: {e}", exc_info=True)
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_msg = e.response.json() if e.response is not None and e.response.content else str(e)
            return CityToIATACodeOutput(
                airports=[], 
                error=f"Failed to fetch IATA codes from Amadeus API. Status: {status_code}, Details: {error_msg}"
            )
        except CustomException as e: # Catch CustomException from token fetch
            logging.error(f"Amadeus token error during IATA lookup: {e}", exc_info=True)
            return CityToIATACodeOutput(
                airports=[], 
                error=f"Amadeus authentication failed, cannot lookup IATA codes. Details: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            )
        except Exception as e:
            logging.error(f"An unexpected error occurred in CityToIATACodeTool for city '{city_name}': {e}", exc_info=True)
            return CityToIATACodeOutput(
                airports=[], 
                error=f"An internal error occurred during IATA code lookup for '{city_name}'. Exception: {str(e)}"
            )

    def _run(self, tool_input: CityToIATACodeInput) -> CityToIATACodeOutput:
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
            return CityToIATACodeOutput(airports=[], error=f"Exception in _run: {str(e)}")