# ai_service/test/tools/test_get_weather_data_tool.py
import pytest
import os
from unittest.mock import patch
from ai_service.src.agentic.tools.get_weather_data_tool import GetWeatherDataTool
from ai_service.src.agentic.models import (GetWeatherDataInput, GetWeatherDataOutput, WeatherAPIResponse, Location, CurrentWeather, Forecast, Condition)
from ai_service.src.agentic.exception import CustomException

# ---- Mocking valid API response ----
mock_valid_api_response = {
    "location": {
        "name": "London", "region": "", "country": "UK",
        "lat": 51.52, "lon": -0.11, "tz_id": "Europe/London",
        "localtime_epoch": 1690000000, "localtime": "2025-08-01 12:00"
    },
    "current": {
        "temp_c": 23.0, "temp_f": 73.4, "is_day": 1,
        "condition": {"text": "Sunny", "icon": "//cdn.weatherapi.com/weather/64x64/day/113.png", "code": 1000},
        "wind_mph": 5.6, "wind_kph": 9.0, "wind_degree": 180, "wind_dir": "S",
        "pressure_mb": 1012.0, "pressure_in": 29.88, "precip_mm": 0.0, "precip_in": 0.0,
        "humidity": 45, "cloud": 0, "feelslike_c": 25.0, "feelslike_f": 77.0,
        "vis_km": 10.0, "vis_miles": 6.0, "uv": 7.0, "gust_mph": 10.0, "gust_kph": 16.0
    },
    "forecast": {
        "forecastday": []
    }
}

@pytest.fixture
def tool():
    """Fixture: Provide tool instance with mocked API key"""
    return GetWeatherDataTool(weather_api_key="mocked_key")

@patch("requests.get")
def test_valid_destination_and_date(mock_get, tool):
    """
    Test case: Valid destination and valid date.
    Expected: Weather data successfully returned with no errors.
    """
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = mock_valid_api_response
    input_data = GetWeatherDataInput(destination="London", date="2025-08-01")

    result = tool._run(tool_input=input_data)
    assert result.error is None
    assert result.weather_data.location.name == "London"
    assert result.weather_data.current.temp_c == 23.0

@patch("requests.get")
def test_future_date_beyond_api_limit(mock_get, tool):
    """
    Test case: Date is too far in the future (API limitation).
    Expected: Structured error message returned.
    """
    mock_get.return_value.status_code = 400
    mock_get.return_value.json.return_value = {"error": {"message": "Date too far in future"}}
    input_data = GetWeatherDataInput(destination="London", date="2030-01-01")

    result = tool._run(tool_input=input_data)
    assert "Failed to parse weather API response" in result.error

@patch("requests.get")
def test_invalid_destination(mock_get, tool):
    """
    Test case: Invalid city or location.
    Expected: API returns error -> structured error message returned.
    """
    mock_get.return_value.status_code = 400
    mock_get.return_value.json.return_value = {"error": {"message": "No matching location found"}}
    input_data = GetWeatherDataInput(destination="InvalidCity", date="2025-08-01")

    result = tool._run(tool_input=input_data)
    assert "Failed to parse weather API response" in result.error

@patch("requests.get", side_effect=Exception("API crashed"))
def test_api_exception_handling(mock_get, tool):
    """
    Test case: requests.get throws an unexpected exception.
    Expected: Structured internal error message returned.
    """
    input_data = GetWeatherDataInput(destination="London", date="2025-08-01")
    result = tool._run(tool_input=input_data)
    assert "internal error" in result.error.lower()

def test_invalid_input_format(tool):
    """
    Test case: Invalid date format provided.
    Expected: Structured error indicating invalid date format.
    """
    input_data = GetWeatherDataInput(destination="London", date="invalid-date")
    result = tool._run(tool_input=input_data)
    assert "Invalid date format" in result.error

def test_missing_parameters(tool):
    """
    Test case: Empty destination and date.
    Expected: Structured error indicating missing parameters.
    """
    input_data = GetWeatherDataInput(destination="", date="")
    result = tool._run(tool_input=input_data)
    assert "Missing 'destination' or 'date'" in result.error

def test_pydantic_input_output_conformance():
    """
    Test case: Ensure Pydantic input/output schemas work correctly.
    """
    input_data = GetWeatherDataInput(destination="Paris", date="2025-08-01")
    assert isinstance(input_data, GetWeatherDataInput)

    current_dict = dict(mock_valid_api_response["current"])
    condition_data = current_dict.pop("condition")
    dummy_output = GetWeatherDataOutput(
        weather_data=WeatherAPIResponse(
            location=Location(**mock_valid_api_response["location"]),
            current=CurrentWeather(
                **current_dict,
                condition=Condition(**condition_data)
            ),
            forecast=Forecast(forecastday=[])
        ),
        error=None
    )
    assert isinstance(dummy_output, GetWeatherDataOutput)

def test_sync_run_wrapper_handles_event_loop(tool):
    """
    Test case: Validate synchronous wrapper handles event loop correctly.
    """
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_valid_api_response
        input_data = GetWeatherDataInput(destination="London", date="2025-08-01")

        result = tool._run(tool_input=input_data)
        assert result.error is None

def test_runtime_error_due_to_missing_key():
    """
    Test case: Initialize tool without API key in env or constructor.
    Expected: CustomException raised.
    """
    os.environ.pop("WEATHER_API_KEY", None)  # Ensure no env var
    with pytest.raises(CustomException) as exc:
        GetWeatherDataTool()
    assert "WEATHER_API_KEY environment variable not set" in str(exc.value)

def test_validation_error_handling(tool):
    """
    Test case: API response missing required fields, triggering ValidationError.
    Expected: Structured error returned.
    """
    bad_response = {"location": {"name": "Paris"}}  # Incomplete response
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = bad_response
        input_data = GetWeatherDataInput(destination="Paris", date="2025-08-01")

        result = tool._run(tool_input=input_data)
        assert "Failed to parse weather API response" in result.error
