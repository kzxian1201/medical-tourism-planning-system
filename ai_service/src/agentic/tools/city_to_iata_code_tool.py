# ai_service/src/agentic/tools/city_to_iata_code_tool.py
import json
import asyncio
import urllib.request
from pathlib import Path
from typing import List
from langchain_core.tools import tool
from ..logger import logging
from ..models import CityToIATACodeInput, CityToIATACodeOutput, AirportInfo, DataProvenance
from ..config import AppConfig

AIRPORTS_JSON_URL = "https://raw.githubusercontent.com/jbrooksuk/JSON-Airports/master/airports.json"

def _ensure_offline_db_sync(cache_file: Path):
    """Download and cache the airports database (if not already cached)."""
    if not cache_file.exists():
        logging.info(f"📥 Downloading offline airports database to {cache_file}...")
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(AIRPORTS_JSON_URL, cache_file)
            logging.info("✅ Offline database ready.")
        except Exception as e:
            logging.error(f"Failed to download airports DB: {e}")

def _search_offline_db(city_name: str, cache_file: Path) -> List[AirportInfo]:
    """Search the local memory cache for airports by city name."""
    if not cache_file.exists():
        return []
        
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            airports_data = json.load(f)
    except Exception:
        return []

    search_term = city_name.lower().strip()
    results = []
    
    prov = DataProvenance(
        source="Offline Airports DB (Open Source)",
        confidence_score=1.0,
        is_mock_data=False
    )

    for apt in airports_data:
        apt_city = str(apt.get("city", "")).lower()
        apt_iata = apt.get("iata", "")
        
        if search_term in apt_city and apt_iata and apt_iata != "\\N":
            results.append(AirportInfo(
                city_name=apt.get("city", "Unknown"),
                airport_name=apt.get("name", "Unknown Airport"),
                iata_code=apt_iata,
                country_code=apt.get("country", "Unknown"),
                provenance=prov
            ))
            
            if len(results) >= 5:
                break
                
    return results

def create_city_to_iata_code_tool(config: AppConfig):
    """[Factory] Creates the City to IATA Code Tool using Offline Local Caching."""
    cache_file = config.storage.data_dir / "airports_offline_cache.json"

    @tool("city_to_iata_code_converter", args_schema=CityToIATACodeInput)
    async def city_to_iata_code_converter(city_name: str) -> CityToIATACodeOutput:
        """Useful for converting a city name into its IATA airport code(s) extremely fast."""
        logging.info(f"📍 Offline Lookup for city: {city_name}")
        try:
            # Explicitly pass the cache_file path
            await asyncio.to_thread(_ensure_offline_db_sync, cache_file)
            airports = await asyncio.to_thread(_search_offline_db, city_name, cache_file)
            
            if not airports:
                return CityToIATACodeOutput(airports=[], error=f"No airports found for {city_name}")
                
            return CityToIATACodeOutput(airports=airports)
            
        except Exception as e:
            logging.error(f"Offline IATA Lookup Error: {e}", exc_info=True)
            return CityToIATACodeOutput(airports=[], error=str(e))

    return city_to_iata_code_converter