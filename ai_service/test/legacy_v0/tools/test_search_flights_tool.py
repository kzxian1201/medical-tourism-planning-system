# ai_service/test/tools/test_search_flights_tool.py
import os
import pytest
import nest_asyncio
import requests
from unittest.mock import patch
from datetime import datetime, timedelta

from ai_service.src.agentic.tools.search_flights_tool import SearchFlightsTool
from ai_service.src.agentic.models import SearchFlightsInput, SearchFlightsOutput
from ai_service.src.agentic.exception import CustomException

@pytest.fixture
def tool_instance(monkeypatch):
    # Set up a valid tool instance with fake env vars and access token
    monkeypatch.setenv("AMADEUS_API_KEY", "test_key")
    monkeypatch.setenv("AMADEUS_API_SECRET", "test_secret")

    tool = SearchFlightsTool()
    tool._AMADEUS_ACCESS_TOKEN = "mock_token"
    tool._TOKEN_EXPIRY_TIME = datetime.now() + timedelta(minutes=5)
    return tool

def test_missing_credentials(monkeypatch):
    """Test case: Initialization fails when env vars are missing"""
    monkeypatch.delenv("AMADEUS_API_KEY", raising=False)
    monkeypatch.delenv("AMADEUS_API_SECRET", raising=False)
    with pytest.raises(CustomException):
        SearchFlightsTool()

@pytest.mark.asyncio
async def test_valid_flight_search(tool_instance):
    """Test case: A normal successful search"""
    mock_response = {
        "data": [{
            "type": "flight-offer",
            "id": "1",
            "source": "GDS",
            "instantTicketingRequired": False,
            "oneWay": False,
            "lastTicketingDate": "2025-07-30",
            "lastTicketingDateTime": "2025-07-30T23:59:00",
            "numberOfBookableSeats": 5,
            "itineraries": [{
                "duration": "PT3H",
                "segments": [{
                    "id": "1",
                    "departure": {"iataCode": "KUL", "at": "2025-08-01T08:00:00"},
                    "arrival": {"iataCode": "SIN", "at": "2025-08-01T11:00:00"},
                    "carrierCode": "MH",
                    "number": "123",
                    "duration": "PT3H",
                    "numberOfStops": 0
                }]
            }],
            "price": {"total": "100.00", "currency": "USD", "base": "80.00"},
            "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": False},
            "travelerPricings": []
        }]
    }

    with patch("requests.get") as mock_get, patch("requests.post"):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        result = await tool_instance._arun(
            SearchFlightsInput(origin="KUL", destination="SIN", departure_date="2025-08-01")
        )

        assert isinstance(result, SearchFlightsOutput)
        assert len(result.flight_options) == 1
        assert result.flight_options[0].total_cost == "100.00"

@pytest.mark.asyncio
async def test_no_flights_found(tool_instance):
    """Test case: API returns empty data"""
    with patch("requests.get") as mock_get, patch("requests.post"):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": []}

        result = await tool_instance._arun(
            SearchFlightsInput(origin="AAA", destination="ZZZ", departure_date="2025-08-01")
        )
        assert isinstance(result, SearchFlightsOutput)
        assert len(result.flight_options) == 0

@pytest.mark.asyncio
async def test_specific_criteria_filtering(tool_instance):
    """Test case: Filtering by airline and time constraints"""
    with patch("requests.get") as mock_get, patch("requests.post"):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "data": [{
                "type": "flight-offer",
                "id": "2",
                "source": "GDS",
                "instantTicketingRequired": False,
                "oneWay": False,
                "lastTicketingDate": "2025-07-31",
                "lastTicketingDateTime": "2025-07-31T23:59:00",
                "numberOfBookableSeats": 4,
                "itineraries": [{
                    "duration": "PT2H",
                    "segments": [{
                        "id": "1",
                        "departure": {"iataCode": "KUL", "at": "2025-08-01T09:00:00"},
                        "arrival": {"iataCode": "SIN", "at": "2025-08-01T11:00:00"},
                        "carrierCode": "SQ",
                        "number": "456",
                        "duration": "PT2H",
                        "numberOfStops": 0
                    }]
                }],
                "price": {"total": "150.00", "currency": "USD", "base": "120.00"},
                "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": False},
                "travelerPricings": []
            }]
        }

        result = await tool_instance._arun(
            SearchFlightsInput(
                origin="KUL",
                destination="SIN",
                departure_date="2025-08-01",
                adults=2,
                travel_class="business",
                preferred_airlines=["SQ"],
                earliest_departure_time="08:00",
                latest_arrival_time="12:00"
            )
        )
        assert result.error is None
        assert result.flight_options[0].airline_names == "SQ"


