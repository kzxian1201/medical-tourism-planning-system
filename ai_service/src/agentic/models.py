# ai_service/src/agentic/models.py
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal, Annotated
from typing_extensions import TypedDict
import re
from datetime import datetime
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# Constants
PROVENANCE_DESCRIPTION = "Data provenance information for auditability."

# Auditability & Provenance Models
class DataProvenance(BaseModel):
    """
    [Enterprise Grade]
    Attached to every critical data point to ensure traceability.
    """
    source: str = Field(..., description="The origin of this data (e.g., 'MHTC Official Website', 'Google Search', 'Mock Database').")
    source_url: Optional[str] = Field(None, description="Direct link to the source if available.")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="When was this data fetched?")
    confidence_score: float = Field(default=1.0, description="Confidence level of this information (0.0 - 1.0).")
    is_mock_data: bool = Field(default=False, description="Flag to indicate if this is demo/fallback data.")

class KnowledgeEntity(BaseModel):
    """
    [Entity-Centric RAG]
    The pre-compiled, structured knowledge entity (e.g., Hospital, Visa Policy).
    """
    entity_id: str = Field(..., description="Unique identifier, e.g., 'hospital_island_penang'")
    category: str = Field(..., description="Category: 'hospital', 'visa', 'restaurant'")
    name: str = Field(..., description="Name of the entity")
    data: Dict[str, Any] = Field(..., description="The highly structured data payload")
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp of last merge")
    conflict_warning: Optional[str] = Field(None, description="Warnings if contradicting information was found during ingestion")
    provenance: DataProvenance = Field(...)

class ValidationVerdict(BaseModel):
    """
    [Ingestion QA]
    Verdict for Data Quality before committing to the Database.
    """
    is_valid: bool = Field(..., description="True if the data is safe to write to SQLite, False if flagged for issues.")
    requires_human_review: bool = Field(..., description="True if a severe anomaly or conflict was detected.")
    error_log: List[str] = Field(default_factory=list, description="Specific reasons triggering the interception.")

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
    fetched_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp of the search execution.")
    
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

# model for medical knowledge base tool
class KnowledgeBaseInput(BaseModel):
    """
    Input for the Unified Medical Knowledge Base.
    Agent should use this to find Hospitals, Doctors, Visa info, Accommodation, or Transport.
    """
    category: Literal["hospital", "doctor", "treatment", "accommodation", "transport", "visa"] = Field(
        ...,
        description="The category of data to retrieve."
    )
    query: str = Field(
        ...,
        description="Natural language query describing what you need. E.g., 'Cheap hotel with kitchen in KL' or 'Visa for Chinese to Malaysia'."
    )
    
# Output model for medical knowledge base tool
class KnowledgeBaseOutput(BaseModel):
    results: List[Dict[str, Any]] = Field(default_factory=list)
    message: str
    error: Optional[str] = None

# --- Visa Requirements Models ---
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
    visa_required: str = Field(..., description="Is a visa required? e.g., 'Yes', 'No', 'Consult Embassy'.")
    visa_type: str = Field(..., description="Type of visa required (e.g., 'eVisa', 'Visa-Free', 'Medical Visa').")
    stay_duration_notes: str = Field(..., description="Notes on maximum duration of stay.")
    required_documents: List[str] = Field(..., description="List of required documents.")
    processing_time_days: str = Field(..., description="Estimated processing time in days or 'N/A'.")
    notes: str = Field(..., description="Additional notes or instructions.")

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
    weather_data: Dict[str, Any] = Field(default_factory=dict, description="Raw weather data JSON.")
    error: Optional[str] = Field(default=None, description="Error message if weather data retrieval failed.")
    provenance: Optional[DataProvenance] = Field(default=None, description=PROVENANCE_DESCRIPTION)

