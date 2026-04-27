#ai_service/test/tools/test_travel_logistics_tool.py
import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from pydantic import ValidationError

from ai_service.src.agentic.tools.travel_logistics_tool import TravelLogisticsTool
from ai_service.src.agentic.models import (
    TravelLogisticsInput, TravelLogisticsOutput,
    LocalMedicalTransportOutput,
    WebSearchRawResults, WebSearchResult,
    TransportOption
)
from ai_service.src.agentic.exception import CustomException
from langchain_core.language_models.fake import FakeListLLM

# --- Mock Data ---
mock_travel_logistics_input_full = TravelLogisticsInput(
    medical_destination_city="Singapore",
    medical_destination_country="Singapore",
    medical_stay_start_date="2025-07-29",
    medical_stay_end_date="2025-08-04",
    num_guests_total=2,
    airport_pick_up_required=True,
    local_transportation_needs=["wheelchair-accessible taxi"],
    additional_local_services_needed=["interpreter"],
    dietary_needs=["halal"],
    sim_card_assistance_needed=True,
    leisure_activities_interest=["city tours"],
    patient_accessibility_needs="wheelchair accessible"
)

mock_travel_logistics_input_partial = TravelLogisticsInput(
    medical_destination_city="Singapore",
    medical_destination_country="Singapore",
    medical_stay_start_date="2025-07-29",
    medical_stay_end_date="2025-08-04",
    num_guests_total=1,
    airport_pick_up_required=False,
    local_transportation_needs=None,
    additional_local_services_needed=None,
    dietary_needs=None,
    sim_card_assistance_needed=False,
    leisure_activities_interest=None,
    patient_accessibility_needs=None
)

mock_local_transport_output = LocalMedicalTransportOutput(
    status="Completed",
    message="Transport options found.",
    transport_options=[
        TransportOption(
            id="TRANS-APT-01",
            service_name="Grab Assist",
            type="wheelchair-accessible taxi",
            provider="Grab",
            estimated_cost_per_transfer_usd="$25 - $35",
            contact_info="https://www.grab.com/sg/transport/wheelchair/",
            notes="Price based on typical routes from Changi Airport.",
            country="Singapore",
            city="Singapore",
            accessibility_features=["wheelchair lift"]
        )
    ]
)

mock_web_research_results = WebSearchRawResults(
    search_parameters={
        "q": "Halal restaurants in Singapore",
        "engine": "google",
        "location": "Singapore"
    },
    organic_results=[
        WebSearchResult(
            title="Halal Restaurants in Singapore",
            snippet="Lau Pa Sat offers various halal options.",
            link="https://example.com/halal-sg"
        )
    ]
)

mock_llm_full_output = {
    "status": "Completed",
    "airport_pick_up_details": mock_local_transport_output.transport_options[0].model_dump(),
    "local_transport_suggestions": [t.model_dump() for t in mock_local_transport_output.transport_options],
    "additional_local_services_suggestions": [{
        "service_type": "interpreter",
        "provider_name": "Medi-Translate",
        "contact_info": "interpreter-sg.com",
        "notes": "Web search found several options for medical interpreters."
    }],
    "dietary_recommendations": [{
        "dietary_need": "halal",
        "suggestions": "A variety of halal restaurants and food stalls are available throughout Singapore.",
        "source_link": "https://halal-guide-sg.com"
    }],
    "sim_card_assistance_info": {
        "info": "Multiple providers like Singtel and Starhub offer tourist SIM cards.",
        "source_link": "https://sim-sg.com"
    },
    "leisure_activity_suggestions": [{
        "activity_name": "Gardens by the Bay",
        "accessibility_notes": "Wheelchair accessible paths and facilities.",
        "notes": "Consider a visit to Gardens by the Bay.",
        "source_link": "https://tours-sg.com/accessible"
    }],
    "message": "Travel logistics planned.",
    "error": None
}

mock_llm_partial_output = {
    "status": "Completed",
    "airport_pick_up_details": None,
    "local_transport_suggestions": [],
    "additional_local_services_suggestions": [],
    "dietary_recommendations": [],
    "sim_card_assistance_info": None,
    "leisure_activity_suggestions": [],
    "message": "Planned with limited input.",
    "error": None
}

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_full_logistics_plan_success(mock_tool_class):
    tool = mock_tool_class()

    tool.llm = FakeListLLM(responses=[json.dumps(mock_llm_full_output)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=mock_local_transport_output)
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)
    
    async def mock_arun(**kwargs):
        return TravelLogisticsOutput.model_validate(mock_llm_full_output)

    tool._arun = mock_arun

    result = await tool._arun(**mock_travel_logistics_input_full.model_dump())

    assert isinstance(result, TravelLogisticsOutput)
    assert result.status == "Completed"
    assert result.airport_pick_up_details.provider == "Grab"
    assert len(result.local_transport_suggestions) > 0
    assert len(result.dietary_recommendations) > 0


@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_logistics_plan_partial_input(mock_tool_class):
    tool = mock_tool_class()
    
    tool.llm = FakeListLLM(responses=[json.dumps(mock_llm_partial_output)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput(status="Completed", transport_options=[]))
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=WebSearchRawResults(search_parameters={"q": "empty", "engine": "google"}, organic_results=[]))

    async def mock_arun(**kwargs):
        return TravelLogisticsOutput.model_validate(mock_llm_partial_output)

    tool._arun = mock_arun

    result = await tool._arun(**mock_travel_logistics_input_partial.model_dump())

    assert isinstance(result, TravelLogisticsOutput)
    assert result.status == "Completed"
    assert result.airport_pick_up_details is None
    assert len(result.local_transport_suggestions) == 0
    assert result.sim_card_assistance_info is None   

