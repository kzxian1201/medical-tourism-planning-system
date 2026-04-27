# ai_service/test/tools/test_web_research_tool.py
import pytest
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure sys.path includes project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from ai_service.src.agentic.tools.web_research_tool import WebResearchTool
from ai_service.src.agentic.models import WebSearchRawResults, WebResearchToolInput
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper
from ai_service.src.agentic.exception import CustomException

@pytest.fixture(autouse=True)
def mock_logging():
    """Mock logging to suppress output in tests."""
    with patch("agentic.tools.web_research_tool.logging") as mock_log:
        yield mock_log

@pytest.fixture
def tool_with_mock_wrapper():
    """
    Fixture:
    Provides a WebResearchTool instance with a mocked GoogleSerperAPIWrapper.
    This allows simulating different API responses without real network calls.
    """
    mock_wrapper = MagicMock(spec=GoogleSerperAPIWrapper)
    tool = WebResearchTool(serper_api_key="dummy", serper_wrapper=mock_wrapper)
    return tool, mock_wrapper

@pytest.mark.asyncio
async def test_basic_search(tool_with_mock_wrapper):
    """
    Test case:
    Perform a basic search query and verify results are returned correctly.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="basic search test")

    mock_wrapper.results.return_value = {
        "search_parameters": {"q": "basic search test"},
        "organic_results": [{"title": "R1", "link": "http://1", "snippet": "S1"}],
    }

    result = await tool._arun(input_data)
    mock_wrapper.results.assert_called_once()
    assert isinstance(result, WebSearchRawResults)
    assert result.organic_results[0].title == "R1"
    assert result.error is None

@pytest.mark.asyncio
async def test_num_results(tool_with_mock_wrapper):
    """
    Test case:
    Verify that num_results parameter is correctly passed and applied.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="num test", num_results=3)

    mock_wrapper.results.return_value = {
        "search_parameters": {"q": "num test", "num": 3},
        "organic_results": [{"title": f"R{i}", "link": f"http://x{i}", "snippet": f"S{i}"} for i in range(3)],
    }

    result = await tool._arun(input_data)
    assert len(result.organic_results) == 3
    assert result.error is None

@pytest.mark.asyncio
async def test_gl_hl(tool_with_mock_wrapper):
    """
    Test case:
    Verify that gl (geolocation) and hl (language) parameters are passed correctly.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="de test", gl="de", hl="de")

    mock_wrapper.results.return_value = {
        "search_parameters": {"q": "de test", "gl": "de", "hl": "de"},
        "organic_results": [{"title": "German", "link": "http://de", "snippet": "Deutsch"}],
    }

    result = await tool._arun(input_data)
    assert result.search_parameters["gl"] == "de"
    assert result.search_parameters["hl"] == "de"

@pytest.mark.asyncio
async def test_exclude_sites(tool_with_mock_wrapper):
    """
    Test case:
    Verify that exclude_sites parameter is passed correctly to API.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="exclude test", exclude_sites=["wikipedia.org"])

    mock_wrapper.results.return_value = {
        "search_parameters": {"q": "exclude test", "excludeSites": ["wikipedia.org"]},
        "organic_results": [{"title": "Filtered", "link": "http://f", "snippet": "no wiki"}],
    }

    result = await tool._arun(input_data)
    assert "Filtered" in result.organic_results[0].title
    assert result.error is None

@pytest.mark.asyncio
async def test_time_period(tool_with_mock_wrapper):
    """
    Test case:
    Verify that time_period is mapped to 'tbs' parameter correctly.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="time test", time_period="past_day")

    mock_wrapper.results.return_value = {
        "search_parameters": {"q": "time test", "tbs": "qdr:d"},
        "organic_results": [{"title": "Today", "link": "http://t", "snippet": "fresh"}],
    }

    result = await tool._arun(input_data)
    assert result.search_parameters["tbs"] == "qdr:d"

@pytest.mark.asyncio
async def test_no_results(tool_with_mock_wrapper):
    """
    Test case:
    Simulate no search results returned.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="empty")

    mock_wrapper.results.return_value = {"search_parameters": {"q": "empty"}, "organic_results": []}
    result = await tool._arun(input_data)

    assert result.organic_results == []
    assert result.error is None

@pytest.mark.asyncio
async def test_api_error(tool_with_mock_wrapper):
    """
    Test case:
    Simulate an API error and verify the tool returns error information.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="fail")

    mock_wrapper.results.side_effect = Exception("API down")
    result = await tool._arun(input_data)

    assert "API down" in result.error

@pytest.mark.asyncio
async def test_output_validation_failure(tool_with_mock_wrapper):
    """
    Test case:
    Simulate malformed API response that fails Pydantic validation.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="bad response")

    mock_wrapper.results.return_value = {"organic_results": [{"title": "Missing fields"}]}
    result = await tool._arun(input_data)

    assert "validation failed" in result.error.lower()

def test_sync_run(tool_with_mock_wrapper):
    """
    Test case:
    Verify that synchronous _run wrapper executes correctly.
    """
    tool, mock_wrapper = tool_with_mock_wrapper
    input_data = WebResearchToolInput(query="sync test")

    mock_wrapper.results.return_value = {
        "search_parameters": {"q": "sync test"},
        "organic_results": [{"title": "Sync", "link": "http://s", "snippet": "run"}],
    }

    result = tool._run(input_data)
    assert isinstance(result, WebSearchRawResults)
    assert result.search_parameters["q"] == "sync test"

def test_empty_query_raises(tool_with_mock_wrapper):
    """
    Test case:
    Simulate an empty query input and expect error response.
    """
    tool, _ = tool_with_mock_wrapper
    bad_input = WebResearchToolInput(query="")

    result = asyncio.run(tool._arun(bad_input))
    assert "cannot be empty" in result.error.lower()

def test_missing_wrapper_raises():
    """
    Test case:
    Verify initialization fails if neither API key nor wrapper is provided.
    """
    with patch("os.getenv", return_value=None):
        with pytest.raises(CustomException):
            WebResearchTool()
