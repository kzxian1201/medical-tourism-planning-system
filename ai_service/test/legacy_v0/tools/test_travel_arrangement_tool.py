#ai_service/test/tools/test_travel_arrangement_tool.py
import logging
import pytest
from unittest.mock import patch, AsyncMock
from ai_service.src.agentic.tools.travel_arrangement_tool import TravelArrangementTool, CityToIATACodeTool, SearchFlightsTool, AccessibleAccommodationTool, GetWeatherDataTool
from langchain_core.language_models.fake import FakeListLLM
from ai_service.src.agentic.models import (
    TravelArrangementInput, TravelArrangementOutput,
    CityToIATACodeOutput, SearchFlightsOutput,
    AccessibleAccommodationOutput, GetWeatherDataOutput,
    FlightOptionSummary, AccommodationOption, WeatherData,
    WeatherAPIResponse,
    DayForecast, Astro, HourForecast, ForecastDay, Forecast, Location,
    Condition, CurrentWeather
)

# Configure logging for test output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

mock_weather_data_api_response = WeatherAPIResponse(
    location=Location(
        name="Singapore",
        region="Central Singapore",
        country="Singapore",
        lat=1.3521,
        lon=103.8198,
        tz_id="Asia/Singapore",
        localtime_epoch=1672531200,
        localtime="2025-07-28 10:00"
    ),
    current=CurrentWeather(
        temp_c=30.0,
        temp_f=86.0,
        is_day=1,
        condition=Condition(text="Sunny", icon="", code=1000),
        wind_mph=9.3,
        wind_kph=15.0,
        wind_degree=300,
        wind_dir="NW",
        pressure_mb=1010.0,
        pressure_in=29.83,
        precip_mm=0.0,
        precip_in=0.0,
        humidity=70,
        cloud=0,
        feelslike_c=35.0,
        feelslike_f=95.0,
        vis_km=10.0,
        vis_miles=6.0,
        uv=10.0,
        gust_mph=12.4,
        gust_kph=20.0
    ),
    forecast=Forecast(forecastday=[
        ForecastDay(
            date="2025-07-28",
            date_epoch=1672531200,
            day=DayForecast(
                maxtemp_c=31.0,
                maxtemp_f=87.8,
                mintemp_c=25.0,
                mintemp_f=77.0,
                avgtemp_c=28.0,
                avgtemp_f=82.4,
                maxwind_mph=9.3,
                maxwind_kph=15.0,
                totalprecip_mm=0.0,
                totalprecip_in=0.0,
                totalsnow_cm=0.0,
                avgvis_km=10.0,
                avgvis_miles=6.0,
                avghumidity=75.0,
                daily_will_it_rain=0,
                daily_chance_of_rain=0,
                daily_will_it_snow=0,
                daily_chance_of_snow=0,
                condition=Condition(text="Sunny", icon="", code=1000),
                uv=10.0
            ),
            astro=Astro(sunrise="07:00 AM", sunset="07:00 PM", moonrise="", moonset="", moon_phase="", moon_illumination="", is_moon_up=0, is_sun_up=1),
            hour=[
                HourForecast(
                    time_epoch=1672531200,
                    time="2025-07-28 10:00",
                    temp_c=30.0,
                    temp_f=86.0,
                    is_day=1,
                    condition=Condition(text="Sunny", icon="", code=1000),
                    wind_mph=6.2,
                    wind_kph=10.0,
                    wind_degree=300,
                    wind_dir="NW",
                    pressure_mb=1010.0,
                    pressure_in=29.83,
                    precip_mm=0.0,
                    precip_in=0.0,
                    humidity=70,
                    cloud=0,
                    feelslike_c=35.0,
                    feelslike_f=95.0,
                    windchill_c=30.0,
                    windchill_f=86.0,
                    heatindex_c=35.0,
                    heatindex_f=95.0,
                    dewpoint_c=20.0,
                    dewpoint_f=68.0,
                    will_it_rain=0,
                    chance_of_rain=0,
                    will_it_snow=0,
                    chance_of_snow=0,
                    vis_km=10.0,
                    vis_miles=6.0,
                    gust_mph=12.4,
                    gust_kph=20.0,
                    uv=10.0
                )
            ]
        )
    ])
)

