# ai_service/src/agentic/tools/get_weather_data_tool.py
import asyncio
import requests
from langchain_core.tools import tool
from ..logger import logging
from ..models import GetWeatherDataInput, GetWeatherDataOutput, DataProvenance
from ..config import AppConfig

def create_get_weather_data_tool(config: AppConfig):
    """
    [Factory] Creates the Get Weather Data Tool.
    Retrieves real-time and forecast weather data using WeatherAPI.com.
    """
    GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    
    @tool("get_weather_data", args_schema=GetWeatherDataInput)
    async def get_weather_data(destination: str, date: str) -> GetWeatherDataOutput:
        """Get real-time weather forecasts based on actual city names.
        Automatically perform geographic coordinate transformation and return medically sensitive weather data including precipitation probability.
        """
        if config.environment == "development":
            logging.info(f"🌦️ [DEV MODE] Fetching real-time weather for: {destination}")

        try:
            # Real geocoding
            geo_res = await asyncio.to_thread(
                requests.get,
                GEO_URL,
                params={"name": destination, "count": 1},
                timeout=10
            )
            geo_data = geo_res.json().get("results", [])
            if not geo_data:
                raise ValueError(f"Could not locate city: {destination}")
            
            lat, lon = geo_data[0]["latitude"], geo_data[0]["longitude"]
            city_full = f"{geo_data[0].get('name')}, {geo_data[0].get('country')}"

            # Get real-time weather (Open-Meteo)
            weather_params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,rain_sum",
                "timezone": "auto"
            }
            weather_res = await asyncio.to_thread(requests.get, WEATHER_URL, params=weather_params)
            weather_data = weather_res.json()

            prov = DataProvenance(
                source=f"Open-Meteo Real-time (Location: {city_full})",
                source_url="https://open-meteo.com/",
                confidence_score=1.0,
                is_mock_data=False
            )
            
            return GetWeatherDataOutput(weather_data=weather_data, provenance=prov)

        except Exception as e:
            logging.error(f"Weather Tool Error: {e}")
            return GetWeatherDataOutput(weather_data={}, error=str(e))
            
    return get_weather_data