class WeatherData(BaseModel):
    """
    A simplified weather model for the TravelArrangementOutput,
    summarizing key information for the user and safety planning.
    """
    city: str = Field(..., description="The name of the destination city.")
    date_range: str = Field(..., description="The date or range of the forecast, e.g., 'March 5 - March 17'.")
    temperature_range: str = Field(..., description="Expected temperature range, e.g., '24°C - 32°C'.")
    precipitation_probability: str = Field(..., description="Max precipitation probability, e.g., '80%'. CRITICAL for wheelchair safety planning.")
    condition: str = Field(..., description="Brief description of the overall weather, e.g., 'Mostly Sunny' or 'Likely Rain'.")
    weather_advice: str = Field(..., description="Specific advice for the medical traveler based on weather (e.g., 'High rain probability, recommend indoor activities and GrabAssist').")

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
    total_cost: str = Field(..., description="Total estimated cost of the flight, including currency.")
    currency: str = Field(..., description="Currency of the total cost (e.g., 'USD', 'EUR').")
    duration: str = Field(..., description="Total flight duration (e.g., 'PT10H30M').")
    layovers_description: Optional[str] = Field(None, description="Total number of layovers.")
    segments: List[FlightSegmentSummary] = Field(..., description="Summarized details of each flight segment.")
    airline_names: str = Field(..., description="Comma-separated list of airline names involved.")
    segments_summary: str = Field(..., description="A concise summary of the flight segments (e.g., 'KUL-SIN (direct)').")
    notes: Optional[str] = Field(None, description="Any additional notes about the flight option.")
    provenance: Optional[DataProvenance] = Field(None, description=PROVENANCE_DESCRIPTION)

class SearchFlightsInput(BaseModel):
    """Input schema for SearchFlightsTool."""
    origin: str = Field(..., description="The origin airport IATA code (e.g., 'KUL').")
    destination: str = Field(..., description="The destination airport IATA code (e.g., 'SIN').")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format.")
    return_date: Optional[str] = Field(default=None, description="Optional return date in YYYY-MM-DD format for round trip.")
    adults: int = Field(1, description="Total number of passengers (patient + companions)")
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

class FlightExtraction(BaseModel):
    flights: List[FlightOptionSummary] = Field(description="List of extracted flight options.")

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
    provenance: Optional[DataProvenance] = Field(None, description=PROVENANCE_DESCRIPTION)

class CityToIATACodeOutput(BaseModel):
    """Output schema for CityToIATACodeTool."""
    airports: List[AirportInfo] = Field(..., description="List of airports found for the city, with IATA codes.")
    error: Optional[str] = Field(None, description="Error message if lookup failed.")

# --- Accessible Accommodation Models ---
class AccommodationOption(BaseModel):
    """Represents a single accessible accommodation option."""
    id: str = Field(..., description="Unique identifier for the accommodation option.")
    name: str = Field(..., description="Name of the accommodation (e.g., 'Comfort Suites Accessible').")
    location: str = Field(..., description="General location of the accommodation (e.g., 'Central Singapore').")
    country: str = Field(..., description="Country where the accommodation is located.")
    city: str = Field(..., description="City where the accommodation is located.")
    min_cost_per_night_usd: float = Field(..., description="Minimum estimated cost per night in USD.")
    max_cost_per_night_usd: float = Field(..., description="Maximum estimated cost per night in USD.")
    total_cost_estimate_usd: str = Field(..., description="Estimated total cost for the stay in USD.")
    accessibility_features: List[str] = Field(default_factory=list, description="Detailed accessibility features (e.g., 'Roll-in shower', 'grab bars', 'wide doorways').")
    availability: str = Field(..., description="Availability notes (e.g., 'Available for specified dates').")
    contact_info: Optional[str] = Field(default="Contact via concierge", description="Booking phone or email.")
    booking_link: Optional[str] = Field(default=None, description="Direct booking link if available.")
    notes: str = Field(..., description="Any additional notes about the accommodation.")
    nearby_landmarks: Optional[List[str]] = Field(None, description="List of nearby landmarks or hospitals.")
    image_url: Optional[str] = Field(default=None, description="Image URL for the accommodation.")
    star_rating: Optional[int] = Field(None, description="Star rating of the accommodation.")
    accommodation_type: Optional[str] = Field(None, description="Type of accommodation (e.g., 'hotel', 'serviced_apartment').")
    with_kitchen: Optional[int] = Field(default=0, description="Whether the accommodation has kitchen facilities (0 or 1).")
    pet_friendly: Optional[int] = Field(default=0, description="Whether the accommodation is pet-friendly (0 or 1).")
    provenance: Optional[DataProvenance] = Field(None, description=PROVENANCE_DESCRIPTION)

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