@pytest.mark.asyncio
async def test_full_travel_plan_success():
        """
        Tests a complete, successful travel plan scenario where all sub-tools return valid data.
        The LLM is mocked to return a valid TravelArrangementOutput.
        """
        # Create valid mock outputs for sub-tools
        mock_iata_origin = CityToIATACodeOutput(airports=[{"iata_code": "KUL", "city_name": "Kuala Lumpur", "airport_name": "Kuala Lumpur International Airport", "country_code": "MY"}])
        mock_iata_destination = CityToIATACodeOutput(airports=[{"iata_code": "SIN", "city_name": "Singapore", "airport_name": "Changi Airport", "country_code": "SG"}])
    
        mock_flight_summary_1 = FlightOptionSummary(
            id="FLT1",
            total_cost="$300",
            currency="USD",
            duration="PT3H",
            layovers=0,
            segments_summary="KUL-SIN direct",
            segments=[{
                "from": "KUL",
                "to": "SIN",
                "duration": "PT3H",
                "departure_iata": "KUL",
                "arrival_iata": "SIN",
                "departure_time": "2025-07-27T10:00:00",
                "arrival_time": "2025-07-27T13:00:00",
                "carrier_code": "MH",
                "number": "123",
                "number_of_stops": 0
            }],
            airline_names="Malaysia Airlines"
        )
        mock_flight_summary_2 = FlightOptionSummary(
            id="FLT2",
            total_cost="$250",
            currency="USD",
            duration="PT5H",
            layovers=1,
            segments_summary="KUL-SIN 1 stop",
            segments=[{
                "from": "KUL",
                "to": "HKG",
                "duration": "PT2H",
                "departure_iata": "KUL",
                "arrival_iata": "HKG",
                "departure_time": "2025-07-27T10:00:00",
                "arrival_time": "2025-07-27T12:00:00",
                "carrier_code": "AK",
                "number": "456",
                "number_of_stops": 0
            }, {
                "from": "HKG",
                "to": "SIN",
                "duration": "PT3H",
                "departure_iata": "HKG",
                "arrival_iata": "SIN",
                "departure_time": "2025-07-27T14:00:00",
                "arrival_time": "2025-07-27T17:00:00",
                "carrier_code": "CX",
                "number": "789",
                "number_of_stops": 0
            }],
            airline_names="AirAsia, Cathay Pacific"
        )

        mock_flights = SearchFlightsOutput(
            flight_options=[mock_flight_summary_1.model_dump(), mock_flight_summary_2.model_dump()]
        )

        mock_accommodation = AccessibleAccommodationOutput(
            accommodation_options=[
                AccommodationOption(
                    id="ACC1",
                    name="Hotel Mock",
                    cost_per_night_usd="$100",
                    location="123 Mock St",
                    country="Singapore",
                    city="Singapore",
                    min_cost_per_night_usd=90.0,
                    max_cost_per_night_usd=110.0,
                    total_cost_estimate_usd="$500",
                    availability="Available",
                    notes="Accessible room available."
                ),
                AccommodationOption(
                    id="ACC2",
                    name="Inn Mock",
                    cost_per_night_usd="$80",
                    location="456 Test Ave",
                    country="Singapore",
                    city="Singapore",
                    min_cost_per_night_usd=75.0,
                    max_cost_per_night_usd=90.0,
                    total_cost_estimate_usd="$400",
                    availability="Limited availability",
                    notes="Requires prior notice for accessibility features."
                )
            ],
            error=None
        )

        mock_weather = GetWeatherDataOutput(weather_data=mock_weather_data_api_response, error=None)

        # Mock the LLM output that the tool will parse
        mock_llm_output = TravelArrangementOutput(
            flight_suggestions=[mock_flight_summary_1, mock_flight_summary_2],
            accommodation_suggestions=[
                AccommodationOption(
                    id="ACC1",
                    name="Hotel Mock",
                    cost_per_night_usd="$100",
                    location="123 Mock St",
                    country="Singapore",
                    city="Singapore",
                    min_cost_per_night_usd=90.0,
                    max_cost_per_night_usd=110.0,
                    total_cost_estimate_usd="$500",
                    availability="Available",
                    notes="Accessible room available."
                ),
                AccommodationOption(
                    id="ACC2",
                    name="Inn Mock",
                    cost_per_night_usd="$80",
                    location="456 Test Ave",
                    country="Singapore",
                    city="Singapore",
                    min_cost_per_night_usd=75.0,
                    max_cost_per_night_usd=90.0,
                    total_cost_estimate_usd="$400",
                    availability="Limited availability",
                    notes="Requires prior notice for accessibility features."
                )
            ],
            weather_info=WeatherData(city="Singapore", country="Singapore", date="2025-07-28", condition="Sunny", temperature_celsius=30, forecast="Sunny and warm."),
            visa_assistance_flag=False,
            message="Travel arrangements planned successfully.",
            error=None
        )

        with patch('ai_service.src.agentic.tools.travel_arrangement_tool.CityToIATACodeTool._arun', new_callable=AsyncMock) as mock_iata_arun, \
            patch('ai_service.src.agentic.tools.travel_arrangement_tool.SearchFlightsTool._arun', new_callable=AsyncMock) as mock_flights_arun, \
            patch('ai_service.src.agentic.tools.travel_arrangement_tool.AccessibleAccommodationTool._arun', new_callable=AsyncMock) as mock_accommodation_arun, \
            patch('ai_service.src.agentic.tools.travel_arrangement_tool.GetWeatherDataTool._arun', new_callable=AsyncMock) as mock_weather_arun:

            tool = TravelArrangementTool()
            tool._llm = FakeListLLM(responses=[
                mock_llm_output.model_dump_json()  # This returns a JSON string, which is valid
            ])
            tool._city_to_iata_code_tool = CityToIATACodeTool()
            tool._search_flights_tool = SearchFlightsTool()
            tool._accessible_accommodation_tool = AccessibleAccommodationTool()
            tool._get_weather_data_tool = GetWeatherDataTool()
            tool._web_research_tool = AsyncMock()

            # Set up the mocks for the _arun method on the *returned instance* of each mocked sub-tool
            async def iata_side_effect_success(city_name):
                if city_name == "Kuala Lumpur":
                    return mock_iata_origin
                elif city_name == "Singapore":
                    return mock_iata_destination
                return None

            mock_iata_arun.side_effect = iata_side_effect_success
            mock_flights_arun.return_value = mock_flights
            mock_accommodation_arun.return_value = mock_accommodation
            mock_weather_arun.return_value = mock_weather

            # Instantiate the tool. This will call the patched classes and return the mock instances.
             #tool = TravelArrangementTool()

            input_data = TravelArrangementInput(
                departure_city="Kuala Lumpur",
                departure_date="2025-07-27",
                destination_city="Singapore",
                destination_date="2025-07-28",
                is_accessible=True,
                patient_details="patient needs a wheelchair",
                estimated_return_date="2025-07-30",
                medical_destination_city="Singapore",
                medical_destination_country="Singapore",
                medical_departure_date="2025-07-27",
                check_in_date="2025-07-27",
                check_out_date="2025-07-28",
                star_rating_min=4,
                star_rating_max=5,
                flight_preferences=["direct flight"],
                accommodation_requirements=["wheelchair accessible room"],
                num_guests_medical_plan=2
            )
            
            response = await tool._arun(**input_data.model_dump())
            
            # Verify the response
            assert response.message == "Travel arrangements planned successfully."
            assert response.error is None
            assert len(response.flight_suggestions) == 2
            assert len(response.accommodation_suggestions) == 2