@pytest.mark.asyncio
async def test_invalid_dates_pydantic():
    """
    Test case:
    Verify that Pydantic rejects invalid departure_date before hitting the API.
    """
    with pytest.raises(ValueError):
        SearchFlightsInput(origin="KUL", destination="SIN", departure_date="bad-date")

@pytest.mark.asyncio
async def test_api_error_handling(tool_instance):
    """Test case: Unexpected API failure"""
    with patch("requests.get") as mock_get, patch("requests.post"):
        mock_get.side_effect = Exception("API is down")

        result = await tool_instance._arun(
            SearchFlightsInput(origin="KUL", destination="SIN", departure_date="2025-08-01")
        )
        assert "API is down" in result.error

def test_pydantic_input_validation():
    """Test case: Input schema validation fails when required field missing"""
    with pytest.raises(Exception):
        SearchFlightsInput(destination="SIN", departure_date="2025-08-01")  # Missing origin

@pytest.mark.asyncio
async def test_pydantic_output_validation(tool_instance):
    """Test case: Malformed API response fails Pydantic validation"""
    with patch("requests.get") as mock_get, patch("requests.post"):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": [{}]}  # Missing required fields

        result = await tool_instance._arun(
            SearchFlightsInput(origin="KUL", destination="SIN", departure_date="2025-08-01")
        )
        assert result.error and "parse flight API response" in result.error

def test_sync_run_wrapper_handles_event_loop(monkeypatch):
    """Test case: Sync wrapper works when event loop is already running"""
    monkeypatch.setenv("AMADEUS_API_KEY", "dummy_key")
    monkeypatch.setenv("AMADEUS_API_SECRET", "dummy_secret")

    nest_asyncio.apply()

    tool = SearchFlightsTool()
    tool._AMADEUS_ACCESS_TOKEN = "mock_token"
    tool._TOKEN_EXPIRY_TIME = datetime.now() + timedelta(minutes=5)

    async def mock_arun(*args, **kwargs):
        return SearchFlightsOutput(flight_options=[], message="Mocked", error=None)

    tool._arun = mock_arun  # Patch the async function

    result = tool._run(SearchFlightsInput(origin="KUL", destination="SIN", departure_date="2025-08-01"))
    assert isinstance(result, SearchFlightsOutput)
    assert result.message == "Mocked"

def test_run_handles_runtime_error(monkeypatch):
    """Test case: Sync wrapper returns error when _arun fails"""
    monkeypatch.setenv("AMADEUS_API_KEY", "dummy_key")
    monkeypatch.setenv("AMADEUS_API_SECRET", "dummy_secret")

    tool = SearchFlightsTool()
    tool._AMADEUS_ACCESS_TOKEN = "mock_token"
    tool._TOKEN_EXPIRY_TIME = datetime.now() + timedelta(minutes=5)

    async def mock_arun(*args, **kwargs):
        raise RuntimeError("Simulated failure in _arun")

    tool._arun = mock_arun

    result = tool._run(SearchFlightsInput(origin="KUL", destination="SIN", departure_date="2025-08-01"))
    assert isinstance(result, SearchFlightsOutput)
    assert result.error
    assert "Simulated failure" in result.error