# --- Transport Option Models ---
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

class HospitalDetails(BaseModel):
    """Specific details about the hospital's professionalism and services."""
    hospital_type: Optional[str] = Field("Unknown", description="Type of hospital, e.g., 'Private Tertiary'")
    certifications: List[str] = Field(default_factory=list, description="List of accreditations, e.g., ['JCI Accredited', 'MSQH']")
    key_specializations: List[str] = Field(default_factory=list, description="Top medical departments.")
    international_services: List[str] = Field(default_factory=list, description="Services for foreign patients like airport transfer, interpreters.")

class CurrencyConverterInput(BaseModel):
    amount: float = Field(..., description="The amount of money to convert.")
    base_currency: str = Field(..., description="The 3-letter currency code to convert FROM (e.g., USD, AUD, SGD).")
    target_currency: str = Field(..., description="The 3-letter currency code to convert TO (e.g., MYR, THB).")

class InsuranceInput(BaseModel):
    duration_days: int = Field(..., description="Trip duration in days to calculate premium.")
    destination: str = Field(..., description="Destination country (e.g., 'Malaysia').")

class UpdateProfileInput(BaseModel):
    dietary_needs: Optional[List[str]] = Field(None, description="New dietary restrictions (e.g., ['Halal', 'Vegetarian']).")
    accessibility_needs: Optional[List[str]] = Field(None, description="New mobility needs (e.g., ['Wheelchair']).")
    medical_allergies: Optional[List[str]] = Field(None, description="Reported drug or material allergies (e.g., ['Penicillin']).")
    preferred_language: Optional[str] = Field(None, description="User's preferred language.")
    travel_class_preference: Optional[str] = Field(None, description="Flight/train class preference (e.g., 'Economy', 'Business').")

# --- Medical Planning Agent Models ---
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
    id: Optional[str] = Field(None, description="Unique identifier for the medical plan option, e.g., 'MP_OPT_001'.")
    treatment_name: Optional[str] = Field("N/A", description="Name of the medical treatment or procedure.")
    estimated_cost_usd: Optional[str] = Field("N/A", description="Estimated total cost of the treatment in USD.")
    clinic_name: Optional[str] = Field("N/A", description="Name of the recommended clinic/hospital.")
    clinic_location: Optional[str] = Field("N/A", description="Location of the clinic/hospital (city, country).")
    required_recovery_days: int = Field(0, description="Minimum days required to stay in the city before flying safely (e.g. 10 for surgery, 1 for checkup).")
    visa_notes: Optional[str] = Field("N/A", description="Relevant notes about visa requirements for this plan.")
    brief_description: Optional[str] = Field("N/A", description="A brief summary of this medical plan option for the card.")
    full_hospital_details: HospitalDetails = Field(..., description="You MUST fill this with hospital certifications.")
    full_treatment_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    image_url: Optional[str] = Field(default=None, description="URL of the hospital/treatment image.")
    provenance: Optional[DataProvenance] = Field(None, description=PROVENANCE_DESCRIPTION)

class MedicalPlanningOutput(BaseModel):
    """Output schema for MedicalPlanningTool."""
    reasoning_scratchpad: str = Field(
        ...,
        description="YOUR INTERNAL THINKING PROCESS. Step 1: Feasibility Check. Step 2: Cost Comparison. Step 3: Selection Justification. You must fill this field FIRST."
    )
    medical_plan_options: List[MedicalPlanOption] = Field(default_factory=list, description="A list of structured medical plan options.")
    message: str = Field("Medical planning completed.", description="A message indicating the status of the medical planning process.")
    error: Optional[str] = Field(None, description="Error message if medical planning failed or is incomplete.")
    visa_information: Optional[VisaInfo] = Field(None, description="Detailed visa information based on nationality and destination.")

class MedicalPlanningLLMOutput(BaseModel):
    """
    A standard BaseModel to wrap the list of medical plan options.
    This is a more stable target for the LLM's with_structured_output.
    """
    medical_plan_options: List[MedicalPlanOption] = Field(default_factory=list, description="A list of synthesized medical plan options based on the prompt.")

