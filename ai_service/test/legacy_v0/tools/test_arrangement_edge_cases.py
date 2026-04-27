#ai_service/test/tools/test_arrangement_edge_cases.py
import pytest
import json
from datetime import datetime, timedelta
from pydantic import ValidationError
import asyncio
from ai_service.src.agentic.tools.travel_arrangement_tool import TravelArrangementTool
from ai_service.src.agentic.tools.city_to_iata_code_tool import CityToIATACodeTool
from ai_service.src.agentic.tools.search_flights_tool import SearchFlightsTool
from ai_service.src.agentic.tools.search_accessible_accommodation_tool import AccessibleAccommodationTool
from ai_service.src.agentic.tools.get_weather_data_tool import GetWeatherDataTool
from ai_service.src.agentic.tools.check_visa_requirements_tool import VisaRequirementsCheckerTool
from ai_service.src.agentic.models import (
    TravelArrangementInput,
    TravelArrangementOutput,
    CityToIATACodeOutput,
    AirportInfo,
    SearchFlightsOutput,
    FlightOptionSummary,
    AccessibleAccommodationOutput,
    AccommodationOption,
    GetWeatherDataOutput,
    WeatherAPIResponse,
    Location,
    Forecast,
    ForecastDay,
    DayForecast,
    Condition,
    Astro,
    WeatherData,
    WebSearchRawResults,
    VisaRequirementsOutput,
    VisaInfo,
    CurrentWeather
)
from typing import List, Any

def make_base_input():
    today = datetime.today()
    return {
        "departure_city": "Kuala Lumpur",
        "estimated_return_date": (today + timedelta(days=14)).strftime("%Y-%m-%d"),
        "medical_destination_city": "Bangkok",
        "medical_destination_country": "Thailand",
        "medical_departure_date": today.strftime("%Y-%m-%d"),
        "check_in_date": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
        "check_out_date": (today + timedelta(days=7)).strftime("%Y-%m-%d"),
        "num_guests_medical_plan": 1,
        "flight_preferences": ["direct flight"],
        "accommodation_requirements": ["near hospital"],
        "star_rating_min": 3,
        "star_rating_max": 5,
        "accessibility_needs": [],
        "nearby_landmarks": "Bangkok General Hospital",
        "with_kitchen_req": False,
        "pet_friendly_req": False,
        "visa_assistance_needed": True,
        "visa_information_from_medical_plan": None
    }

def make_minimal_current_weather():
    return CurrentWeather(
        temp_c=0.0,
        temp_f=32.0,
        is_day=1,
        condition=Condition(text="Unknown", icon="", code=0),
        wind_mph=0.0,
        wind_kph=0.0,
        wind_degree=0,
        wind_dir="N",
        pressure_mb=0.0,
        pressure_in=0.0,
        precip_mm=0.0,
        precip_in=0.0,
        humidity=0,
        cloud=0,
        feelslike_c=0.0,
        feelslike_f=32.0,
        vis_km=0.0,
        vis_miles=0.0,
        uv=0.0,
        gust_mph=0.0,
        gust_kph=0.0
    )

@pytest.mark.asyncio
async def test_same_city_departure_and_destination():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["medical_destination_city"] = input_data["departure_city"]
    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.error is not None
    assert not result.flight_suggestions
    assert not result.accommodation_suggestions
    assert any(
        keyword in result.error.lower()
        for keyword in ["same city", "invalid route", "iata code", "fallback"]
    )

@pytest.mark.asyncio
async def test_extreme_weather_destination():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["medical_destination_city"] = "Antarctica"
    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    if result.weather_info is None:
        assert result.error is not None
        assert "weather" in result.error.lower() or "fallback" in result.message.lower()
    else:
        assert result.weather_info.temperature_celsius < 0 or "cold" in result.weather_info.forecast.lower()

@pytest.mark.asyncio
async def test_invalid_or_missing_dates():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["medical_departure_date"] = "not-a-date"  # invalid date format

    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.error is not None
    assert "date" in result.error.lower() or "invalid" in result.message.lower()

@pytest.mark.asyncio
async def test_accommodation_with_no_accessibility():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["accessibility_needs"] = ["elevator", "wheelchair accessible room"]
    
    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.error is not None
    assert "accessible" in result.error.lower() or "no accessible accommodation" in result.message.lower()

