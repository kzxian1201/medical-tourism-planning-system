# ai_service/src/agentic/tools/web_research_tool.py
import sys
import asyncio
import os
from typing import Dict, Any, Optional, Type
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import ValidationError, PrivateAttr
from ..logger import logging
from ..exception import CustomException
from ..models import WebSearchRawResults, WebResearchToolInput

class WebResearchTool(BaseTool):
    """
    A pure tool for performing general web searches using the Google Serper API.
    It expects structured Pydantic input and returns structured Pydantic output.
    """
    name: str = "web_research_tool"
    description: str = (
        """Useful for performing general web searches to find information not available in internal databases.
        Input is a JSON object conforming to the WebResearchToolInput schema.
        Returns a JSON object conforming to the WebSearchRawResults schema, typically with 'organic_results' (list of dicts with 'title', 'link', 'snippet'), 'news_results', etc.
        For medical-related queries, consider excluding unreliable sources like Wikipedia using 'exclude_sites'.
        For timely information, use 'time_period' to restrict search results (e.g., 'past_year')."""
    )
    args_schema: Type[WebResearchToolInput] = WebResearchToolInput

    _serper_api_key: Optional[str] = PrivateAttr(default=None)
    _serper_wrapper: GoogleSerperAPIWrapper = PrivateAttr()

    def __init__(self, serper_api_key: Optional[str] = None, serper_wrapper: Optional[GoogleSerperAPIWrapper] = None, **kwargs):
        super().__init__(**kwargs)
        try:
            self._serper_api_key = serper_api_key if serper_api_key else os.getenv("SERPER_API_KEY")
            if not self._serper_api_key and serper_wrapper is None:
                logging.error("SERPER_API_KEY environment variable not set or not provided.")
                raise ValueError("SERPER_API_KEY environment variable not set or not provided.")

            self._serper_wrapper = serper_wrapper or GoogleSerperAPIWrapper(serper_api_key=self._serper_api_key)
            logging.info("WebResearchTool initialized with GoogleSerperAPIWrapper.")
        except Exception as e:
            logging.error(f"Failed to initialize WebResearchTool: {e}", exc_info=True)
            raise CustomException(sys, e)

    async def _arun(self, tool_input: WebResearchToolInput) -> WebSearchRawResults:
        """
        Performs a web search using the Serper API based on a structured Pydantic input.
        """
        logging.info(f"Executing web search for query: '{tool_input.query}'.")

        raw_search_results_dict: Dict[str, Any] = {}

        try:
            if not tool_input.query:
                raise ValueError("Query parameter cannot be empty.")

            serper_kwargs = {"q": tool_input.query}
            if tool_input.num_results is not None:
                serper_kwargs["num"] = tool_input.num_results
            if tool_input.gl:
                serper_kwargs["gl"] = tool_input.gl
            if tool_input.hl:
                serper_kwargs["hl"] = tool_input.hl

            if tool_input.search_type:
                serper_kwargs["tbm"] = tool_input.search_type
                logging.info(f"Using search_type: {tool_input.search_type} (mapped to tbm)")

            if tool_input.exclude_sites:
                serper_kwargs["excludeSites"] = tool_input.exclude_sites
                logging.info(f"Excluding sites from search: {', '.join(tool_input.exclude_sites)}")

            if tool_input.time_period:
                time_period_map = {
                    "past_hour": "qdr:h",
                    "past_day": "qdr:d",
                    "past_week": "qdr:w",
                    "past_month": "qdr:m",
                    "past_year": "qdr:y",
                }
                serper_tbs_value = time_period_map.get(tool_input.time_period.lower(), tool_input.time_period)
                serper_kwargs["tbs"] = serper_tbs_value
                logging.info(f"Restricting search to time period: {serper_tbs_value}")

            if self._serper_wrapper is None:
                raise CustomException(sys, "Serper API wrapper not initialized.")

            raw_search_results_dict = self._serper_wrapper.results(serper_kwargs)

            if "search_parameters" not in raw_search_results_dict:
                raw_search_results_dict["search_parameters"] = serper_kwargs
            if "organic_results" not in raw_search_results_dict:
                raw_search_results_dict["organic_results"] = []

            logging.info(f"Web search completed for '{tool_input.query}'. Results obtained.")

            return WebSearchRawResults(**raw_search_results_dict)

        except ValidationError as ve:
            logging.error(f"WebResearchTool output validation failed: {ve}. Raw dict: {raw_search_results_dict}", exc_info=True)
            return WebSearchRawResults(
                search_parameters={"query": tool_input.query},
                error=f"Web search returned malformed results or validation failed. Details: {ve}"
            )
        except Exception as e:
            logging.error(f"An error occurred during web_research_tool execution for '{tool_input.query}': {e}", exc_info=True)
            return WebSearchRawResults(
                search_parameters={"query": tool_input.query},
                error=f"An internal error occurred during web search for '{tool_input.query}'. Exception: {str(e)}"
            )

    def _run(self, tool_input: WebResearchToolInput) -> WebSearchRawResults:
        """Synchronous wrapper for asynchronous execution."""
        try:
            return asyncio.run(self._arun(tool_input))
        except RuntimeError as e:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self._arun(tool_input))