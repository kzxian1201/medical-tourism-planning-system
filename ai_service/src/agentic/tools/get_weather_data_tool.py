# ai_service/src/agentic/tools/get_weather_data_tool.py
import sys
import asyncio
import nest_asyncio
import os
import re
import requests
from pydantic import ValidationError
from typing import Optional, Type
from ..logger import logging 
from ..exception import CustomException 
from ..models import GetWeatherDataInput, GetWeatherDataOutput, WeatherAPIResponse, Location, CurrentWeather, Forecast, Condition 
from langchain_core.tools import BaseTool

class GetWeatherDataTool(BaseTool): 
    """
    A tool to retrieve real-time and forecast weather data using WeatherAPI.com.
    It expects structured Pydantic input and returns structured Pydantic output.
    """
    name: str = "get_weather_data"
    description: str = (
        """Useful for retrieving weather forecast data for a specified destination and date (up to 14 days in the future for free tier).
        Input MUST be a JSON object conforming to GetWeatherDataInput schema with 'destination' (string, city or coordinate) and 'date' (string, YYYY-MM-DD) keys.
        Example: '{"destination": "London", "date": "2025-08-01"}'
        The tool returns a JSON object conforming to GetWeatherDataOutput schema, containing detailed weather information (location, current weather, and forecast for the requested date).
        """
    )
    args_schema: Type[GetWeatherDataInput] = GetWeatherDataInput 
    
    _WEATHER_API_KEY: Optional[str] = None
    WEATHER_API_BASE_URL: str = "http://api.weatherapi.com/v1"

    def __init__(self, weather_api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        try:
            self._WEATHER_API_KEY = weather_api_key if weather_api_key else os.getenv("WEATHER_API_KEY")
            if not self._WEATHER_API_KEY:
                logging.error("WEATHER_API_KEY environment variable not set or not provided.")
                raise ValueError("WEATHER_API_KEY environment variable not set or not provided.")
            logging.info("GetWeatherDataTool initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize GetWeatherDataTool: {e}", exc_info=True)
            raise CustomException(sys, e)

    async def _arun(self, tool_input: GetWeatherDataInput) -> GetWeatherDataOutput:
        """
        Asynchronously fetches real weather data from WeatherAPI.com.
        """
        destination = tool_input.destination
        date = tool_input.date

        logging.info(f"Executing real weather data retrieval for destination: '{destination}', date: '{date}'.")

        try:
            if not destination or not date:
                # Return a structured error output
                return GetWeatherDataOutput(
                    weather_data=WeatherAPIResponse(
                        location=Location(name="N/A", region="N/A", country="N/A", lat=0.0, lon=0.0, tz_id="N/A", localtime_epoch=0, localtime="N/A"),
                        current=CurrentWeather(temp_c=0.0, temp_f=0.0, is_day=0, condition=Condition(text="N/A", icon="N/A", code=0), wind_mph=0.0, wind_kph=0.0, wind_degree=0, wind_dir="N/A", pressure_mb=0.0, pressure_in=0.0, precip_mm=0.0, precip_in=0.0, humidity=0, cloud=0, feelslike_c=0.0, feelslike_f=0.0, vis_km=0.0, vis_miles=0.0, uv=0.0, gust_mph=0.0, gust_kph=0.0),
                        forecast=Forecast(forecastday=[])
                    ),
                    error="Missing 'destination' or 'date' parameter."
                )
            
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                 # Return a structured error output
                 return GetWeatherDataOutput(
                    weather_data=WeatherAPIResponse(
                        location=Location(name="N/A", region="N/A", country="N/A", lat=0.0, lon=0.0, tz_id="N/A", localtime_epoch=0, localtime="N/A"),
                        current=CurrentWeather(temp_c=0.0, temp_f=0.0, is_day=0, condition=Condition(text="N/A", icon="N/A", code=0), wind_mph=0.0, wind_kph=0.0, wind_degree=0, wind_dir="N/A", pressure_mb=0.0, pressure_in=0.0, precip_mm=0.0, precip_in=0.0, humidity=0, cloud=0, feelslike_c=0.0, feelslike_f=0.0, vis_km=0.0, vis_miles=0.0, uv=0.0, gust_mph=0.0, gust_kph=0.0),
                        forecast=Forecast(forecastday=[])
                    ),
                    error=f"Invalid date format: '{date}'. Expected YYYY-MM-DD format."
                 )

            params = {
                "key": self._WEATHER_API_KEY,
                "q": destination,
                "dt": date,
                "aqi": "no",
                "alerts": "no"
            }
            
            api_endpoint = f"{self.WEATHER_API_BASE_URL}/forecast.json"

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(api_endpoint, params=params, timeout=10)
            )
            response.raise_for_status()
            
            json_data = response.json()
            
            # Validate raw API response with Pydantic model
            parsed_data = WeatherAPIResponse(**json_data)
            
            logging.info(f"Real weather data fetched for '{destination}' on '{date}'.")
            
            # Return the structured Pydantic output
            return GetWeatherDataOutput(weather_data=parsed_data, error=None)

        except ValidationError as ve:
            logging.error(f"Failed to validate WeatherAPI response with Pydantic model for '{destination}, {date}': {ve}", exc_info=True)
            # Return a structured error output
            return GetWeatherDataOutput(
                weather_data=WeatherAPIResponse(
                    location=Location(name="N/A", region="N/A", country="N/A", lat=0.0, lon=0.0, tz_id="N/A", localtime_epoch=0, localtime="N/A"),
                    current=CurrentWeather(temp_c=0.0, temp_f=0.0, is_day=0, condition=Condition(text="N/A", icon="N/A", code=0), wind_mph=0.0, wind_kph=0.0, wind_degree=0, wind_dir="N/A", pressure_mb=0.0, pressure_in=0.0, precip_mm=0.0, precip_in=0.0, humidity=0, cloud=0, feelslike_c=0.0, feelslike_f=0.0, vis_km=0.0, vis_miles=0.0, uv=0.0, gust_mph=0.0, gust_kph=0.0),
                    forecast=Forecast(forecastday=[])
                ),
                error=f"Failed to parse weather API response due to data structure mismatch. Details: {ve}"
            )
        except requests.exceptions.RequestException as e:
            logging.error(f"HTTP request failed for get_weather_data: {e}", exc_info=True)
            status_code = e.response.status_code if e.response is not None else "N/A"
            error_msg = e.response.json() if e.response is not None and e.response.content else str(e)
            # Return a structured error output
            return GetWeatherDataOutput(
                weather_data=WeatherAPIResponse(
                    location=Location(name="N/A", region="N/A", country="N/A", lat=0.0, lon=0.0, tz_id="N/A", localtime_epoch=0, localtime="N/A"),
                    current=CurrentWeather(temp_c=0.0, temp_f=0.0, is_day=0, condition=Condition(text="N/A", icon="N/A", code=0), wind_mph=0.0, wind_kph=0.0, wind_degree=0, wind_dir="N/A", pressure_mb=0.0, pressure_in=0.0, precip_mm=0.0, precip_in=0.0, humidity=0, cloud=0, feelslike_c=0.0, feelslike_f=0.0, vis_km=0.0, vis_miles=0.0, uv=0.0, gust_mph=0.0, gust_kph=0.0),
                    forecast=Forecast(forecastday=[])
                ),
                error=f"Failed to fetch weather data from API. Status: {status_code}, Details: {error_msg}"
            )
        except Exception as e:
            logging.error(f"An unexpected error occurred during get_weather_data execution for '{destination}, {date}': {e}", exc_info=True)
            # Return a structured error output
            return GetWeatherDataOutput(
                weather_data=WeatherAPIResponse(
                    location=Location(name="N/A", region="N/A", country="N/A", lat=0.0, lon=0.0, tz_id="N/A", localtime_epoch=0, localtime="N/A"),
                    current=CurrentWeather(temp_c=0.0, temp_f=0.0, is_day=0, condition=Condition(text="N/A", icon="N/A", code=0), wind_mph=0.0, wind_kph=0.0, wind_degree=0, wind_dir="N/A", pressure_mb=0.0, pressure_in=0.0, precip_mm=0.0, precip_in=0.0, humidity=0, cloud=0, feelslike_c=0.0, feelslike_f=0.0, vis_km=0.0, vis_miles=0.0, uv=0.0, gust_mph=0.0, gust_kph=0.0),
                    forecast=Forecast(forecastday=[])
                ),
                error=f"An internal error occurred during weather data retrieval. Exception: {str(e)}"
            )

    def _run(self, tool_input: GetWeatherDataInput) -> GetWeatherDataOutput:
        """Synchronous wrapper for asynchronous execution with fallback and safety."""
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
            logging.error(f"An error occurred in synchronous run: {e}", exc_info=True)
            return GetWeatherDataOutput(
                weather_data=WeatherAPIResponse(
                    location=Location(name="N/A", region="N/A", country="N/A", lat=0.0, lon=0.0, tz_id="N/A", localtime_epoch=0, localtime="N/A"),
                    current=CurrentWeather(temp_c=0.0, temp_f=0.0, is_day=0,
                                        condition=Condition(text="N/A", icon="N/A", code=0),
                                        wind_mph=0.0, wind_kph=0.0, wind_degree=0, wind_dir="N/A",
                                        pressure_mb=0.0, pressure_in=0.0, precip_mm=0.0, precip_in=0.0,
                                        humidity=0, cloud=0, feelslike_c=0.0, feelslike_f=0.0,
                                        vis_km=0.0, vis_miles=0.0, uv=0.0, gust_mph=0.0, gust_kph=0.0),
                    forecast=Forecast(forecastday=[])
                ),
                error=f"Synchronous wrapper failed due to: {str(e)}"
            )