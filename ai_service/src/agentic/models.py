from pydantic import BaseModel, Field, field_validator, model_validator, RootModel, StringConstraints
from typing import List, Optional, Dict, Any, Union, Literal, Annotated
import re
from uuid import uuid4

# --- Web Research Tool Models ---
class WebSearchResult(BaseModel):
    """Represents a single organic search result from the web."""
    title: str = Field(..., description="Title of the search result.")
    link: str = Field(..., description="URL link of the search result.")
    snippet: str = Field(..., description="Brief snippet or description of the search result content.")

class WebSearchRawResults(BaseModel):
    """Schema for raw web search results, typically containing organic_results, news_results, etc."""
    search_parameters: Dict[str, Any] = Field(..., description="Parameters used for the search.")
    organic_results: List[WebSearchResult] = Field(default_factory=list, description="List of organic search results (raw dictionaries).")
    news_results: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="List of news search results (raw dictionaries).")
    error: Optional[str] = Field(None, description="Error message if the search failed.")

    @field_validator('organic_results', mode='before')
    @classmethod
    def convert_organic_results(cls, v):
        if isinstance(v, list) and all(isinstance(item, dict) for item in v):
            return [WebSearchResult(**item) for item in v]
        return v
    
class WebResearchToolInput(BaseModel):
    query: str = Field(..., description="The search query string.")
    num_results: Optional[int] = Field(default=10, description="Number of results to retrieve.")
    gl: Optional[str] = Field("my", description="Geographical location for search (e.g., 'us', 'uk').") 
    hl: Optional[str] = Field(None, description="Host language for search (e.g., 'en', 'zh-CN').")
    search_type: Optional[str] = Field(None, description="Specific search type (e.g., 'news', 'images', 'shopping'). If not provided, general web search.")
    exclude_sites: Optional[List[str]] = Field(None, description="List of domains to exclude from search results (e.g., ['wikipedia.org', 'blogspam.com']).")
    time_period: Optional[str] = Field(None, description="Restrict results to a specific time period (e.g., 'past_hour', 'past_day', 'past_week', 'past_month', 'past_year', or Serper 'qdr' string like 'qdr:3m' for past 3 months).")

# --- Hospital, Doctor and Treatment Full Detail Models ---
class GeoLocation(BaseModel):
    latitude: float
    longitude: float

class ContactInfo(BaseModel):
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class MedicalProfessionalism(BaseModel):
    hospital_type: str
    certifications: List[str]
    key_specializations: List[str]
    renowned_doctor_teams_overview: Optional[str] = None
    advanced_technology_overview: Optional[List[str]] = None

class InternationalPatientServices(BaseModel):
    has_international_patient_center: bool
    languages_supported: List[str]
    cultural_accommodations: List[str]
    offers_medical_tourism_packages: bool
    package_details: Optional[str] = None

class GeographicalConvenience(BaseModel):
    distance_to_airport_km: Optional[float] = None
    distance_to_airport_text: Optional[str] = None
    transport_accessibility: Optional[str] = None
    nearby_tourist_attractions: Optional[List[str]] = None
    nearby_amenities: Optional[List[str]] = None

class BrandReputation(BaseModel):
    average_rating: Optional[float] = None
    review_count: Optional[int] = None
    review_summary_overview: Optional[str] = None
    listed_on_platforms: Optional[List[str]] = None
    online_presence_score: Optional[str] = None

class CostCurrency(BaseModel):
    min: Optional[float] = None 
    max: Optional[float] = None 
    currency: Optional[str] = None 

class TreatmentCost(BaseModel):
    myr: Optional[CostCurrency] = None
    usd: Optional[CostCurrency] = None
    unit: Optional[str] = None

class OfferedTreatment(BaseModel):
    treatment_id: str
    cost: TreatmentCost
    notes: Optional[str] = None

# FamousDoctor is not needed here if hospitals.json only stores doctor IDs
# class FamousDoctor(BaseModel):
#     name: str
#     specialty: str
#     background_summary: Optional[str] = None

class CostAndValue(BaseModel):
    hospital_price_tier: str
    service_cost_overview: Optional[str] = None
    main_currency_accepted: str
    accepts_multiple_currencies: bool
    payment_options: List[str]
    cost_transparency_score: Optional[str] = None

class HospitalDetails(BaseModel):
    """Represents comprehensive details of a hospital, matching your JSON example."""
    id: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    geo_location: Optional[GeoLocation] = None
    contact: Optional[ContactInfo] = None
    description_overview: Optional[str] = None
    medical_professionalism: Optional[MedicalProfessionalism] = None
    international_patient_services: Optional[InternationalPatientServices] = None
    geographical_convenience: Optional[GeographicalConvenience] = None
    brand_reputation: Optional[BrandReputation] = None
    cost_and_value: Optional[CostAndValue] = None
    treatments_offered: Optional[List[OfferedTreatment]] = None
    famous_doctors: Optional[List[str]] = None 
    equipment_list: Optional[List[str]] = None
    tourism_packages: Optional[List[str]] = None
    accessibility_features: Optional[List[str]] = Field(None, description="List of accessibility features provided by the hospital.")
    image_url: Optional[str] = Field(None, description="Image URL for the hospital.")

    @property
    def average_rating(self) -> Optional[float]:
        return self.brand_reputation.average_rating if self.brand_reputation else None
    