# --- Travel Arrangement Agent Models ---
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
    reasoning_scratchpad: str = Field(
        ...,
        description="YOUR INTERNAL THINKING PROCESS. Step 1: Analyze dates. Step 2: Evaluate budget. Step 3: Match locations. You must fill this field FIRST."
    )
    medical_destination_city: Optional[str] = Field(None, description="City where the medical treatment will take place.")
    flight_suggestions: List[FlightOptionSummary] = Field(default_factory=list, description="List of suggested flight options.")
    accommodation_suggestions: List[AccommodationOption] = Field(default_factory=list, description="List of suggested accommodation options.")
    weather_info: WeatherData = Field(..., description="MUST be populated with weather data based on the tools.")
    visa_assistance_flag: bool = Field(..., description="Flag indicating if visa assistance was requested/considered.")
    visa_information: VisaInfo = Field(..., description="Detailed visa information fetched from the visa tool.")

    @model_validator(mode="after")
    def check_visa_fields(self) -> "TravelArrangementOutput":
        if self.error:
            return self

        if self.visa_assistance_flag and self.visa_information is None:
            # fix： raise ValueError("Visa information must be provided if visa assistance is requested and no error occurred.")
            pass
        return self
    
    message: str = Field("Travel arrangements planned.", description="A message indicating the planning status.")
    error: Optional[str] = Field(None, description="Error message if travel arrangement failed.")
    
class TravelArrangementLLMOutput(BaseModel):
    """
    A simplified model for the LLM to output ONLY the synthesized lists.
    Python code will handle assembly of weather, visa, and error fields.
    """
    flight_suggestions: List[FlightOptionSummary] = Field(default_factory=list, description="List of synthesized flight suggestions based on user preferences.")
    accommodation_suggestions: List[AccommodationOption] = Field(default_factory=list, description="List of synthesized accommodation suggestions based on user preferences.")

# --- Travel Logistics Agent Models  ---
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
    reasoning_scratchpad: str = Field(
        ...,
        description="YOUR INTERNAL THINKING PROCESS. Step 1: Analyze physical limitations. Step 2: Ensure dietary & accessibility match. You must fill this field FIRST."
    )
    status: str = Field(..., description="Overall status of the travel logistics planning (e.g., 'Completed', 'Partial', 'Failed').")
    airport_pick_up_details: Optional[TransportOption] = Field(None, description="Details of the recommended airport pick-up service.")
    local_transport_suggestions: List[TransportOption] = Field(default_factory=list, description="Suggested local medical transport options.")
    additional_local_services_suggestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Suggestions for additional local services (e.g., interpreters, nursing care).")
    dietary_recommendations: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Recommendations based on dietary needs (e.g., restaurants, grocery stores).")
    sim_card_assistance_info: Optional[Dict[str, Any]] = Field(None, description="Information regarding local SIM card assistance (e.g., providers, where to buy).")
    leisure_activity_suggestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Suggestions for leisure activities or sightseeing.")
    message: str = Field("Travel logistics planned.", description="A message indicating the status of the overall logistics process.")
    error: Optional[str] = Field(None, description="Error message if travel logistics planning failed or are incomplete.")

class TravelLogisticsLLMOutput(BaseModel):
    """
    A simplified model for the LLM to output ONLY the synthesized web search results.
    Python code will handle assembly of structured transport data, status, and errors.
    """
    additional_local_services_suggestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Suggestions for additional local services (e.g., interpreters, nursing care).")
    dietary_recommendations: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Recommendations based on dietary needs (e.g., restaurants, grocery stores).")
    sim_card_assistance_info: Optional[Dict[str, Any]] = Field(None, description="Information regarding local SIM card assistance (e.g., providers, where to buy).")
    leisure_activity_suggestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Suggestions for leisure activities or sightseeing.")
    
# --- Calculate Budget Tool Models ---
class CalculateBudgetInput(BaseModel):
    """Input schema for the CalculateBudgetTool."""
    session_state: dict = Field(..., description="The full session state JSON object containing all collected plan parameters.")

# --- Data Curator Agent Models ---
class CuratedData(BaseModel):
    items: List[Dict[str, Any]] = Field(description="A list of extracted entities (e.g., hospitals, clinics) containing their details.")