@pytest.mark.asyncio
async def test_token_refresh_success(monkeypatch):
    """Test case: Token expired → API call refreshes token successfully"""
    monkeypatch.setenv("AMADEUS_API_KEY", "test_key")
    monkeypatch.setenv("AMADEUS_API_SECRET", "test_secret")

    tool = SearchFlightsTool()
    tool._AMADEUS_ACCESS_TOKEN = "expired_token"
    tool._TOKEN_EXPIRY_TIME = datetime.now() - timedelta(minutes=1)  # Expired

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "new_token",
            "expires_in": 1800
        }

        token = await tool._get_amadeus_access_token()
        assert token == "new_token"
        assert tool._AMADEUS_ACCESS_TOKEN == "new_token"

@pytest.mark.asyncio
async def test_token_refresh_failure(monkeypatch):
    """Test case: Token expired → refresh attempt fails"""
    monkeypatch.setenv("AMADEUS_API_KEY", "test_key")
    monkeypatch.setenv("AMADEUS_API_SECRET", "test_secret")

    tool = SearchFlightsTool()
    tool._AMADEUS_ACCESS_TOKEN = "expired_token"
    tool._TOKEN_EXPIRY_TIME = datetime.now() - timedelta(minutes=1)  # Expired

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 401
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")

        with pytest.raises(CustomException):
            await tool._get_amadeus_access_token()

@pytest.mark.asyncio
async def test_airline_filter_excludes_flights():
    """
    Test case:
    API returns flights but none match preferred_airlines filter.
    Expected result: No flights returned.
    """
    with patch.dict(os.environ, {"AMADEUS_API_KEY": "dummy", "AMADEUS_API_SECRET": "dummy"}):
        tool_instance = SearchFlightsTool()

        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            # ✅ mock token
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "access_token": "dummy_access_token",
                "expires_in": 1800
            }

            # ✅ mock flights
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "data": [{
                    "id": "3",
                    "type": "flight-offer",
                    "source": "GDS",
                    "instantTicketingRequired": False,
                    "nonHomogeneous": False,
                    "oneWay": False,
                    "lastTicketingDate": "2025-07-31",
                    "lastTicketingDateTime": "2025-07-31T23:59:00",
                    "numberOfBookableSeats": 5,
                    "itineraries": [{
                        "duration": "PT2H",
                        "segments": [{
                            "id": "1",
                            "departure": {"iataCode": "KUL", "at": "2025-08-01T10:00:00"},
                            "arrival": {"iataCode": "SIN", "at": "2025-08-01T12:00:00"},
                            "carrierCode": "MH",  # mismatch
                            "number": "789",
                            "duration": "PT2H",
                            "numberOfStops": 0
                        }]
                    }],
                    "price": {"total": "200.00", "currency": "USD", "base": "150.00"},
                    "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": True},
                    "validatingAirlineCodes": ["MH"],
                    "travelerPricings": []
                }]
            }

            result = await tool_instance._arun(
                SearchFlightsInput(
                    origin="KUL", destination="SIN", departure_date="2025-08-01",
                    preferred_airlines=["SQ"]  # mismatch
                )
            )
            assert len(result.flight_options) == 0
            assert "Found 0 flight options" in result.message