class TreatmentDetails(BaseModel):
    """Represents comprehensive details of a medical treatment."""
    id: Optional[str] = None
    name: Optional[str] = None
    associated_specialties: Optional[List[str]] = Field(default_factory=list)
    description: Optional[str] = None
    procedure_complexity_level: Optional[str] = None
    typical_hospital_stay: Optional[Dict[str, Any]] = None 
    estimated_recovery_time: Optional[Dict[str, Any]] = None 
    common_benefits: Optional[List[str]] = None
    potential_risks: Optional[List[str]] = None
    pre_procedure_requirements: Optional[List[str]] = None
    post_procedure_follow_ups: Optional[List[str]] = None
    estimated_market_cost_range_usd_min: Optional[float] = None
    estimated_market_cost_range_usd_max: Optional[float] = None
    cost_unit: Optional[str] = None 
    price_notes: Optional[str] = None
    cost_breakdown_notes: Optional[str] = None 

class DoctorDetails(BaseModel):
    """Details for a medical doctor."""
    id: Optional[str] = None
    name: Optional[str] = None
    specialty: Optional[str] = None
    education: Optional[str] = None
    experience_years: Optional[int] = None
    bio: Optional[str] = None
    average_rating: Optional[float] = None
    review_count: Optional[int] = None
    affiliated_hospital_ids: Optional[List[str]] = Field(default_factory=list)
    contact_info: Optional[ContactInfo] = None
    languages_spoken: Optional[List[str]] = Field(default_factory=list)
    certifications: Optional[List[str]] = Field(default_factory=list)
    awards: Optional[List[str]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# --- Medical DB Search Tool Models ---
class MedicalDBSearchInput(BaseModel):
    """
    Input schema for MedicalDBSearchTool.
    Aligned with the _arun method signature in medical_db_search_tool.py.
    """
    type: Literal["hospital", "doctor", "treatment"]= Field(..., description="Type of search entity: 'hospital', 'treatment', or 'doctor'.")
    name: Optional[str] = Field(None, description="Name of the hospital, treatment, or doctor to search for.")
    specialty: Optional[str] = Field(None, description="Specialty to filter by for doctors or treatments.")
    location: Optional[str] = Field(None, description="City or country to filter hospitals by.")
    international_services: Optional[bool] = Field(None, description="Filter for hospitals with international patient services.", strict=True)
    accessibility_features: Optional[str] = Field(None, description="Filter hospitals that support a given accessibility feature (e.g., wheelchair access).")
    min_rating: Optional[float] = Field(None, description="Minimum average rating to filter by.")
    treatment_id: Optional[str] = Field(None, description="ID of a specific treatment to filter by (e.g., for hospitals offering it).")
    min_cost: Optional[float] = Field(None, description="Minimum estimated cost to filter treatments by.")
    max_cost: Optional[float] = Field(None, description="Maximum estimated cost to filter treatments by.")
    cost_unit: Optional[str] = Field(None, description="Unit of cost (e.g., 'USD', 'MYR', 'per procedure').")
    min_experience_years: Optional[int] = Field(None, description="Minimum experience in years to filter doctors by.")
    affiliated_hospital_id: Optional[str] = Field(None, description="Filter doctors by affiliated hospital ID.")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        if v not in ('hospital', 'treatment', 'doctor'):
            raise ValueError("Type must be 'hospital', 'treatment', or 'doctor'.")
        return v
    
class MedicalDBSearchOutput(BaseModel):
    """
    Output schema for MedicalDBSearchTool.
    Corrected to match the explicit results returned by _arun (hospital_results, treatment_results, doctor_results).
    """
    hospital_results: List[HospitalDetails] = Field(default_factory=list, description="List of matching hospital records.")
    treatment_results: List[TreatmentDetails] = Field(default_factory=list, description="List of matching treatment records.")
    doctor_results: List[DoctorDetails] = Field(default_factory=list, description="List of matching doctor records.")
    message: str = Field("Search completed.", description="A message indicating the search status.")
    error: Optional[str] = Field(None, description="Error message if the search failed.")

    @property
    def results(self) -> List:
        if sum(bool(x) for x in [self.hospital_results, self.treatment_results, self.doctor_results]) > 1:
            raise ValueError("Ambiguous results: more than one result list is non-empty.")
        return self.hospital_results or self.treatment_results or self.doctor_results

# --- Medical Cost Estimator Tool Models ---
class MedicalCostEstimatorInput(BaseModel):
    """Input schema for MedicalCostEstimatorTool."""
    procedure_name: str = Field(..., description="The name of the medical procedure for which to estimate cost.")
    location: Optional[str] = Field(None, description="Optional: The location to refine cost estimation (e.g., city, country).")

class MedicalCost(BaseModel):
    """Represents the estimated cost details for a medical procedure."""
    procedure_name: str = Field(..., description="Name of the medical procedure.")
    estimated_cost_range_usd: str = Field(..., description="Estimated cost range in USD (e.g., '$1,500 - $3,000' or 'N/A').")
    associated_specialties: Optional[List[str]] = Field(None, description="Related medical specialties (matching TreatmentDetails).")
    notes: str = Field(..., description="Notes regarding the cost estimation.")
    
class MedicalCostEstimatorOutput(BaseModel):
    """Output schema for MedicalCostEstimatorTool."""
    cost_estimation: MedicalCost = Field(..., description="Details of the estimated medical cost.")

    @property
    def estimated_cost_range(self) -> Optional[str]:
        if self.cost_estimation:
            return self.cost_estimation.estimated_cost_range_usd
        return None
    
    error: Optional[str] = Field(None, description="Error message if cost estimation failed.")

# --- Visa Requirements Checker Tool Models ---
class VisaRequirementsInput(BaseModel):
    """Input schema for VisaRequirementsCheckerTool."""
    nationality: str = Field(..., description="The nationality of the traveler (e.g., 'us', 'chinese', 'malaysian').")
    destination_country: str = Field(..., description="The destination country for visa check (e.g., 'malaysia', 'singapore').")
    purpose: str = Field(..., description="The purpose of travel (e.g., 'medical', 'tourism', or other categories).") 

    @field_validator('nationality', 'destination_country')
    @classmethod
    def normalize_case(cls, v: str) -> str:
        """Normalize nationality and destination country to lowercase."""
        return v.lower()

class VisaInfo(BaseModel):
    """Details of visa requirements, matching the visa_rules.json structure."""
    visa_required: Union[bool, str] = Field(..., description="Is a visa required? Boolean or 'Consult Embassy'.")
    visa_type: Optional[str] = Field(..., description="Type of visa required (e.g., 'eVisa', 'Visa-Free', 'Medical Visa').")
    stay_duration_notes: Optional[str] = Field(..., description="Notes on maximum duration of stay.")
    required_documents: List[str] = Field(default_factory=list, description="List of required documents.")
    processing_time_days: Optional[Union[str, int]] = Field(..., description="Estimated processing time in days or 'N/A'.")
    notes: Optional[str] = Field(..., description="Additional notes or instructions.")

    @field_validator('visa_required', mode='before') 
    @classmethod
    def convert_visa_required_to_bool_or_string(cls, v):
        """Converts 'Yes'/'No' strings to boolean True/False, keeps 'Consult Embassy' as string."""
        if isinstance(v, str):
            if v.lower() == 'yes':
                return True
            elif v.lower() == 'no':
                return False
            elif v.lower() == 'consult embassy':
                return "Consult Embassy"
        return v 

class VisaRequirementsOutput(BaseModel):
    """Output schema for VisaRequirementsCheckerTool."""
    nationality: str
    destination_country: str
    purpose: str
    visa_info: VisaInfo
    error: Optional[str] = None

# --- Get Weather Data Tool Models ---
class Condition(BaseModel):
    text: str
    icon: str
    code: int

class CurrentWeather(BaseModel):
    temp_c: float
    temp_f: float
    is_day: int
    condition: Condition
    wind_mph: float
    wind_kph: float
    wind_degree: int
    wind_dir: str
    pressure_mb: float
    pressure_in: float
    precip_mm: float
    precip_in: float
    humidity: int
    cloud: int
    feelslike_c: float
    feelslike_f: float
    vis_km: float
    vis_miles: float
    uv: float
    gust_mph: float
    gust_kph: float

class DayForecast(BaseModel):
    maxtemp_c: float
    maxtemp_f: float
    mintemp_c: float
    mintemp_f: float
    avgtemp_c: float
    avgtemp_f: float
    maxwind_mph: float
    maxwind_kph: float
    totalprecip_mm: float
    totalprecip_in: float
    totalsnow_cm: float
    avgvis_km: float
    avgvis_miles: float
    avghumidity: float
    daily_will_it_rain: int
    daily_chance_of_rain: int
    daily_will_it_snow: int
    daily_chance_of_snow: int
    condition: Condition
    uv: float

class Astro(BaseModel):
    sunrise: str
    sunset: str
    moonrise: str
    moonset: str
    moon_phase: str
    moon_illumination: str

    @field_validator("moon_illumination", mode="before")
    @classmethod
    def convert_illumination(cls, v):
        return str(v)
    
    is_moon_up: int
    is_sun_up: int

class HourForecast(BaseModel):
    time_epoch: int
    time: str
    temp_c: float
    temp_f: float
    is_day: int
    condition: Condition
    wind_mph: float
    wind_kph: float
    wind_degree: int
    wind_dir: str
    pressure_mb: float
    pressure_in: float
    precip_mm: float
    precip_in: float
    humidity: int
    cloud: int
    feelslike_c: float
    feelslike_f: float
    windchill_c: float
    windchill_f: float
    heatindex_c: float
    heatindex_f: float
    dewpoint_c: float
    dewpoint_f: float
    will_it_rain: int
    chance_of_rain: int
    will_it_snow: int
    chance_of_snow: int
    vis_km: float
    vis_miles: float
    gust_mph: float
    gust_kph: float
    uv: float

class ForecastDay(BaseModel):
    date: str
    date_epoch: int
    day: DayForecast
    astro: Astro
    hour: List[HourForecast]

class Forecast(BaseModel):
    forecastday: List[ForecastDay]

class Location(BaseModel):
    name: str
    region: str
    country: str
    lat: float
    lon: float
    tz_id: str
    localtime_epoch: int
    localtime: str

class WeatherAPIResponse(BaseModel):
    location: Location
    current: CurrentWeather
    forecast: Forecast

class GetWeatherDataInput(BaseModel):
    """Input schema for GetWeatherDataTool."""
    destination: str = Field(..., description="The city or location for which to get weather data (e.g., 'London', 'New York').")
    date: str = Field(..., description="The date for the weather forecast in YYYY-MM-DD format (up to 14 days in the future for free tier).")

class GetWeatherDataOutput(BaseModel):
    """Output schema for GetWeatherDataTool."""
    weather_data: WeatherAPIResponse = Field(..., description="Detailed weather information from WeatherAPI.com.")
    error: Optional[str] = Field(None, description="Error message if weather data retrieval failed.")

class WeatherData(BaseModel):
    """
    A simplified weather model for the TravelArrangementOutput,
    summarizing key information for the user.
    """
    city: str = Field(..., description="The name of the city.")
    country: str = Field(..., description="The name of the country.")
    date: str = Field(..., description="The date of the weather forecast in YYYY-MM-DD format.")
    condition: str = Field(..., description="A brief description of the weather, e.g., 'Sunny', 'Cloudy'.")
    temperature_celsius: Optional[float] = Field(None, description="The average temperature in Celsius.")
    temperature_fahrenheit: Optional[float] = Field(None, description="The average temperature in Fahrenheit.")
    humidity_percent: Optional[float] = Field(None, description="The average humidity as a percentage.")
    wind_speed_kph: Optional[float] = Field(None, description="The average wind speed in km/h.")
    forecast: str = Field(..., description="A short textual forecast for the day.")

# --- Search Flights Tool Models ---
class FlightSegmentSummary(BaseModel):
    departure_iata: str = Field(..., description="Departure airport IATA code.")
    arrival_iata: str = Field(..., description="Arrival airport IATA code.")
    departure_time: str = Field(..., description="Departure time (HH:MM).")
    arrival_time: str = Field(..., description="Arrival time (HH:MM).")
    duration: str = Field(..., description="Segment duration (e.g., 'PT2H30M').")
    carrier_code: str = Field(..., description="Airline carrier code.")
    number: str = Field(..., description="Flight number.")
    number_of_stops: int = Field(..., description="Number of stops in this segment.")

class FlightOptionSummary(BaseModel):
    """Summarized flight option for user presentation."""
    id: str = Field(..., description="Unique identifier for the flight option, e.g., 'FLIGHT_A_1'.")
    total_cost: Union[int, str] = Field(..., description="Total estimated cost of the flight, including currency.")
    currency: str = Field(..., description="Currency of the total cost (e.g., 'USD', 'EUR').")
    duration: str = Field(..., description="Total flight duration (e.g., 'PT10H30M').")
    layovers: Union[int, List[dict]] = Field(..., description="Total number of layovers for the entire itinerary.")
    segments: List[FlightSegmentSummary] = Field(..., description="Summarized details of each flight segment.")
    airline_names: str = Field(..., description="Comma-separated list of airline names involved.")
    segments_summary: str = Field(..., description="A concise summary of the flight segments (e.g., 'KUL-SIN (direct)').")
    notes: Optional[str] = Field(None, description="Any additional notes about the flight option.")

class SearchFlightsInput(BaseModel):
    """Input schema for SearchFlightsTool."""
    origin: str = Field(..., description="The origin airport IATA code (e.g., 'KUL').")
    destination: str = Field(..., description="The destination airport IATA code (e.g., 'SIN').")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format.")
    return_date: Optional[str] = Field(None, description="Optional return date in YYYY-MM-DD format for round trip.")
    adults: int = Field(1, description="Number of adult passengers (default 1).")
    children: int = Field(0, description="Number of children passengers.")
    infants: int = Field(0, description="Number of infant passengers.")
    travel_class: Optional[str] = Field("ECONOMY", description="Travel class (e.g., 'ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST').")
    max_results: int = Field(5, description="Maximum number of flight offers to retrieve (default 5).")
    non_stop: Optional[bool] = Field(None, description="If true, only non-stop flights are returned.")
    currency_code: Optional[str] = Field(None, description="The preferred currency for flight prices (e.g., 'USD', 'EUR').")
    preferred_airlines: Optional[List[str]] = Field(None, description="List of preferred airline codes (e.g., ['MH', 'SQ']).")
    max_layover_duration: Optional[str] = Field(None, description="Maximum allowed layover duration in ISO 8601 format (e.g., 'PT3H' for 3 hours, 'PT1H30M' for 1 hour 30 minutes).")
    earliest_departure_time: Optional[str] = Field(None, description="Earliest preferred departure time in HH:MM format (e.g., '08:00').")
    latest_arrival_time: Optional[str] = Field(None, description="Latest preferred arrival time in HH:MM format (e.g., '18:00').")

    @field_validator('departure_date', 'return_date', mode='before') 
    @classmethod
    def validate_date_format(cls, v):
        if v is None:
            return v
        if not re.fullmatch(r"^\d{4}-\d{2}-\d{2}$", v): 
            raise ValueError("Date must be in YYYY-MM-DD format.")
        return v
    
    @field_validator('travel_class', mode='before') 
    @classmethod
    def validate_travel_class(cls, v):
        if v:
            v_upper = v.upper()
            if v_upper not in ['ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST']:
                raise ValueError("Travel class must be 'ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', or 'FIRST'.")
            return v_upper
        return v

class SearchFlightsOutput(BaseModel):
    """Output schema for SearchFlightsTool."""
    flight_options: List[FlightOptionSummary] = Field(..., description="A list of summarized flight options.")
    message: str = Field("Search completed.", description="A message indicating the search status.") 
    error: Optional[str] = Field(None, description="Error message if flight search failed.")

# --- Amadeus API raw response models (for internal validation of raw API response) ---
class TravelerPricing(BaseModel):
    travelerId: str
    fareOption: str
    travelerType: str
    price: Dict[str, str] 

class Segment(BaseModel):
    departure: Dict[str, Any] 
    arrival: Dict[str, Any]
    carrierCode: str
    number: str
    duration: str 
    id: str
    numberOfStops: int
    blacklistedInEU: Optional[bool] = None

class Itinerary(BaseModel):
    duration: str 
    segments: List[Segment]

class Price(BaseModel):
    currency: str
    total: str
    base: str
    fees: Optional[List[Dict[str, str]]] = None
    grandTotal: Optional[str] = None

class FlightOffer(BaseModel):
    type: str
    id: str
    source: str
    instantTicketingRequired: bool
    nonHomogeneous: Optional[bool] = None
    oneWay: bool
    lastTicketingDate: str
    lastTicketingDateTime: str
    numberOfBookableSeats: int
    itineraries: List[Itinerary]
    price: Price
    pricingOptions: Dict[str, Any] 
    validatingAirlineCodes: Optional[List[str]] = None
    travelerPricings: List[TravelerPricing]

class AmadeusFlightSearchResponse(BaseModel):
    data: List[FlightOffer]
    # Add meta and dictionaries if needed for full response parsing
    # meta: Optional[Dict[str, Any]] = None
    # dictionaries: Optional[Dict[str, Any]] = None

# --- City to IATA Code Tool Models ---
class CityToIATACodeInput(BaseModel):
    """Input schema for CityToIATACodeTool."""
    city_name: str = Field(..., description="The name of the city (e.g., 'Kuala Lumpur').")

class AirportInfo(BaseModel):
    city_name: str = Field(..., description="Name of the city the airport is in.")
    airport_name: str = Field(..., description="Full name of the airport.")
    iata_code: str = Field(..., description="IATA airport code (e.g., 'KUL').")
    country_code: str = Field(..., description="ISO country code (e.g., 'MY').")

class CityToIATACodeOutput(BaseModel):
    """Output schema for CityToIATACodeTool."""
    airports: List[AirportInfo] = Field(..., description="List of airports found for the city, with IATA codes.")
    error: Optional[str] = Field(None, description="Error message if lookup failed.")

# --- Search Accessible Accommodation Tool Models ---
class AccommodationOption(BaseModel):
    """Represents a single accessible accommodation option."""
    id: str = Field(..., description="Unique identifier for the accommodation option.")
    name: str = Field(..., description="Name of the accommodation (e.g., 'Comfort Suites Accessible').")
    location: str = Field(..., description="General location of the accommodation (e.g., 'Central Singapore').")
    country: str = Field(..., description="Country where the accommodation is located.")
    city: str = Field(..., description="City where the accommodation is located.")
    min_cost_per_night_usd: float = Field(..., description="Minimum estimated cost per night in USD.") 
    max_cost_per_night_usd: float = Field(..., description="Maximum estimated cost per night in USD.") 
    total_cost_estimate_usd: Union[int, str] = Field(..., description="Estimated total cost for the stay in USD.")
    accessibility_features: List[str] = Field(default_factory=list, description="Detailed accessibility features (e.g., 'Roll-in shower', 'grab bars', 'wide doorways').")
    availability: str = Field(..., description="Availability notes (e.g., 'Available for specified dates').")
    contact_info: Optional[str] = Field(None, description="Contact information for booking.")
    booking_link: Optional[str] = Field(None, description="Direct booking link if available.")
    notes: str = Field(..., description="Any additional notes about the accommodation.")
    nearby_landmarks: Optional[List[str]] = Field(None, description="List of nearby landmarks or hospitals.")
    image_url: Optional[str] = Field(None, description="Image URL for the accommodation.")
    star_rating: Optional[int] = Field(None, description="Star rating of the accommodation.")
    accommodation_type: Optional[str] = Field(None, description="Type of accommodation (e.g., 'hotel', 'serviced_apartment').")
    with_kitchen: Optional[int] = Field(None, description="Whether the accommodation has kitchen facilities (0 or 1).")
    pet_friendly: Optional[int] = Field(None, description="Whether the accommodation is pet-friendly (0 or 1).")

class AccessibleAccommodationInput(BaseModel):
    """Input schema for AccessibleAccommodationTool."""
    destination_city: str = Field(..., description="The destination city for accommodation (e.g., 'Singapore').")
    destination_country: str = Field(..., description="The destination country for accommodation (e.g., 'Singapore').")
    check_in_date: str = Field(..., description="Check-in date in YYYY-MM-DD format.")
    check_out_date: str = Field(..., description="Check-out date in YYYY-MM-DD format.")
    num_guests: int = Field(1, description="Number of guests.")
    accommodation_type: Optional[List[str]] = Field(None, description="Preferred accommodation type (e.g., ['hotel'], ['serviced_apartment', 'guesthouse']).")
    accessibility_needs: Optional[List[str]] = Field(None, description="Specific accessibility needs (e.g., ['wheelchair accessible room'], ['hearing impaired facilities']).")
    nearby_landmarks: Optional[str] = Field(None, description="Specific nearby landmarks or hospitals to prioritize.")
    star_rating_min: Optional[int] = Field(None, description="Minimum preferred star rating (e.g., 3).")
    star_rating_max: Optional[int] = Field(None, description="Maximum preferred star rating (e.g., 5).")
    with_kitchen_req: Optional[bool] = Field(None, description="Whether kitchen facilities are required.")
    pet_friendly_req: Optional[bool] = Field(None, description="Whether the accommodation must be pet-friendly.")

class AccessibleAccommodationOutput(BaseModel):
    """Output schema for AccessibleAccommodationTool."""
    accommodation_options: List[AccommodationOption] = Field(default_factory=list, description="List of matching accessible accommodation options.")
    message: str = Field("Search completed.", description="A message indicating the search status.")
    error: Optional[str] = Field(None, description="Error message if the search failed.")

# --- Arrange Local Medical Transport Tool Models ---
class TransportOption(BaseModel):
    """Represents a single local medical transport option."""
    id: str = Field(..., description="Unique identifier for the transport option.")
    service_name: str = Field(..., description="Name of the transport service.")
    type: str = Field(..., description="Type of transport (e.g., 'Wheelchair-accessible taxi', 'Medical shuttle').")
    provider: str = Field(..., description="Provider of the transport service.")
    estimated_cost_per_transfer_usd: str = Field(..., description="Estimated cost per transfer in USD.")
    contact_info: Optional[str] = Field(None, description="Contact information for booking.")
    notes: str = Field(..., description="Additional notes about the service.")
    country: str = Field(..., description="Country where the service is available.")
    city: str = Field(..., description="City where the service is primarily available.")
    accessibility_features: List[str] = Field(default_factory=list, description="List of accessibility features.")

class LocalMedicalTransportInput(BaseModel):
    """Input schema for LocalMedicalTransportTool."""
    destination_city: str = Field(..., description="The destination city for transport (e.g., 'Singapore').")
    destination_country: str = Field(..., description="The destination country for transport (e.g., 'Singapore').")
    transport_date: Optional[str] = Field(None, description="Specific date for transport in YYYY-MM-DD format.")
    transport_purpose: Optional[str] = Field(None, description="Purpose of transport (e.g., 'hospital visits', 'airport transfer').")
    transport_type: Optional[str] = Field(None, description="Preferred type of transport (e.g., 'wheelchair-accessible taxi', 'medical shuttle', 'ambulance').")
    accessibility_needs: Optional[str] = Field(None, description="Specific accessibility needs (e.g., 'wheelchair accessible', 'stretcher').")

class LocalMedicalTransportOutput(BaseModel):
    """Output schema for LocalMedicalTransportTool."""
    transport_options: List[TransportOption] = Field(default_factory=list, description="List of matching local medical transport options.")
    message: str = Field("Search completed.", description="A message indicating the search status.")
    error: Optional[str] = Field(None, description="Error message if the search failed.")

# --- Medical Planning Tool Models ---
class MedicalPlanningInput(BaseModel):
    """Input schema for MedicalPlanningTool."""
    medical_purpose: str = Field(..., description="The medical condition or procedure the user is seeking treatment for.")
    patient_nationality: str = Field(..., description="The patient's nationality, crucial for visa requirements.")
    destination_country: str = Field(..., description="The country the user wishes to travel to for medical care.")
    estimated_budget_usd: Optional[str] = Field(None, description="The user's estimated medical budget in USD (e.g., '$10,000 - $20,000').")
    departure_date: Optional[str] = Field(None, description="The planned departure date in YYYY-MM-DD format.")
    travel_date_flexibility: Optional[str] = Field(None, description="User's flexibility with travel dates (e.g., 'flexible', 'fixed', 'within 1 month').")
    treatment_urgency: Optional[str] = Field(None, description="Urgency of treatment (e.g., 'urgent', 'elective', 'within 3 months').")
    accompanying_guests: int = Field(0, description="Number of accompanying guests.")
    preferred_medical_language: Optional[str] = Field(None, description="Preferred language for medical services (e.g., 'English', 'Mandarin').")

class MedicalPlanOption(BaseModel):
    """Represents a single medical plan option proposed by the MedicalPlanningTool."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the medical plan option.")  
    treatment_name: Optional[str] = Field("N/A", description="Name of the medical treatment or procedure.")
    estimated_cost_usd: Optional[str] = Field("N/A", description="Estimated total cost of the treatment in USD.")
    clinic_name: Optional[str] = Field("N/A", description="Name of the recommended clinic/hospital.")
    clinic_location: Optional[str] = Field("N/A", description="Location of the clinic/hospital (city, country).")
    visa_notes: Optional[str] = Field("N/A", description="Relevant notes about visa requirements for this plan.")
    brief_description: Optional[str] = Field("N/A", description="A brief summary of this medical plan option for the card.")
    full_hospital_details: Optional[Dict[str, Any]] = None
    full_treatment_details: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None

class MedicalPlanningOutput(BaseModel):
    """Output schema for MedicalPlanningTool."""
    medical_plan_options: List[MedicalPlanOption] = Field(default_factory=list, description="A list of structured medical plan options.")
    message: str = Field("Medical planning completed.", description="A message indicating the status of the medical planning process.")
    error: Optional[str] = Field(None, description="Error message if medical planning failed or is incomplete.")
    visa_information: Optional[VisaInfo] = Field(None, description="Detailed visa information based on nationality and destination.")

class MedicalPlanOptionList(RootModel[List[MedicalPlanOption]]):
    pass

# --- Travel Arrangement Tool Models ---
class TravelArrangementInput(BaseModel):
    """Input schema for TravelArrangementTool."""
    departure_city: str = Field(..., description="The user's departure city.")
    estimated_return_date: str = Field(..., description="The estimated return date in YYYY-MM-DD format.")
    flight_preferences: Optional[List[str]] = Field(default_factory=list, description="User's preferences for flights (e.g., 'direct flights', 'business class').")
    accommodation_requirements: Optional[List[str]] = Field(default_factory=list, description="User's requirements for accommodation (e.g., 'near hospital', 'kitchenette').")
    star_rating_min: Optional[int] = Field(None, description="Minimum star rating for accommodation.")
    star_rating_max: Optional[int] = Field(None, description="Maximum star rating for accommodation.")
    accessibility_needs: Optional[List[str]] = Field(default_factory=list, description="Specific accessibility features required for accommodation (e.g., 'wheelchair accessible room').")
    nearby_landmarks: Optional[str] = Field(None, description="Nearby landmarks or points of interest for accommodation search (e.g., 'hospital name').")
    with_kitchen_req: Optional[bool] = Field(None, description="Whether a kitchen or kitchenette is required in the accommodation.")
    pet_friendly_req: Optional[bool] = Field(None, description="Whether pet-friendly accommodation is required.")
    visa_assistance_needed: Optional[bool] = Field(False, description="True if the user requires visa assistance, or 'not sure'.")
    visa_information_from_medical_plan: Optional[VisaInfo] = Field(None, description="Visa information passed from the medical planning stage.")
    medical_destination_city: str = Field(..., description="The medical destination city from the selected medical plan.")
    medical_destination_country: str = Field(..., description="The medical destination country from the selected medical plan.")
    check_in_date: str = Field(..., description="The accommodation check-in date, which also serves as the medical trip's departure date, in YYYY-MM-DD format.")
    check_out_date: str = Field(..., description="The accommodation check-out date in YYYY-MM-DD format.")
    num_guests_medical_plan: int = Field(1, description="Number of guests from the selected medical plan, including patient.")

class TravelArrangementOutput(BaseModel):
    """Output schema for TravelArrangementTool."""
    medical_destination_city: Optional[str] = Field(None, description="City where the medical treatment will take place.")
    flight_suggestions: List[FlightOptionSummary] = Field(default_factory=list, description="List of suggested flight options.")
    accommodation_suggestions: List[AccommodationOption] = Field(default_factory=list, description="List of suggested accommodation options.")
    weather_info: Optional[WeatherData] = Field(None, description="Weather information for the destination.")
    visa_assistance_flag: Optional[bool] = Field(None, description="Flag indicating if visa assistance was requested/considered.")
    visa_information: Optional[VisaInfo] = Field(None, description="Detailed visa information if assistance was requested.")
    
    @model_validator(mode="after")
    def check_visa_fields(self) -> "TravelArrangementOutput":
        if self.error:
            return self

        if self.visa_assistance_flag and self.visa_information is None:
            raise ValueError(
                "Visa information must be provided if visa assistance is requested and no error occurred."
            )
        return self
    
    message: str = Field("Travel arrangements planned.", description="A message indicating the planning status.")
    error: Optional[str] = Field(None, description="Error message if travel arrangement failed.")
    
# --- Travel Logistics Tool Models  ---
class TravelLogisticsInput(BaseModel):
    """Input schema for TravelLogisticsTool."""
    medical_purpose: Optional[str] = Field(None, description="The patient's medical purpose for the trip (e.g., surgery, rehabilitation, general check-up).")
    medical_destination_city: str = Field(..., description="The medical destination city from previous stages.")
    medical_destination_country: str = Field(..., description="The medical destination country from previous stages.")
    medical_stay_start_date: str = Field(..., description="The start date of the medical stay (e.g., flight arrival date or accommodation check-in).")
    medical_stay_end_date: str = Field(..., description="The end date of the medical stay (e.g., flight return date or accommodation check-out).")
    num_guests_total: int = Field(1, description="Total number of guests including patient.")
    airport_pick_up_required: bool = Field(False, description="Whether airport pick-up service is required upon arrival.")
    local_transportation_needs: Optional[List[str]] = Field(default_factory=list, description="User's local transportation needs during medical stay (e.g., 'wheelchair-accessible taxi', 'daily hospital shuttle').")
    additional_local_services_needed: Optional[List[str]] = Field(default_factory=list, description="Any additional local services required (e.g., 'interpreter', 'nursing care').")
    dietary_needs: Optional[List[str]] = Field(default_factory=list, description="Specific dietary needs or restrictions (e.g., 'halal', 'vegetarian', 'gluten-free').")
    sim_card_assistance_needed: bool = Field(False, description="Whether assistance with a local SIM card is required.")
    leisure_activities_interest: Optional[List[str]] = Field(default_factory=list, description="User's interest in leisure activities or sightseeing during recovery (e.g., 'city tours', 'museums').")
    patient_accessibility_needs: Optional[str] = Field(None, description="Patient's general accessibility needs (e.g., 'wheelchair accessible') from medical plan.")

class TravelLogisticsOutput(BaseModel):
    """Output schema for TravelLogisticsTool."""
    status: str = Field(..., description="Overall status of the travel logistics planning (e.g., 'Completed', 'Partial', 'Failed').")
    airport_pick_up_details: Optional[TransportOption] = Field(None, description="Details of the recommended airport pick-up service.")
    local_transport_suggestions: List[TransportOption] = Field(default_factory=list, description="Suggested local medical transport options.")
    additional_local_services_suggestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Suggestions for additional local services (e.g., interpreters, nursing care).")
    dietary_recommendations: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Recommendations based on dietary needs (e.g., restaurants, grocery stores).")
    sim_card_assistance_info: Optional[Dict[str, Any]] = Field(None, description="Information regarding local SIM card assistance (e.g., providers, where to buy).")
    leisure_activity_suggestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Suggestions for leisure activities or sightseeing.")
    message: str = Field("Travel logistics planned.", description="A message indicating the status of the overall logistics process.")
    error: Optional[str] = Field(None, description="Error message if travel logistics planning failed or are incomplete.")

# --- Update Session State Tool Models ---
class UpdateSessionStateInput(BaseModel):
    """Input schema for the UpdateSessionStateTool."""
    type: Annotated[str, StringConstraints(min_length=1)] = Field(..., description="The type of plan to save (e.g., 'medical_plan', 'flight', 'accommodation', 'local_logistics').")
    id: Annotated[str, StringConstraints(min_length=1)] = Field(..., description="The ID of the option selected by the user (e.g., 'MP_001', 'FLIGHT_001', 'HOTEL_001').")

# --- Calculate Budget Tool Models ---
class CalculateBudgetInput(BaseModel):
    """Input schema for the CalculateBudgetTool."""
    session_state: dict = Field(..., description="The full session state JSON object containing all collected plan parameters.")

class LoadSessionRequest(BaseModel):
    session_id: str

# Pydantic model for incoming request body
class NextStepRequest(BaseModel):
    user_input: str
    session_id: str
    current_stage: str
    chat_history: List[Dict[str, Any]]
    session_state: Dict[str, Any]

class AgentRequest(BaseModel):
    user_input: str
    chat_history: Optional[List[Dict[str, Any]]] = []
    session_state: Optional[Dict[str, Any]] = {}

class SummaryCard(BaseModel):
    id: str
    name: str
    location: str
    cost_usd: Optional[str] = None
    brief_description: Optional[str] = None
    image_url: Optional[str] = None
    details_data: Dict[str, Any] = Field(default_factory=dict) 

class MedicalPlanningResponseContent(BaseModel):
    output: List[SummaryCard]
    visa_information: Dict[str, Any]

class TravelArrangementResponseContent(BaseModel):
    output: List[SummaryCard]
    # flight_info: Dict[str, Any]
    # accommodation_info: Dict[str, Any]

class TravelLogisticsResponseContent(BaseModel):
    output: List[SummaryCard]
    # transport_info: Dict[str, Any]

class AgentQuestionContent(BaseModel):
    id: str
    prompt: str
    type: str
    options: Optional[List[Dict[str, Any]]] = None

class AgentSummaryCardsContent(BaseModel):
    planning_type: str = Field(..., description="E.g., 'medical_plans', 'travel_arrangements'")
    payload: Union[
        MedicalPlanningResponseContent,
        TravelArrangementResponseContent,
        TravelLogisticsResponseContent
    ]

class AgentResponse(BaseModel):
    """
    Standardized response format for the AI agent.
    """
    message_type: str
    content: Dict[str, Any]
    action_items: Optional[List[Dict[str, Any]]] = None