# --- Verification Agent Models ---
class VerificationOutput(BaseModel):
    reasoning_scratchpad: str = Field(
        ...,
        description="YOUR INTERNAL THINKING PROCESS. Step 1: Check locations. Step 2: Check dates. Step 3: Check budget. Fill this FIRST."
    )
    is_valid: bool = Field(..., description="Set to True ONLY if all checks pass.")
    feedback: str = Field(..., description="Detailed feedback on errors, or confirmation message.")

# --- Plan Evalutor Models ---
class AuditorVerdict(BaseModel):
    reasoning_scratchpad: str = Field(
        ...,
        description="YOUR AUDIT PROCESS. Evaluate Safety, Recovery Logic, Accessibility, and Finance step-by-step. Fill this FIRST."
    )
    score: float = Field(..., description="Score from 0.0 to 5.0, where 5.0 is perfect.")
    reason: str = Field(..., description="A concise, critical explanation of the verdict.")
    is_pass: bool = Field(..., description="True if score >= 4.0, False otherwise.")

#  Compliance Guardrails Models
class InputGuardOutput(BaseModel):
    """Result of the Input Guardrail check."""
    is_safe: bool = Field(..., description="True if the request is safe and legal to process.")
    risk_category: Optional[str] = Field(None, description="E.g., 'Illegal Medical Procedure', 'Harassment', 'Political'.")
    reason: str = Field(..., description="Explanation of why it was flagged or passed.")
    sanitized_input: Optional[str] = Field(None, description="If input needed minor cleaning, this is the safe version.")

class OutputGuardOutput(BaseModel):
    """Result of the Output Guardrail check."""
    is_compliant: bool = Field(..., description="True if the output contains necessary disclaimers and avoids diagnosis.")
    missing_disclaimers: List[str] = Field(default_factory=list, description="List of missing required legal statements.")
    correction_needed: bool = Field(False, description="If True, the agent must regenerate the response.")

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