@pytest.mark.asyncio
async def test_unrealistic_budget_expectation():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["accommodation_requirements"] = []
    input_data["star_rating_min"] = 5
    input_data["star_rating_max"] = 5
    input_data["with_kitchen_req"] = True
    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.accommodation_suggestions or result.error
    assert "fallback" in result.message.lower() or result.error

@pytest.mark.asyncio
async def test_all_subtools_fail(monkeypatch):
    async def fail_arun(*args, **kwargs):
        raise Exception("Simulated failure")

    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.CityToIATACodeTool._arun", fail_arun)
    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.SearchFlightsTool._arun", fail_arun)
    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.AccessibleAccommodationTool._arun", fail_arun)
    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.GetWeatherDataTool._arun", fail_arun)

    tool = TravelArrangementTool()
    input_model = TravelArrangementInput(**make_base_input())
    result = await tool._arun(**input_model.model_dump())

    assert result.flight_suggestions == []
    assert result.accommodation_suggestions == []
    assert result.weather_info is None
    assert result.error

@pytest.mark.asyncio
async def test_visa_info_pass_through_from_medical_plan():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["visa_assistance_needed"] = True
    input_data["visa_information_from_medical_plan"] = {
        "visa_required": True,
        "visa_type": "Medical Visa",
        "stay_duration_notes": "Up to 30 days",
        "required_documents": ["Passport", "Medical letter"],
        "processing_time_days": "7-10 business days",
        "notes": "Patient must apply in advance"
    }

    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.visa_assistance_flag is True
    if result.error:
        # fallback situation where visa information may not be structured
        assert isinstance(result.visa_information, (dict, VisaInfo)) or result.visa_information is None
    else:
        assert isinstance(result.visa_information, VisaInfo)


    # Optional: only if LLM output structured well
    if isinstance(result.visa_information, dict):  # Defensive
        assert "visa_type" in result.visa_information
        assert "Medical Visa" in result.visa_information["visa_type"]
    elif hasattr(result.visa_information, "visa_type"):
        assert "Medical Visa" in result.visa_information.visa_type
    else:
        # fallback string match
        assert "Medical Visa" in str(result.visa_information)

    assert hasattr(result.visa_information, "required_documents")
    assert "Passport" in result.visa_information.required_documents

@pytest.mark.asyncio
async def test_llm_returns_malformed_json(monkeypatch):
    tool = TravelArrangementTool()
    input_data = make_base_input()

    async def bad_llm_response(*args, **kwargs):
        class DummyMsg:
            content = "{this is not valid JSON"
        return DummyMsg()
    
    class DummySynthesisChain:
        async def ainvoke(self, *args, **kwargs):
            return await bad_llm_response()
    
    monkeypatch.setattr(
        "langchain_core.prompts.ChatPromptTemplate.from_messages",
        lambda msgs: DummySynthesisChain()
    )

    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.message.startswith("Travel planning could not be fully completed")
    assert result.error

def make_minimal_output():
    return {
        "medical_destination_city": "Bangkok",
        "flight_suggestions": [{
            "id": "FL001",
            "total_cost": 100.0,
            "currency": "USD",
            "duration": "PT2H30M",
            "layovers": 0,
            "segments": [{
                "departure_iata": "SIN",
                "arrival_iata": "BKK",
                "departure_time": "10:00",
                "arrival_time": "12:30",
                "duration": "PT2H30M",
                "carrier_code": "SQ",
                "number": "SQ123",
                "number_of_stops": 0
            }],
            "airline_names": "Singapore Airlines",
            "segments_summary": "SIN-BKK direct",
            "notes": None
        }],
        "accommodation_suggestions": [{
            "id": "ACC001",
            "name": "Bangkok Medical Hotel",
            "location": "Central Bangkok",
            "country": "Thailand",
            "city": "Bangkok",
            "min_cost_per_night_usd": 50.0,
            "max_cost_per_night_usd": 70.0,
            "total_cost_estimate_usd": 350.0,
            "accessibility_features": [],
            "availability": "Available",
            "notes": "Near hospital"
        }],
        "weather_info": {
            "city": "Bangkok",
            "country": "Thailand",
            "date": "2025-08-15",
            "condition": "Sunny",
            "forecast": [
                {"date": "2025-08-15", "condition": "Sunny"}
            ]
        },
        "visa_assistance_flag": False,
        "visa_information": None,
        "message": "Plan generated",
        "error": None
    }

