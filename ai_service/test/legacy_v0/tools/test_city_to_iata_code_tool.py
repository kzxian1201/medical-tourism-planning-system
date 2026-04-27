# ai_service/test/tools/test_city_to_iata_code_tool.py
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from ai_service.src.agentic.tools.city_to_iata_code_tool import CityToIATACodeTool
from ai_service.src.agentic.models import CityToIATACodeInput, CityToIATACodeOutput, AirportInfo
from ai_service.src.agentic.exception import CustomException

@pytest.fixture
def tool():
    """Fixture: Provide initialized tool with valid token injected."""
    instance = CityToIATACodeTool(amadeus_api_key="mock_key", amadeus_api_secret="mock_secret")
    instance._AMADEUS_ACCESS_TOKEN = "mock_token"
    instance._TOKEN_EXPIRY_TIME = asyncio.get_event_loop().time() + 600  # Token still valid
    return instance

@pytest.mark.asyncio
async def test_valid_city_name(tool):
    """
    Test case:
    Provide a valid city name (Kuala Lumpur). Expect one valid AirportInfo returned.
    """
    mocked_response = {
        "data": [
            {
                "iataCode": "KUL",
                "subType": "AIRPORT",
                "name": "Kuala Lumpur International Airport",
                "address": {"cityName": "Kuala Lumpur", "countryCode": "MY"},
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mocked_response)
        result = await tool._arun(CityToIATACodeInput(city_name="Kuala Lumpur"))
        assert isinstance(result, CityToIATACodeOutput)
        assert result.error is None
        assert result.airports[0].iata_code == "KUL"

def test_run_returns_valid_result():
    """
    Test case:
    _run wrapper should return correct result when _arun is mocked.
    """
    tool = CityToIATACodeTool(amadeus_api_key="mock", amadeus_api_secret="mock")

    async def mock_arun(city_name: CityToIATACodeInput):
        return CityToIATACodeOutput(
            airports=[
                AirportInfo(
                    city_name="Kuala Lumpur",
                    airport_name="Kuala Lumpur International Airport",
                    iata_code="KUL",
                    country_code="MY",
                )
            ],
            error=None,
        )

    tool._arun = mock_arun
    result = tool._run(CityToIATACodeInput(city_name="Kuala Lumpur"))

    assert result.error is None
    assert result.airports[0].iata_code == "KUL"

@pytest.mark.asyncio
async def test_multiple_airports(tool):
    """
    Test case:
    Return multiple airports for London, expect both Heathrow and Gatwick in output.
    """
    mocked_response = {
        "data": [
            {"iataCode": "LHR", "subType": "AIRPORT", "name": "Heathrow", "address": {"cityName": "London", "countryCode": "GB"}},
            {"iataCode": "LGW", "subType": "AIRPORT", "name": "Gatwick", "address": {"cityName": "London", "countryCode": "GB"}},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mocked_response)
        result = await tool._arun(CityToIATACodeInput(city_name="London"))
        assert len(result.airports) == 2

@pytest.mark.asyncio
async def test_invalid_city_name(tool):
    """
    Test case:
    API returns empty list for invalid city, expect error message and no airports.
    """
    mocked_response = {"data": []}
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mocked_response)
        result = await tool._arun(CityToIATACodeInput(city_name="InvalidCity"))
        assert result.error
        assert result.airports == []

@pytest.mark.asyncio
async def test_api_error_handling(tool):
    """
    Test case:
    Simulate API exception (e.g., connection error). Expect error message returned.
    """
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("API is down")
        result = await tool._arun(CityToIATACodeInput(city_name="Kuala Lumpur"))
        assert result.error
        assert "API" in result.error or "Exception" in result.error

@pytest.mark.asyncio
async def test_pydantic_output_validation(tool):
    """
    Test case:
    API returns incomplete data missing required fields. Expect validation error.
    """
    mocked_response = {"data": [{}]}  # Missing required fields
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mocked_response)
        result = await tool._arun(CityToIATACodeInput(city_name="Test"))
        assert result.error

@pytest.mark.asyncio
async def test_token_refresh_when_expired():
    """
    Test case:
    Expired token should trigger refresh and store new token.
    """
    tool = CityToIATACodeTool(amadeus_api_key="mock_key", amadeus_api_secret="mock_secret")
    tool._TOKEN_EXPIRY_TIME = asyncio.get_event_loop().time() - 10  # expired

    token_response = {"access_token": "new_token", "expires_in": 1800}

    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: token_response)
        token = await tool._get_amadeus_access_token()
        assert token == "new_token"
        assert tool._AMADEUS_ACCESS_TOKEN == "new_token"