@pytest.mark.asyncio
async def test_search_flights_failure():
        """
        Tests the scenario where the flight search tool fails.
        The tool should return a fallback with an error message but potentially valid accommodation and weather info.
        """
        mock_iata_origin = CityToIATACodeOutput(airports=[{"iata_code": "KUL", "city_name": "Kuala Lumpur", "airport_name": "Kuala Lumpur International Airport", "country_code": "MY"}])
        mock_iata_destination = CityToIATACodeOutput(airports=[{"iata_code": "SIN", "city_name": "Singapore", "airport_name": "Changi Airport", "country_code": "SG"}])

        mock_accommodation = AccessibleAccommodationOutput(
            accommodation_options=[
                AccommodationOption(
                    id="ACC1",
                    name="Hotel Mock",
                    cost_per_night_usd="$100",
                    location="123 Mock St",
                    country="Singapore",
                    city="Singapore",
                    min_cost_per_night_usd=90.0,
                    max_cost_per_night_usd=110.0,
                    total_cost_estimate_usd="$500",
                    availability="Available",
                    notes="Accessible room available."
                )
            ],
            error=None
        )

        mock_weather = GetWeatherDataOutput(weather_data=mock_weather_data_api_response, error=None)

        with patch('ai_service.src.agentic.tools.travel_arrangement_tool.CityToIATACodeTool._arun', new_callable=AsyncMock) as mock_iata_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.SearchFlightsTool._arun', new_callable=AsyncMock) as mock_flights_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.AccessibleAccommodationTool._arun', new_callable=AsyncMock) as mock_accommodation_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.GetWeatherDataTool._arun', new_callable=AsyncMock) as mock_weather_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.WebResearchTool._arun', new_callable=AsyncMock) as mock_research_arun:

            tool = TravelArrangementTool()

            mock_iata_arun.side_effect = [mock_iata_origin, mock_iata_destination]
            mock_flights_arun.return_value = SearchFlightsOutput(flight_options=[], error="No flights found.")
            mock_accommodation_arun.return_value = mock_accommodation
            mock_weather_arun.return_value = mock_weather

            input_data = TravelArrangementInput(
                departure_city="Kuala Lumpur",
                departure_date="2025-07-27",
                destination_city="Singapore",
                destination_date="2025-07-28",
                is_accessible=True,
                patient_details="patient needs a wheelchair",
                estimated_return_date="2025-07-30",
                medical_destination_city="Singapore",
                medical_destination_country="Singapore",
                medical_departure_date="2025-07-27",
                check_in_date="2025-07-27",
                check_out_date="2025-07-28",
            )
            
            response = await tool._arun(**input_data.model_dump())

            # Verify the response
            assert response.message == "Travel planning could not be fully completed. Please review the provided options and error details."
            assert response.error is not None
            assert len(response.accommodation_suggestions) == 1