@pytest.mark.asyncio
async def test_airline_filter_includes_only_matching():
    """
    Test case:
    API returns flights from multiple airlines but only preferred airline is included.
    Expected result: Only flights matching preferred airline(s) remain.
    """
    with patch.dict(os.environ, {"AMADEUS_API_KEY": "dummy", "AMADEUS_API_SECRET": "dummy"}):
        tool_instance = SearchFlightsTool()

        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            # ✅ mock token
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "access_token": "dummy_access_token",
                "expires_in": 1800
            }

            # ✅ mock flights
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "data": [
                    {
                        "id": "1",
                        "type": "flight-offer",
                        "source": "GDS",
                        "instantTicketingRequired": False,
                        "nonHomogeneous": False,
                        "oneWay": False,
                        "lastTicketingDate": "2025-07-31",
                        "lastTicketingDateTime": "2025-07-31T23:59:00",
                        "numberOfBookableSeats": 5,
                        "itineraries": [{
                            "duration": "PT2H",
                            "segments": [{
                                "id": "1",
                                "departure": {"iataCode": "KUL", "at": "2025-08-01T10:00:00"},
                                "arrival": {"iataCode": "SIN", "at": "2025-08-01T12:00:00"},
                                "carrierCode": "SQ",  # ✅ preferred
                                "number": "222",
                                "duration": "PT2H",
                                "numberOfStops": 0
                            }]
                        }],
                        "price": {"total": "300.00", "currency": "USD", "base": "250.00"},
                        "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": True},
                        "validatingAirlineCodes": ["SQ"],
                        "travelerPricings": []
                    },
                    {
                        "id": "2",
                        "type": "flight-offer",
                        "source": "GDS",
                        "instantTicketingRequired": False,
                        "nonHomogeneous": False,
                        "oneWay": False,
                        "lastTicketingDate": "2025-07-31",
                        "lastTicketingDateTime": "2025-07-31T23:59:00",
                        "numberOfBookableSeats": 5,
                        "itineraries": [{
                            "duration": "PT2H",
                            "segments": [{
                                "id": "2",
                                "departure": {"iataCode": "KUL", "at": "2025-08-01T15:00:00"},
                                "arrival": {"iataCode": "SIN", "at": "2025-08-01T17:00:00"},
                                "carrierCode": "MH",  # ❌ not preferred
                                "number": "333",
                                "duration": "PT2H",
                                "numberOfStops": 0
                            }]
                        }],
                        "price": {"total": "250.00", "currency": "USD", "base": "200.00"},
                        "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": True},
                        "validatingAirlineCodes": ["MH"],
                        "travelerPricings": []
                    }
                ]
            }

            result = await tool_instance._arun(
                SearchFlightsInput(
                    origin="KUL", destination="SIN", departure_date="2025-08-01",
                    preferred_airlines=["SQ"]
                )
            )
            assert len(result.flight_options) == 1
            assert result.flight_options[0].airline_names == "SQ"
            assert result.flight_options[0].segments[0].carrier_code == "SQ"
            assert "Found" in result.message

@pytest.mark.asyncio
async def test_multiple_flights_returned(tool_instance):
    """Test case: API returns multiple flights"""
    mock_response = {
        "data": [
            {
                "type": "flight-offer",
                "id": "1",
                "source": "GDS",
                "instantTicketingRequired": False,
                "oneWay": False,
                "lastTicketingDate": "2025-07-29",
                "lastTicketingDateTime": "2025-07-29T23:59:00",
                "numberOfBookableSeats": 5,
                "itineraries": [{
                    "duration": "PT3H",
                    "segments": [{
                        "id": "s1",
                        "departure": {"iataCode": "KUL", "at": "2025-08-01T08:00:00"},
                        "arrival": {"iataCode": "SIN", "at": "2025-08-01T11:00:00"},
                        "carrierCode": "MH",
                        "number": "111",
                        "duration": "PT3H",
                        "numberOfStops": 0
                    }]
                }],
                "price": {"total": "120.00", "currency": "USD", "base": "100.00"},
                "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": False},
                "travelerPricings": []
            },
            {
                "type": "flight-offer",
                "id": "2",
                "source": "GDS",
                "instantTicketingRequired": False,
                "oneWay": False,
                "lastTicketingDate": "2025-07-28",
                "lastTicketingDateTime": "2025-07-28T23:59:00",
                "numberOfBookableSeats": 2,
                "itineraries": [{
                    "duration": "PT1H",
                    "segments": [{
                        "id": "s2",
                        "departure": {"iataCode": "KUL", "at": "2025-08-01T09:00:00"},
                        "arrival": {"iataCode": "SIN", "at": "2025-08-01T10:00:00"},
                        "carrierCode": "SQ",
                        "number": "222",
                        "duration": "PT1H",
                        "numberOfStops": 0
                    }]
                }],
                "price": {"total": "180.00", "currency": "USD", "base": "150.00"},
                "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": False},
                "travelerPricings": []
            }
        ]
    }

    with patch("requests.get") as mock_get, patch("requests.post"):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        result = await tool_instance._arun(
            SearchFlightsInput(origin="KUL", destination="SIN", departure_date="2025-08-01")
        )

        assert len(result.flight_options) == 2
        assert {f.airline_names for f in result.flight_options} == {"MH", "SQ"}
