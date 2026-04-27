# ai_service/src/agentic/tools/search_flights_tool.py
import asyncio
import requests
from typing import List
from langchain_core.tools import tool
from ..logger import logging
from datetime import datetime
from ..models import SearchFlightsInput, SearchFlightsOutput, FlightOptionSummary, DataProvenance
from ..config import AppConfig

def _build_skyscanner_params(origin: str, dest: str, date: str, adults: int, kwargs: dict) -> dict:
    """Build Skyscanner API request parameters"""
    return {
        "placeIdFrom": f"{origin}-sky",
        "placeIdTo": f"{dest}-sky",
        "departDate": date,
        "adults": str(adults),
        "cabinClass": kwargs.get("travel_class", "ECONOMY") or "ECONOMY",
        "currency": kwargs.get("currency_code", "USD") or "USD"
    }

async def _fetch_skyscanner_data(params: dict, headers: dict) -> dict:
    """Fetch Skyscanner flight API data"""
    base_url = "https://sky-scanner3.p.rapidapi.com/web/flights/search-one-way"
    poll_url = "https://sky-scanner3.p.rapidapi.com/web/flights/search-incomplete"
    
    response = await asyncio.to_thread(requests.get, base_url, headers=headers, params=params, timeout=15)
    res_data = response.json()

    if res_data.get("data", {}).get("context", {}).get("status") == "incomplete":
        session_id = res_data["data"]["context"].get("sessionId")
        await asyncio.sleep(2)
        poll_res = await asyncio.to_thread(requests.get, poll_url, headers=headers, params={"sessionId": session_id})
        res_data = poll_res.json()
        
    return res_data

def _parse_skyscanner_results(res_data: dict, max_results: int, origin: str, dest: str, currency: str) -> List[FlightOptionSummary]:
    """Parse Skyscanner API response to extract flight options"""
    itineraries = res_data.get("data", {}).get("itineraries", {}).get("results", [])
    parsed_options = []
    
    for item in itineraries[:max_results]:
        raw_price = item.get("price", {}).get("raw", 500)
        leg = item.get("legs", [{}])[0]
        stop_count = leg.get("stopCount", 0)
        stops_str = "Direct" if stop_count == 0 else f"{stop_count} stops"
        carrier = leg.get("carriers", {}).get("marketing", [{}])[0].get("name", "Unknown Airline")
        
        parsed_options.append(FlightOptionSummary(
            id=f"FLIGHT_{item.get('id')}",
            total_cost=f"{raw_price:.2f}",
            currency=currency,
            duration=f"{leg.get('durationInMinutes', 0)}m",
            airline_names=carrier,
            layovers_description=stops_str,
            segments=[],
            segments_summary=f"{origin}-{dest} ({stops_str})",
            provenance=DataProvenance(source="Skyscanner Live", is_mock_data=False)
        ))
    return parsed_options

def create_search_flights_tool(config: AppConfig):
    """[Factory] Creates the Flight Search Tool using Skyscanner API via RapidAPI."""

    @tool("search_flights_tool", args_schema=SearchFlightsInput)
    async def search_flights(origin: str, destination: str, departure_date: str, adults: int = 1, **kwargs) -> SearchFlightsOutput:
        """Search for real-time flights using Skyscanner's engine."""
        logging.info(f"✈️ Flight Search: {origin}->{destination} on {departure_date} for {adults} pax (Env: {config.environment})")
        
        # Check for airline schedule horizon (typically 330 days)
        try:
            dep_dt = datetime.strptime(departure_date, "%Y-%m-%d")
            days_ahead = (dep_dt - datetime.now()).days
            if days_ahead > 330:
                logging.warning(f"⏳ Horizon Limit Reached: {days_ahead} days ahead.")
                # directly returns a descriptive error without triggering a real API network request
                return SearchFlightsOutput(
                    flight_options=[],
                    error=f"Airlines do not publish schedules more than 330 days in advance (Requested: {days_ahead} days ahead)."
                )
        except ValueError:
            pass # If the date format is incorrect, allow it to proceed to the next step for processing

        rapid_api_key = config.api.rapid_api_key
        cookie = config.api.skyscanner_cookie

        if not rapid_api_key:
            return SearchFlightsOutput(flight_options=[], error="Configuration Error: RapidAPI Key missing.")

        params = _build_skyscanner_params(origin, destination, departure_date, adults, kwargs)
        
        if cookie:
            params["cookie"] = cookie

        headers = {
            "X-RapidAPI-Key": rapid_api_key,
            "X-RapidAPI-Host": "sky-scanner3.p.rapidapi.com"
        }

        try:
            res_data = await _fetch_skyscanner_data(params, headers)
            
            max_results = kwargs.get("max_results", 5)
            parsed_options = _parse_skyscanner_results(res_data, max_results, origin, destination, params["currency"])

            if not parsed_options:
                return SearchFlightsOutput(flight_options=[], message=f"No actual flights found for {origin} to {destination} on {departure_date}.")

            return SearchFlightsOutput(flight_options=parsed_options, message="Success")

        except Exception as e:
            logging.error(f"Flight API Fail: {e}")
            return SearchFlightsOutput(flight_options=[], error=f"Flight API unavailable: {str(e)}")

    return search_flights