class MinimalOutputChain:
    """返回合法的 TravelArrangementOutput JSON"""
    async def arun(self, *args, **kwargs):
        valid_output = TravelArrangementOutput(
            medical_destination_city="Bangkok",
            flight_suggestions=[
                FlightOptionSummary(
                    id="FL001",
                    total_cost=100.0,
                    currency="USD",
                    duration="PT2H30M",
                    layovers=0,
                    segments=[{
                        "departure_iata": "SIN",
                        "arrival_iata": "BKK",
                        "departure_time": "10:00",
                        "arrival_time": "12:30",
                        "duration": "PT2H30M",
                        "carrier_code": "SQ",
                        "number": "SQ123",
                        "number_of_stops": 0
                    }],
                    airline_names="Singapore Airlines",
                    segments_summary="SIN-BKK direct",
                    notes=None
                )
            ],
            accommodation_suggestions=[
                AccommodationOption(
                    id="ACC001",
                    name="Bangkok Medical Hotel",
                    location="Central Bangkok",
                    country="Thailand",
                    city="Bangkok",
                    min_cost_per_night_usd=50.0,
                    max_cost_per_night_usd=70.0,
                    total_cost_estimate_usd=350.0,
                    accessibility_features=[],
                    availability="Available",
                    notes="Near hospital"
                )
            ],
            weather_info=WeatherInfo(
                city="Bangkok",
                country="Thailand",
                date=datetime.today().strftime("%Y-%m-%d"),
                forecast="Sunny",
                temperature_c=30.0,
                precipitation_mm=0.0
            ),
            message="Minimal valid plan"
        )
        return valid_output.model_dump_json()
    
class FakeChain:
    async def arun(self, *args, **kwargs):
        return json.dumps({
            "flight_suggestions": [{"flight_number": "AZ657"}]  
        })
            
@pytest.mark.asyncio
async def test_all_optional_inputs_empty(monkeypatch):
    monkeypatch.setattr(
        "langchain_core.prompts.ChatPromptTemplate.from_messages",
        lambda *_, **__: MinimalOutputChain()
    )

    async def mock_async_city_to_iata(*a, **k):
        return CityToIATACodeOutput(
            airports=[AirportInfo(city_name="Singapore", airport_name="Changi Airport", iata_code="SIN", country_code="SG")],
            error=None
        )
    monkeypatch.setattr(CityToIATACodeTool, "_arun", mock_async_city_to_iata)

    async def mock_async_accommodation(*a, **k):
        return AccessibleAccommodationOutput(
            accommodation_options=[AccommodationOption(
                id="ACC001", name="Bangkok Medical Hotel", location="Central Bangkok",
                country="Thailand", city="Bangkok", min_cost_per_night_usd=50.0,
                max_cost_per_night_usd=70.0, total_cost_estimate_usd=350.0,
                accessibility_features=[], availability="Available", notes="Near hospital"
            )],
            error=None
        )
    monkeypatch.setattr(AccessibleAccommodationTool, "_arun", mock_async_accommodation)

    async def mock_async_flights(*a, **k):
        return SearchFlightsOutput(
            flight_options=[FlightOptionSummary(
                id="FL001", total_cost=100.0, currency="USD", duration="PT2H30M", layovers=0,
                segments=[{"departure_iata": "SIN", "arrival_iata": "BKK", "departure_time": "10:00",
                           "arrival_time": "12:30", "duration": "PT2H30M", "carrier_code": "SQ",
                           "number": "SQ123", "number_of_stops": 0}],
                airline_names="Singapore Airlines", segments_summary="SIN-BKK direct", notes=None
            )],
            error=None
        )
    monkeypatch.setattr(SearchFlightsTool, "_arun", mock_async_flights)

    async def mock_async_weather(*a, **k):
        return GetWeatherDataOutput(
            weather_data=WeatherAPIResponse(
                location=Location(
                    name="Bangkok", region="Bangkok", country="Thailand",
                    lat=13.75, lon=100.48, tz_id="Asia/Bangkok",
                    localtime_epoch=0, localtime="2025-08-15 10:00"
                ),
                current=make_minimal_current_weather(),
                forecast=Forecast(
                    forecastday=[
                        ForecastDay(
                            date="2025-08-15",
                            date_epoch=1723651200,
                            day=DayForecast(  
                                maxtemp_c=32.0, mintemp_c=25.0, avgtemp_c=28.5,
                                maxwind_kph=10.0, totalprecip_mm=0.0, avghumidity=70.0,
                                condition=Condition(text="Sunny", icon="//cdn.weatherapi.com/weather/64x64/day/113.png", code=1000)
                            ),
                            astro=Astro(sunrise="06:00 AM", sunset="06:30 PM", moon_phase="", moon_illumination="", moonrise="", moonset="")
                        )
                    ]
                )
            ),
            error=None
        )
    monkeypatch.setattr(GetWeatherDataTool, "_arun", mock_async_weather)

    async def mock_async_visa(*a, **k):
        return VisaRequirementsOutput(
            nationality="singaporean",
            destination_country="thailand",
            purpose="medical",
            visa_info=VisaInfo(visa_required=False, visa_type="Visa-Free",
                               stay_duration_notes="30 days", required_documents=[],
                               processing_time_days="N/A", notes="Visa-free entry"),
            error=None
        )
    monkeypatch.setattr(VisaRequirementsCheckerTool, "_arun", mock_async_visa)

    tool = TravelArrangementTool()
    today = datetime.today()
    tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    minimal_input = TravelArrangementInput(
        departure_city="Singapore",
        estimated_return_date=(today + timedelta(days=10)).strftime("%Y-%m-%d"),
        check_in_date=tomorrow,
        check_out_date=(today + timedelta(days=7)).strftime("%Y-%m-%d"),
        medical_destination_city="Bangkok",
        medical_destination_country="Thailand",
        medical_departure_date=tomorrow,
        num_guests_medical_plan=1
    )
    result = await tool._arun(**minimal_input.model_dump())
    assert result is not None
    assert result.error is None

