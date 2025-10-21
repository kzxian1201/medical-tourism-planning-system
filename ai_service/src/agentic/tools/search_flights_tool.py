# ai_service/src/agentic/tools/search_flights_tool.py
import sys
import json
import asyncio
import nest_asyncio
import os
import requests
from pydantic import ValidationError
from typing import Optional, List, Type
import isoduration 
from datetime import datetime,timedelta
from ..logger import logging
from ..exception import CustomException
from ..models import (SearchFlightsInput, SearchFlightsOutput, FlightOptionSummary, FlightSegmentSummary,AmadeusFlightSearchResponse)
from langchain_core.tools import BaseTool

class SearchFlightsTool(BaseTool):
    """
    A tool to search for real flight details using the Amadeus Flight Offers Search API.
    It handles authentication and expects structured Pydantic input, returning structured Pydantic output.
    """
    name: str = "search_flights"
    description: str = (
        """Useful for searching for flight details between specified origins, destinations, and dates using Amadeus API.
        Input MUST be a JSON object conforming to SearchFlightsInput schema.
        Required fields: 'origin' (string, IATA airport code, e.g., "KUL"),
        'destination' (string, IATA airport code, e.g., "SIN"), and 'departure_date' (string, YYYY-MM-DD).
        Optional fields: 'return_date' (string, YYYY-MM-DD), 'adults' (integer, default 1),
        'children' (integer), 'infants' (integer), 'travel_class' (string, e.g., "ECONOMY", "BUSINESS", "FIRST"),
        'max_results' (integer, default 5), 'non_stop' (boolean), 'currency_code' (string, e.g., "USD"),
        'preferred_airlines' (list of strings, IATA codes, e.g., ["MH", "SQ"]),
        'max_layover_duration' (string, ISO 8601 duration, e.g., "PT3H" for 3 hours),
        'earliest_departure_time' (string, HH:MM, e.g., "08:00"),
        'latest_arrival_time' (string, HH:MM, e.g., "18:00").
        The tool returns a JSON object conforming to SearchFlightsOutput schema, containing a list of FlightOptionSummary.
        """
    )
    args_schema: Type[SearchFlightsInput] = SearchFlightsInput

    _AMADEUS_API_KEY: Optional[str] = None
    _AMADEUS_API_SECRET: Optional[str] = None
    _AMADEUS_ACCESS_TOKEN: Optional[str] = None
    _TOKEN_EXPIRY_TIME: Optional[datetime] = None

    # Constants for Amadeus API
    AMADEUS_TOKEN_URL: str = "https://test.api.amadeus.com/v1/security/oauth2/token" # Use test environment
    AMADEUS_FLIGHT_SEARCH_URL: str = "https://test.api.amadeus.com/v2/shopping/flight-offers" # Use test environment

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
        self._AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
        if not self._AMADEUS_API_KEY or not self._AMADEUS_API_SECRET:
            logging.error("AMADEUS_API_KEY or AMADEUS_API_SECRET not set in environment variables.")
            raise CustomException(sys, "Amadeus API credentials are not set.")

    async def _get_amadeus_access_token(self) -> str:
        """Retrieves or refreshes the Amadeus access token."""
        if self._AMADEUS_ACCESS_TOKEN and self._TOKEN_EXPIRY_TIME and datetime.now() < self._TOKEN_EXPIRY_TIME:
            return self._AMADEUS_ACCESS_TOKEN

        logging.info("Attempting to retrieve new Amadeus access token.")
        try:
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            data = {
                'grant_type': 'client_credentials',
                'client_id': self._AMADEUS_API_KEY,
                'client_secret': self._AMADEUS_API_SECRET
            }
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, # Use the default thread pool executor
                lambda: requests.post(self.AMADEUS_TOKEN_URL, headers=headers, data=data, timeout=10)
            )
            response.raise_for_status() # Raise an HTTPError for bad responses 
            token_data = response.json()
            self._AMADEUS_ACCESS_TOKEN = token_data['access_token']
            # Set expiry time a bit before actual expiry for buffer
            self._TOKEN_EXPIRY_TIME = datetime.now() + timedelta(seconds=token_data['expires_in'] - 60)
            logging.info("Successfully retrieved new Amadeus access token.")
            return self._AMADEUS_ACCESS_TOKEN
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to retrieve Amadeus access token: {e}", exc_info=True)
            raise CustomException(sys, f"Failed to retrieve Amadeus access token: {e}")
        except KeyError as e:
            logging.error(f"Amadeus token response missing key: {e}. Response: {response.text}", exc_info=True)
            raise CustomException(sys, f"Invalid Amadeus token response format: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during token retrieval: {e}", exc_info=True)
            raise CustomException(sys, f"An unexpected error occurred during Amadeus token retrieval: {e}")

    async def _arun(self, tool_input: SearchFlightsInput) -> SearchFlightsOutput:
        """
        Searches for real flight details using Amadeus Flight Offers Search API.
        Applies additional filtering for unsupported API parameters.
        """
        origin = tool_input.origin
        destination = tool_input.destination
        departure_date = tool_input.departure_date
        return_date = tool_input.return_date
        adults = tool_input.adults
        children = tool_input.children
        infants = tool_input.infants
        travel_class = tool_input.travel_class
        max_results = tool_input.max_results
        non_stop = tool_input.non_stop
        currency_code = tool_input.currency_code
        preferred_airlines = tool_input.preferred_airlines
        max_layover_duration = tool_input.max_layover_duration
        earliest_departure_time = tool_input.earliest_departure_time
        latest_arrival_time = tool_input.latest_arrival_time

        logging.info(f"Executing real flight search for: {origin} to {destination} on {departure_date}.")

        try:
            access_token = await self._get_amadeus_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            params = {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "returnDate": return_date,
                "adults": adults,
                "children": children,
                "infants": infants,
                "travelClass": travel_class.upper() if travel_class else "ECONOMY",
                "max": max_results, 
                "nonStop": non_stop,
                "currencyCode": currency_code
            }

            # --- Add new preference parameter to Amadeus API requests ---
            if preferred_airlines:
                # Amadeus API uses 'includedAirlineCodes' for preferred airlines
                params["includedAirlineCodes"] = ",".join(preferred_airlines)
                logging.info(f"Including preferred airlines: {preferred_airlines}")

            params = {k: v for k, v in params.items() if v is not None} # Remove None values

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, # Use the default thread pool executor
                lambda: requests.get(self.AMADEUS_FLIGHT_SEARCH_URL, headers=headers, params=params, timeout=30)
            )
            response.raise_for_status()

            json_data = response.json()
            parsed_amadeus_response = AmadeusFlightSearchResponse(**json_data)

            flight_options_summary: List[FlightOptionSummary] = []

            # --- Post-processing filtering logic ---
            # Parse max_layover_duration if provided
            max_layover_seconds = None
            if max_layover_duration:
                try:
                    max_layover_timedelta = isoduration.parse_duration(max_layover_duration)
                    max_layover_seconds = max_layover_timedelta.total_seconds()
                    logging.info(f"Parsed max_layover_duration to {max_layover_seconds} seconds.")
                except Exception as e:
                    logging.warning(f"Could not parse max_layover_duration '{max_layover_duration}': {e}. This filter will not be applied.", exc_info=True)
                    max_layover_seconds = None

            # Prepare for time filtering
            earliest_dep_minutes = None
            if earliest_departure_time:
                try:
                    h, m = map(int, earliest_departure_time.split(':'))
                    earliest_dep_minutes = h * 60 + m
                except ValueError as ve:
                    logging.warning(f"Invalid earliest_departure_time format '{earliest_departure_time}': {ve}. This filter will not be applied.")
                    earliest_dep_minutes = None

            latest_arr_minutes = None
            if latest_arrival_time:
                try:
                    h, m = map(int, latest_arrival_time.split(':'))
                    latest_arr_minutes = h * 60 + m
                except ValueError as ve:
                    logging.warning(f"Invalid latest_arrival_time format '{latest_arrival_time}': {ve}. This filter will not be applied.")
                    latest_arr_minutes = None

            for i, offer in enumerate(parsed_amadeus_response.data):
                if not offer.itineraries:
                    continue

                # ✅ Apply Preferred Airlines Filter (local filtering for test consistency)
                if preferred_airlines:
                    offer_airlines = {seg.carrierCode for seg in offer.itineraries[0].segments}
                    if not offer_airlines.intersection(preferred_airlines):
                        logging.debug(
                            f"Skipping offer {offer.id} because airlines {offer_airlines} "
                            f"do not match preferred {preferred_airlines}"
                        )
                        continue

                itinerary = offer.itineraries[0] # Assuming take the first itinerary for simplicity

                # 1. Apply Max Layover Duration Filter
                current_offer_layovers_ok = True
                if max_layover_seconds is not None and len(itinerary.segments) > 1:
                    for k in range(len(itinerary.segments) - 1):
                        arrival_time_str = itinerary.segments[k].arrival.get("at")
                        departure_time_str = itinerary.segments[k+1].departure.get("at")

                        if arrival_time_str and departure_time_str:
                            try:
                                # Amadeus dates are ISO 8601, often with Z for UTC. datetime.fromisoformat handles this.
                                arrival_dt = datetime.fromisoformat(arrival_time_str)
                                departure_dt = datetime.fromisoformat(departure_time_str)
                                layover_timedelta = departure_dt - arrival_dt
                                current_layover_seconds = layover_timedelta.total_seconds()

                                if current_layover_seconds < 0: 
                                    pass # will be caught by positive duration check
                                
                                if current_layover_seconds > max_layover_seconds:
                                    logging.debug(f"Skipping offer {offer.id} due to layover {current_layover_seconds}s > max {max_layover_seconds}s")
                                    current_offer_layovers_ok = False
                                    break
                            except ValueError as ve:
                                logging.warning(f"Error parsing date/time for layover calculation for offer {offer.id}: {ve}")
                                # If dates are malformed, can't reliably filter by layover, so don't skip based on this specific issue.
                        else:
                            logging.warning(f"Missing arrival/departure time for layover calculation in offer {offer.id}. Cannot apply layover filter reliably for this segment.")
                if not current_offer_layovers_ok:
                    continue # Skip this offer if layover exceeds max

                # 2. Apply Earliest Departure Time Filter
                if earliest_dep_minutes is not None:
                    first_segment = itinerary.segments[0]
                    flight_departure_time_str = first_segment.departure.get("at", "T00:00:00").split('T')[-1][:5]
                    try:
                        flight_dep_hour, flight_dep_minute = map(int, flight_departure_time_str.split(':'))
                        flight_dep_minutes = flight_dep_hour * 60 + flight_dep_minute
                        if flight_dep_minutes < earliest_dep_minutes:
                            logging.debug(f"Skipping offer {offer.id} due to early departure: {flight_departure_time_str} < {earliest_departure_time}")
                            continue # Skip this offer
                    except ValueError as ve:
                        logging.warning(f"Error parsing flight departure time '{flight_departure_time_str}' for offer {offer.id}: {ve}. Cannot apply earliest departure filter.")

                # 3. Apply Latest Arrival Time Filter
                if latest_arr_minutes is not None:
                    last_segment = itinerary.segments[-1]
                    flight_arrival_time_str = last_segment.arrival.get("at", "T23:59:59").split('T')[-1][:5]
                    try:
                        flight_arr_hour, flight_arr_minute = map(int, flight_arrival_time_str.split(':'))
                        flight_arr_minutes = flight_arr_hour * 60 + flight_arr_minute
                        if flight_arr_minutes > latest_arr_minutes:
                            logging.debug(f"Skipping offer {offer.id} due to late arrival: {flight_arrival_time_str} > {latest_arrival_time}")
                            continue # Skip this offer
                    except ValueError as ve:
                        logging.warning(f"Error parsing flight arrival time '{flight_arrival_time_str}' for offer {offer.id}: {ve}. Cannot apply latest arrival filter.")

                # If all filters pass, proceed to summarize
                segments_summary_list: List[FlightSegmentSummary] = []
                airline_names_set = set()

                for segment in itinerary.segments:
                    departure_time_str = segment.departure.get("at", "N/A").split("T")[-1][:5]
                    arrival_time_str = segment.arrival.get("at", "N/A").split("T")[-1][:5]

                    segments_summary_list.append(
                        FlightSegmentSummary(
                            departure_iata=segment.departure.get("iataCode", "N/A"),
                            arrival_iata=segment.arrival.get("iataCode", "N/A"),  
                            departure_time=departure_time_str,
                            arrival_time=arrival_time_str,
                            carrier_code=segment.carrierCode,
                            number=segment.number,
                            duration=segment.duration,
                            number_of_stops=segment.numberOfStops
                        )
                    )
                    airline_names_set.add(segment.carrierCode)

                segments_description = " -> ".join([f"{s.departure_iata}-{s.arrival_iata}" for s in segments_summary_list])
                total_stops = sum(s.numberOfStops for s in itinerary.segments)
                if total_stops > 0:
                    segments_description += f" ({total_stops} stop(s))"
                else:
                    segments_description += " (direct)"

                flight_options_summary.append(
                    FlightOptionSummary(
                        id=f"FLIGHT_OPT_{i+1}",
                        total_cost=offer.price.total,
                        currency=offer.price.currency,
                        duration=itinerary.duration,
                        layovers=total_stops, 
                        segments=segments_summary_list,
                        segments_summary=segments_description,
                        airline_names=", ".join(sorted(list(airline_names_set))), # Sort for consistent output
                        notes=f"Bookable seats: {offer.numberOfBookableSeats}. Last ticketing date: {offer.lastTicketingDate}"
                    )
                )

            # Apply max_results after all filtering
            final_flight_options = flight_options_summary[:max_results]

            logging.info(f"Real flight search completed for '{origin}' to '{destination}'. Found {len(final_flight_options)} options after filtering.")
            return SearchFlightsOutput(
                flight_options=final_flight_options,
                message=f"Search completed. Found {len(final_flight_options)} flight options.",
                error=None
            )

        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON input for search_flights: {e}", exc_info=True)
            return SearchFlightsOutput(flight_options=[], message="Search failed.", error=f"The input query is not a valid JSON string. Details: {e}")
        except ValidationError as e:
            logging.error(f"Failed to validate Amadeus API response with Pydantic model: {e}", exc_info=True)
            return SearchFlightsOutput(flight_options=[], message="Search failed.", error=f"Failed to parse flight API response due to data structure mismatch. Details: {e}")
        except requests.exceptions.RequestException as e:
            logging.error(f"HTTP request failed for search_flights: {e}", exc_info=True)
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_msg = e.response.json() if e.response is not None and e.response.content else str(e)
            return SearchFlightsOutput(flight_options=[], message="Search failed.", error=f"Failed to fetch flight data from API. Status: {status_code}, Details: {error_msg}")
        except CustomException as e:
            logging.error(f"Amadeus token error during flight search: {e}", exc_info=True)
            return SearchFlightsOutput(flight_options=[], message="Search failed.", error=f"Amadeus authentication failed, cannot search flights. Details: {e.error_message if hasattr(e, 'error_message') else str(e)}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during search_flights execution: {e}", exc_info=True)
            return SearchFlightsOutput(flight_options=[], message="Search failed.", error=f"An internal error occurred during flight search. Exception: {str(e)}")

    def _run(self, tool_input: SearchFlightsInput) -> SearchFlightsOutput:
        """
        Synchronous wrapper for asynchronous execution, robust across environments.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            nest_asyncio.apply()

        coroutine = self._arun(tool_input)

        try:
            return loop.run_until_complete(coroutine)
        except Exception as e:
            logging.error(f"Exception occurred in _run: {e}", exc_info=True)
            return SearchFlightsOutput(
                flight_options=[],
                message="Search failed.",
                error=f"Exception during synchronous execution: {str(e)}"
            )
    
    