class AgentState(TypedDict):
    """
    [LangChain 1.0+ Standard]
    The shared state for the Agent graph. Must be a TypedDict.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Context Data
    user_id: str
    session_id: str
    user_profile: Dict[str, Any]
    
    # Shared Workflow Data
    plan_data: Optional[Dict[str, Any]]
    compliance_flags: List[str]
    
    # Structured Outputs (Stored here after generation)
    structured_response: Optional[Dict[str, Any]]

class AgentResponse(BaseModel):
    message: str
    data: Any
    type: str

# USER PROFILE MASTER MODEL (The Single Source of Truth)
class UserPreferences(BaseModel):
    """
    User's long-term preferences, which may remain consistent across sessions.
    """
    dietary_needs: List[str] = Field(default_factory=list, description="E.g., ['Halal', 'Vegetarian', 'Gluten-Free']")
    accessibility_needs: List[str] = Field(default_factory=list, description="E.g., ['Wheelchair access', 'Ground floor']")
    medical_allergies: List[str] = Field(default_factory=list, description="E.g., ['Penicillin', 'Latex']")
    preferred_airlines: List[str] = Field(default_factory=list, description="E.g., ['Singapore Airlines', 'Qatar Airways']")
    preferred_hotel_tier: str = Field("Standard", description="E.g., 'Budget', 'Standard', 'Luxury'")
    preferred_language: str = Field("English", description="Preferred language for medical communication.")
    travel_class_preference: str = Field("Economy", description="E.g., 'Economy', 'Business'")
    leisure_interests: List[str] = Field(default_factory=list, description="Interests for recovery period (e.g., 'Museums', 'Nature')")

    @model_validator(mode='before')
    @classmethod
    def normalize_inputs(cls, data: Any) -> Any:
        """
        [Helper] Automatically convert comma-separated strings to lists, ensuring compatibility with legacy data.
        For example: "Vegetarian, Halal" -> ["Vegetarian", "Halal"]
        """
        if isinstance(data, dict):
            # 1. Dietary Needs Cleaning
            if "dietary_needs" in data and isinstance(data["dietary_needs"], str):
                if data["dietary_needs"].lower() in ["none", "null", ""]:
                    data["dietary_needs"] = []
                else:
                    data["dietary_needs"] = [x.strip() for x in data["dietary_needs"].split(",")]
            
            # 2. Accessibility Cleaning
            if "accessibility_needs" in data and isinstance(data["accessibility_needs"], str):
                if data["accessibility_needs"].lower() in ["none", "null", ""]:
                    data["accessibility_needs"] = []
                else:
                    data["accessibility_needs"] = [x.strip() for x in data["accessibility_needs"].split(",")]
                    
        return data

class TripContext(BaseModel):
    """
    Parameters for this specific trip (Session-specific context)。
    """
    origin_city: str = Field("Beijing", description="Where the user is flying from.") # Default fallback
    destination_country: str = Field("Malaysia", description="Target destination.")
    medical_destination_city: Optional[str] = Field(None, description="Specific city for treatment (e.g., 'Kuala Lumpur').")
    
    # Dates
    departure_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    travel_date_flexibility: str = Field("Fixed", description="E.g., 'Flexible', 'Fixed'")
    
    # Constraints
    estimated_budget_usd: Optional[str] = Field(None, description="Total budget constraint.")
    num_guests: int = Field(1, description="Total count including patient.")
    
    # Medical Specifics
    medical_purpose: str = Field("General Checkup", description="Main reason for travel (e.g., 'Heart Bypass').")
    treatment_urgency: str = Field("Elective", description="E.g., 'Urgent', 'Within 3 months'")
    
    # Logistics
    airport_pick_up_required: bool = Field(False)
    sim_card_needed: bool = Field(False)
    visa_assistance_required: bool = Field(False)

class UserProfile(BaseModel):
    """
    [Long-term Memory] User profile model.
    """
    user_id: str = Field(..., description="Unique identifier for the user.")
    session_id: str = Field(..., description="Current session/thread ID for conversation tracking.")
    
    name: str = Field("Guest", description="User's display name.")
    nationality: str = Field("Unknown", description="User's nationality for Visa checks.")
    age: Optional[int] = Field(None, description="User's age.")
    
    is_new_user: bool = Field(False, description="Flag indicating if this is a first-time user.")
    
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    current_trip: Optional[TripContext] = Field(None)
    
    medical_history: List[str] = Field(default_factory=list, description="Summary of past conditions.")
    past_trips: List[Dict[str, Any]] = Field(default_factory=list, description="History of previous trips.")
    
    planner_feedback: str = Field("", description="Feedback loop: Criticisms from Verification Agent.")

    @classmethod
    def _safe_list(cls, source_dict: Dict, *keys: str) -> List[str]:
        """Helper: Extract list from dict safely, handling comma-strings and None."""
        for k in keys:
            val = source_dict.get(k)
            if val is not None:
                if isinstance(val, list): return val
                if isinstance(val, str) and val.lower() != "none": 
                    return [x.strip() for x in val.split(",") if x.strip()]
        return []

    @classmethod
    def _patch_ids(cls, data: Dict) -> Dict:
        """Helper: Ensure user_id and session_id exist."""
        data["session_id"] = data.get("session_id") or data.get("thread_id") or data.get("user_id") or "default_session"
        data["user_id"] = data.get("user_id") or "unknown_user"
        return data

    @classmethod
    def _extract_preferences(cls, data: Dict) -> Dict:
        """Helper: Clean and extract user preferences."""
        raw_prefs = data.get("preferences", {})
        if not isinstance(raw_prefs, dict):
            raw_prefs = {}

        return {
            "dietary_needs": cls._safe_list(raw_prefs, "dietary", "dietary_needs") or cls._safe_list(data, "dietary_needs"),
            "accessibility_needs": cls._safe_list(raw_prefs, "mobility_needs", "accessibility_needs") or cls._safe_list(data, "accessibility_needs"),
            "medical_allergies": cls._safe_list(raw_prefs, "allergies", "medical_allergies") or cls._safe_list(data, "medical_allergies"),
            "travel_class_preference": raw_prefs.get("travel_class_preference") or data.get("travel_class_preference", "Economy"),
            "preferred_hotel_tier": raw_prefs.get("hotel_tier") or raw_prefs.get("preferred_hotel_tier") or data.get("preferred_hotel_tier", "Standard"),
            "preferred_airlines": cls._safe_list(raw_prefs, "airline_alliance", "preferred_airlines") or cls._safe_list(data, "preferred_airlines"),
            "preferred_language": raw_prefs.get("preferred_medical_language") or data.get("preferred_medical_language", "English"),
            "leisure_interests": cls._safe_list(raw_prefs, "leisure_activities_interest", "leisure_interests") or cls._safe_list(data, "leisure_activities_interest")
        }

    @classmethod
    def _extract_trip_context(cls, data: Dict) -> Optional[Dict]:
        """Helper: Build TripContext dictionary from scattered fields."""
        if "current_trip" in data and isinstance(data["current_trip"], dict):
            return data["current_trip"]
        
        raw_prefs = data.get("preferences", {})
        if not isinstance(raw_prefs, dict): raw_prefs = {}
        
        trip_keys = ["medicalPurpose", "medical_purpose", "destination_country", "estimatedBudget", "estimated_budget_usd"]
        
        # Only create trip context if relevant keys exist
        if not any(k in data or k in raw_prefs for k in trip_keys):
            return None

        trip = {
            "origin_city": data.get("origin_city") or data.get("originCity", "Beijing"),
            "destination_country": data.get("destination_country") or data.get("destinationCountry", "Malaysia"),
            "medical_destination_city": data.get("medical_destination_city") or data.get("medicalDestinationCity"),
            "medical_purpose": data.get("medical_purpose") or data.get("medicalPurpose", "General Checkup"),
            "estimated_budget_usd": str(data.get("estimated_budget_usd") or data.get("estimatedBudget") or data.get("estimated_budget") or ""),
            "departure_date": data.get("departure_date") or data.get("departureDate"),
            "return_date": data.get("return_date") or data.get("returnDate"),
            "num_guests": data.get("num_guests") or data.get("accompanyingGuests", 1)
        }
        
        # Merge existing trip object if present
        if "current_trip" in data and isinstance(data["current_trip"], dict):
            trip.update({k: v for k, v in data["current_trip"].items() if v})
            
        return trip

    @model_validator(mode='before')
    @classmethod
    def migrate_legacy_dict(cls, data: Any) -> Any:
        """
        [ETL Layer] Powerful cleaner: Ensures session_id exists and fixes the None list.
        """
        if not isinstance(data, dict):
            return data

        # 1. Patch IDs
        data = cls._patch_ids(data)
        
        # 2. Extract & Clean Sub-objects
        clean_prefs = cls._extract_preferences(data)
        trip_context = cls._extract_trip_context(data)

        # 3. Assemble Final Object
        # We construct a new dict to ensure clean validation by Pydantic
        return {
            "user_id": data["user_id"],
            "session_id": data["session_id"],
            "name": data.get("name", "Guest"),
            "nationality": data.get("nationality", "Unknown"),
            "is_new_user": data.get("is_new_user", False),
            "preferences": clean_prefs,
            "current_trip": trip_context,
            "medical_history": cls._safe_list(data, "medical_history"),
            "past_trips": data.get("past_trips", []),
            "planner_feedback": data.get("planner_feedback", "")
        }
    
# FINAL OUTPUT MODELS
class FinalProposal(BaseModel):
    """
    [Final Deliverable] The final, complete proposal structure.
    Used for front-end rendering and PDF generation.
    """
    document_title: str = Field(..., description="Title of the itinerary.")
    status: str = Field(..., description="Current status: 'Draft', 'Plan_Finalized', 'Blocked'.")
    total_estimated_budget_usd: float = Field(0.0, description="Calculated total cost.")
    currency: str = Field("USD", description="Currency code.")
    
    # Core Content Area
    itinerary_details: Dict[str, Any] = Field(default_factory=dict, description="Nested details of Medical, Flight, Hotel, Logistics.")
    
    # Compliance and Follow-up
    disclaimer: str = Field(..., description="Legal disclaimer text.")
    next_steps: List[str] = Field(default_factory=list, description="Actionable next steps for the user.")
    
    # Financial Details (Optional)
    financial_summary: Optional[Dict[str, Any]] = Field(None, description="breakdown of costs")