@pytest.mark.asyncio
async def test_invalid_input_field_type():
    input_data = make_base_input()
    input_data["num_guests_medical_plan"] = "two"  # should be int
    with pytest.raises(ValidationError):
        TravelArrangementInput(**input_data)

class BadSchemaMsg:
        content = json.dumps({
            "medical_destination_city": "Bangkok",
            "flight_suggestions": "This should be a list",  
            "accommodation_suggestions": [{
                "id": "ACC001",
                "name": "Test Hotel",
                "location": "Central Bangkok",
                "country": "Thailand",
                "city": "Bangkok",
                "min_cost_per_night_usd": 50.0,
                "max_cost_per_night_usd": 70.0,
                "total_cost_estimate_usd": 350.0,
                "accessibility_features": [],
                "availability": "Available",
                "notes": "Near hospital"
            }],
            "weather_info": {
                "city": "Bangkok",
                "country": "Thailand",
                "date": "2025-08-15",
                "condition": "Sunny",
                "forecast": [
                    {"date": "2025-08-15", "condition": "Sunny"}
                ]
            },
            "visa_assistance_flag": False,
            "visa_information": None,
            "message": "Test message",
            "error": None
        })
    
@pytest.mark.asyncio
async def test_llm_output_invalid_schema(monkeypatch):
    # Mock synthesis chain
    monkeypatch.setattr(
        "langchain_core.prompts.ChatPromptTemplate.from_messages",
        lambda *_, **__: FakeChain()
    )

    monkeypatch.setattr(CityToIATACodeTool, "_arun", lambda *a, **k: asyncio.Future().set_result(
        CityToIATACodeOutput(
            airports=[AirportInfo(city_name="Kuala Lumpur", airport_name="KLIA", iata_code="KUL", country_code="MY")],
            error=None
        )
    ).result())
    monkeypatch.setattr(AccessibleAccommodationTool, "_arun", lambda *a, **k: asyncio.Future().set_result( AccessibleAccommodationOutput(
        accommodation_options=[AccommodationOption(
            id="ACC001", name="Test Hotel", location="Bangkok", country="Thailand", city="Bangkok",
            min_cost_per_night_usd=50.0, max_cost_per_night_usd=70.0, total_cost_estimate_usd=350.0,
            accessibility_features=[], availability="Available", notes=""
        )],
        error=None
    )).result())
    monkeypatch.setattr(SearchFlightsTool, "_arun", lambda *a, **k: SearchFlightsOutput(
        flight_options=[FlightOptionSummary(
            id="FL001", total_cost=100.0, currency="USD", duration="PT2H30M", layovers=0,
            segments=[{"departure_iata": "KUL", "arrival_iata": "BKK", "departure_time": "10:00",
                       "arrival_time": "12:30", "duration": "PT2H30M", "carrier_code": "TG",
                       "number": "TG123", "number_of_stops": 0}],
            airline_names="Thai Airways", segments_summary="KUL-BKK direct", notes=None
        )],
        error=None
    ))
    monkeypatch.setattr(GetWeatherDataTool, "_arun", lambda *a, **k: GetWeatherDataOutput(
        weather_data=WeatherAPIResponse(
            location=Location(name="Bangkok", region="Bangkok", country="Thailand",
                              lat=0, lon=0, tz_id="Asia/Bangkok",
                              localtime_epoch=0, localtime="2025-08-15 10:00"),
            current=make_minimal_current_weather(),
            forecast=Forecast(forecastday=[])
        ),
        error=None
    ))
    monkeypatch.setattr(VisaRequirementsCheckerTool, "_arun", lambda *a, **k: VisaRequirementsOutput(
        nationality="malaysian", destination_country="thailand",
        purpose="medical",
        visa_info=VisaInfo(visa_required=False, visa_type="Visa-Free",
                           stay_duration_notes="30 days", required_documents=[],
                           processing_time_days="N/A", notes="Visa-free entry"),
        error=None
    ))

    tool = TravelArrangementTool()
    result = await tool._arun(**TravelArrangementInput(**make_base_input()).model_dump())

    assert result.message.startswith("Travel planning could not be fully completed")
    assert "flight_suggestions" in result.error