@pytest.mark.asyncio
async def test_iata_code_lookup_failure():
        """
        Tests the scenario where the CityToIATACodeTool fails for the destination city.
        This should prevent flight searches but allow other tools to run.
        """
        mock_iata_origin = CityToIATACodeOutput(airports=[{"iata_code": "KUL", "city_name": "Kuala Lumpur", "airport_name": "Kuala Lumpur International Airport", "country_code": "MY"}])
        mock_iata_destination_fail = CityToIATACodeOutput(airports=[], error="No IATA code found.")

        mock_accommodation = AccessibleAccommodationOutput(
            accommodation_options=[
                AccommodationOption(
                    id="ACC1",
                    name="Hotel Mock",
                    cost_per_night_usd="$100",
                    location="123 Mock St",
                    country="Singapore",
                    city="Singapore",
                    min_cost_per_night_usd=90.0,
                    max_cost_per_night_usd=110.0,
                    total_cost_estimate_usd="$500",
                    availability="Available",
                    notes="Accessible room available."
                )
            ],
            error=None
        )

        mock_weather = GetWeatherDataOutput(weather_data=mock_weather_data_api_response, error=None)

        with patch('ai_service.src.agentic.tools.travel_arrangement_tool.CityToIATACodeTool._arun', new_callable=AsyncMock) as mock_iata_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.SearchFlightsTool._arun', new_callable=AsyncMock) as mock_flights_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.AccessibleAccommodationTool._arun', new_callable=AsyncMock) as mock_accommodation_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.GetWeatherDataTool._arun', new_callable=AsyncMock) as mock_weather_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.WebResearchTool._arun', new_callable=AsyncMock) as mock_research_arun:

            tool = TravelArrangementTool()

            # Mock side_effect for the IATA tool to simulate a failure for the destination
            async def iata_side_effect(city_name):
                if city_name == "Kuala Lumpur":
                    return mock_iata_origin
                else:  # For Singapore, return the failure mock
                    return mock_iata_destination_fail
            
            mock_iata_arun.side_effect = iata_side_effect
            mock_flights_arun.return_value = SearchFlightsOutput(flight_options=[], error="No flights found.")
            mock_accommodation_arun.return_value = mock_accommodation
            mock_weather_arun.return_value = mock_weather

            input_data = TravelArrangementInput(
                departure_city="Kuala Lumpur",
                departure_date="2025-07-27",
                destination_city="Singapore",
                destination_date="2025-07-28",
                is_accessible=True,
                patient_details="patient needs a wheelchair",
                estimated_return_date="2025-07-30",
                medical_destination_city="Singapore",
                medical_destination_country="Singapore",
                medical_departure_date="2025-07-27",
                check_in_date="2025-07-27",
                check_out_date="2025-07-28",
            )
            
            response = await tool._arun(**input_data.model_dump())
            
            # Verify the response
            assert response.message == "Travel planning could not be fully completed. Please review the provided options and error details."
            assert response.flight_suggestions == []

