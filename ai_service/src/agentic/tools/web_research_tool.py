# ai_service/src/agentic/tools/web_research_tool.py
import asyncio
import json
import requests
from typing import Any, List, Optional, Tuple
from langchain_core.tools import tool
from ..logger import logging
from ..models import WebSearchRawResults, WebResearchToolInput
from datetime import datetime
from ..config import AppConfig

def _build_actual_query(query: str, exclude_sites: Optional[List[str]]) -> str:
    """Helper: Appends site exclusions to the query."""
    if not exclude_sites:
        return query
    exclusions = " ".join([f"-site:{site}" for site in exclude_sites])
    return f"{query} {exclusions}"

def _map_time_period(time_period: Optional[str]) -> Optional[str]:
    """Helper: Maps human readable time to Serper API time parameters."""
    if not time_period:
        return None
    time_map = {
        "past_hour": "qdr:h",
        "past_day": "qdr:d",
        "past_week": "qdr:w",
        "past_month": "qdr:m",
        "past_year": "qdr:y"
    }
    return time_map.get(time_period.lower(), time_period)

def _build_payload(query: str, num_results: int, gl: str, hl: Optional[str], tbs: Optional[str]) -> dict:
    """Helper: Constructs the JSON payload for the API."""
    payload = {"q": query, "num": num_results, "gl": gl}
    if hl:
        payload["hl"] = hl
    if tbs:
        payload["tbs"] = tbs
    return payload

def _extract_results(raw_result: dict, endpoint: str) -> Tuple[list, list]:
    """Helper: Safely extracts organic and news results based on endpoint type."""
    organic = raw_result.get("organic", []) if endpoint == "search" else []
    news = raw_result.get("news", [])
    return organic, news

def create_web_research_tool(config: AppConfig):
    """
    [Factory] Creates the Enhanced Web Research Tool using direct Serper API calls.
    Refactored to reduce Cognitive Complexity (< 15).
    """

    @tool("web_research_tool", args_schema=WebResearchToolInput)
    async def web_research(
        query: str,
        num_results: int = 10,
        gl: str = "my",
        hl: str = None,
        search_type: str = "search",
        exclude_sites: list[str] = None,
        time_period: str = None,
        **kwargs: Any
    ) -> WebSearchRawResults:
        """
        Perform web or news searches.
        Use search_type='news' for geopolitical risks, war, or current safety events.
        """
        api_key = config.api.serper_api_key
        if not api_key:
            logging.error("Missing SERPER_API_KEY environment variable.")
            return WebSearchRawResults(
                search_parameters={"query": query},
                error="Configuration Error: SERPER_API_KEY missing. Search disabled."
            )

        actual_query = _build_actual_query(query, exclude_sites)
        tbs = _map_time_period(time_period)
        payload = _build_payload(actual_query, num_results, gl, hl, tbs)
        
        endpoint = "news" if search_type and search_type.lower() == "news" else "search"
        url = f"https://google.serper.dev/{endpoint}"
        headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}

        try:
            logging.info(f"🔍 Searching Web [{endpoint.upper()}]: '{actual_query}' (Period: {tbs})")
            
            response = await asyncio.to_thread(
                requests.post, url, headers=headers, data=json.dumps(payload), timeout=15
            )
            response.raise_for_status()
            raw_result = response.json()
            
            organic, news = _extract_results(raw_result, endpoint)
            
            return WebSearchRawResults(
                search_parameters=payload,
                organic_results=organic,
                news_results=news,
                fetched_at=datetime.now().isoformat()
            )

        except Exception as e:
            logging.error(f"Web Search Error: {e}", exc_info=True)
            return WebSearchRawResults(
                search_parameters=payload,
                error=f"Search failed: {str(e)}"
            )

    return web_research