@pytest.mark.asyncio
async def test_token_reuse_when_valid():
    """
    Test case:
    If token is still valid, it should be reused without API call.
    """
    tool = CityToIATACodeTool(amadeus_api_key="mock_key", amadeus_api_secret="mock_secret")
    tool._AMADEUS_ACCESS_TOKEN = "valid_token"
    tool._TOKEN_EXPIRY_TIME = asyncio.get_event_loop().time() + 1000
    token = await tool._get_amadeus_access_token()
    assert token == "valid_token"

def test_run_handles_runtime_error():
    """
    Test case:
    _run should handle exceptions from _arun and return error in output.
    """
    tool = CityToIATACodeTool(amadeus_api_key="mock", amadeus_api_secret="mock")

    async def mock_arun(*args, **kwargs):
        raise RuntimeError("Simulated failure in _arun")

    tool._arun = mock_arun
    result = tool._run(CityToIATACodeInput(city_name="Kuala Lumpur"))

    assert isinstance(result, CityToIATACodeOutput)
    assert result.airports == []
    assert "Simulated failure" in result.error

@pytest.mark.asyncio
async def test_sync_run_wrapper_handles_event_loop():
    """
    Test case:
    Ensure _run works even if event loop is already running (nest_asyncio applied).
    """
    import nest_asyncio
    nest_asyncio.apply()
    tool = CityToIATACodeTool(amadeus_api_key="mock", amadeus_api_secret="mock")

    async def mock_arun(*args, **kwargs):
        return CityToIATACodeOutput(airports=[], error=None)

    tool._arun = mock_arun
    result = tool._run(CityToIATACodeInput(city_name="Kuala Lumpur"))
    assert isinstance(result, CityToIATACodeOutput)
    assert result.error is None

def test_missing_credentials_raises():
    """
    Test case:
    Initialization without API credentials should raise ValueError.
    """
    with patch("os.getenv", return_value=None):
        with pytest.raises(CustomException):
            CityToIATACodeTool()

@pytest.mark.asyncio
async def test_non_200_status_code(tool):
    """
    Test case:
    API returns HTTP 500. Expect error with status code included.
    """
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=500, json=lambda: {"error": "server error"})
        mock_get.return_value.raise_for_status.side_effect = Exception("500 Server Error")
        result = await tool._arun(CityToIATACodeInput(city_name="Paris"))
        assert result.error
        assert "500" in result.error or "Server" in result.error

@pytest.mark.asyncio
async def test_non_json_response(tool):
    """
    Test case:
    API response cannot be parsed as JSON. Expect error message.
    """
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.side_effect = ValueError("Not JSON")
        result = await tool._arun(CityToIATACodeInput(city_name="Tokyo"))
        assert result.error
        assert "JSON" in result.error or "parse" in result.error

@pytest.mark.asyncio
async def test_ignore_non_airport_city_entries(tool):
    """
    Test case:
    API returns entries without iataCode or wrong subtype, expect them ignored.
    """
    mocked_response = {
        "data": [
            {"subType": "RAILWAY", "name": "Some Train Station", "address": {"cityName": "Berlin", "countryCode": "DE"}},
            {"iataCode": "TXL", "subType": "AIRPORT", "name": "Berlin Tegel", "address": {"cityName": "Berlin", "countryCode": "DE"}},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mocked_response)
        result = await tool._arun(CityToIATACodeInput(city_name="Berlin"))
        assert len(result.airports) == 1
        assert result.airports[0].iata_code == "TXL"