@pytest.mark.asyncio
async def test_accommodation_no_results_but_no_error(monkeypatch):
    tool = TravelArrangementTool()
    input_data = make_base_input()

    class EmptyAccommodationOutput:
        accommodation_options = []
        error = None

    monkeypatch.setattr(
        "ai_service.src.agentic.tools.travel_arrangement_tool.AccessibleAccommodationTool._arun",
        lambda *_: EmptyAccommodationOutput()
    )

    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result is not None
    assert result.accommodation_suggestions == []
    assert result.message.lower().startswith("travel planning")

@pytest.mark.asyncio
async def test_visa_requested_but_no_info():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["visa_assistance_needed"] = True
    input_data["visa_information_from_medical_plan"] = None

    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.visa_assistance_flag is True
    assert result.visa_information is None or isinstance(result.visa_information, dict)
    assert result.message.lower().startswith("travel planning")

@pytest.mark.asyncio
async def test_partial_subtool_failure(monkeypatch):
    async def fail_flight(*args, **kwargs):
        raise Exception("Flights API failed")

    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.SearchFlightsTool._arun", fail_flight)

    tool = TravelArrangementTool()
    input_model = TravelArrangementInput(**make_base_input())
    result = await tool._arun(**input_model.model_dump())

    assert result.accommodation_suggestions is not None
    assert result.flight_suggestions == []
    assert result.error

@pytest.mark.asyncio
async def test_visa_required_but_info_missing():
    tool = TravelArrangementTool()
    input_data = make_base_input()
    input_data["visa_assistance_needed"] = True
    input_data["visa_information_from_medical_plan"] = None

    input_model = TravelArrangementInput(**input_data)
    result = await tool._arun(**input_model.model_dump())

    assert result.visa_assistance_flag is True
    assert result.visa_information is None
    assert result.error or "fallback" in result.message.lower()

@pytest.mark.asyncio
async def test_prompt_level_fallback_on_tool_failure(monkeypatch):
    async def fail_arun(*args, **kwargs): raise Exception("Tool failure")

    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.CityToIATACodeTool._arun", fail_arun)
    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.SearchFlightsTool._arun", fail_arun)
    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.AccessibleAccommodationTool._arun", fail_arun)
    monkeypatch.setattr("ai_service.src.agentic.tools.travel_arrangement_tool.GetWeatherDataTool._arun", fail_arun)

    tool = TravelArrangementTool()
    input_model = TravelArrangementInput(**make_base_input())
    result = await tool._arun(**input_model.model_dump())

    assert result.flight_suggestions == []
    assert result.accommodation_suggestions == []
    assert result.weather_info is None
    assert result.visa_information is None or isinstance(result.visa_information, dict)
    assert result.error and "failed" in result.error.lower()