@pytest.mark.asyncio
async def test_llm_returns_invalid_json():
        """
        Tests the tool's robustness when the internal LLM returns malformed JSON.
        The tool should fall back gracefully and provide a clear error message.
        """
        mock_iata_origin = CityToIATACodeOutput(airports=[{"iata_code": "KUL", "city_name": "Kuala Lumpur", "airport_name": "Kuala Lumpur International Airport", "country_code": "MY"}])
        mock_iata_destination = CityToIATACodeOutput(airports=[{"iata_code": "SIN", "city_name": "Singapore", "airport_name": "Changi Airport", "country_code": "SG"}])

        mock_flight_summary = FlightOptionSummary(
            id="FLT1",
            total_cost="$300",
            currency="USD",
            duration="PT3H",
            layovers=0,
            segments_summary="KUL-SIN direct",
            segments=[{
                "from": "KUL",
                "to": "SIN",
                "duration": "PT3H",
                "departure_iata": "KUL",
                "arrival_iata": "SIN",
                "departure_time": "2025-07-27T10:00:00",
                "arrival_time": "2025-07-27T13:00:00",
                "carrier_code": "MH",
                "number": "123",
                "number_of_stops": 0
            }],
            airline_names="Malaysia Airlines"
        )
        mock_flights = SearchFlightsOutput(flight_options=[mock_flight_summary.model_dump()])

        mock_accommodation = AccessibleAccommodationOutput(
            accommodation_options=[
                AccommodationOption(
                    id="ACC1",
                    name="Hotel Mock",
                    cost_per_night_usd="$100",
                    location="123 Mock St",
                    country="Singapore",
                    city="Singapore",
                    min_cost_per_night_usd=90.0,
                    max_cost_per_night_usd=110.0,
                    total_cost_estimate_usd="$500",
                    availability="Available",
                    notes="Accessible room available."
                )
            ],
            error=None
        )

        mock_weather = GetWeatherDataOutput(weather_data=mock_weather_data_api_response, error=None)

        with patch('ai_service.src.agentic.tools.travel_arrangement_tool.CityToIATACodeTool._arun', new_callable=AsyncMock) as mock_iata_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.SearchFlightsTool._arun', new_callable=AsyncMock) as mock_flights_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.AccessibleAccommodationTool._arun', new_callable=AsyncMock) as mock_accommodation_arun, \
             patch('ai_service.src.agentic.tools.travel_arrangement_tool.GetWeatherDataTool._arun', new_callable=AsyncMock) as mock_weather_arun:

            tool = TravelArrangementTool()

            tool._llm = FakeListLLM(responses=["This is not valid JSON and will cause an error."])
            
            mock_iata_arun.side_effect = [mock_iata_origin, mock_iata_destination]
            mock_flights_arun.return_value = mock_flights
            mock_accommodation_arun.return_value = mock_accommodation
            mock_weather_arun.return_value = mock_weather
            
            input_data = TravelArrangementInput(
                departure_city="Kuala Lumpur",
                departure_date="2025-07-27",
                destination_city="Singapore",
                destination_date="2025-07-28",
                is_accessible=True,
                patient_details="patient needs a wheelchair",
                estimated_return_date="2025-07-30",
                medical_destination_city="Singapore",
                medical_destination_country="Singapore",
                medical_departure_date="2025-07-27",
                check_in_date="2025-07-27",
                check_out_date="2025-07-28",
            )
            
            response = await tool._arun(**input_data.model_dump())

            # Verify the response
            assert response.message == "Travel planning could not be fully completed. Please review the provided options and error details."
            assert "LLM synthesis failed" in response.error
