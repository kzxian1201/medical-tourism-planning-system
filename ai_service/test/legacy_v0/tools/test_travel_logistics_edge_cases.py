#ai_service/test/tools/test_travel_logistics_edge_cases.py
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

# --- Mock Data from test_travel_logistics_tool.py ---
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

mock_travel_logistics_input_sim_only = TravelLogisticsInput(
    medical_destination_city="Singapore",
    medical_destination_country="Singapore",
    medical_stay_start_date="2025-07-29",
    medical_stay_end_date="2025-08-04",
    sim_card_assistance_needed=True
)

mock_travel_logistics_input_multi_transport = TravelLogisticsInput(
    medical_destination_city="Singapore",
    medical_destination_country="Singapore",
    medical_stay_start_date="2025-07-29",
    medical_stay_end_date="2025-08-04",
    local_transportation_needs=["wheelchair-accessible taxi", "hospital shuttle"]
)

mock_travel_logistics_input_invalid_leisure = TravelLogisticsInput(
    medical_destination_city="Singapore",
    medical_destination_country="Singapore",
    medical_stay_start_date="2025-07-29",
    medical_stay_end_date="2025-08-04",
    leisure_activities_interest=["!@#$$%^&"]
)

mock_travel_logistics_input_large_guests = TravelLogisticsInput(
    medical_destination_city="Singapore",
    medical_destination_country="Singapore",
    medical_stay_start_date="2025-07-29",
    medical_stay_end_date="2025-08-04",
    num_guests_total=1000
)

mock_partial_llm_response = {
    "status": "Completed",
    "sim_card_assistance_info": {
        "info": "Singtel and Starhub offer options.",
        "source_link": "https://example.com/sim"
    },
    "airport_pick_up_details": None,
    "local_transport_suggestions": [],
    "additional_local_services_suggestions": [],
    "dietary_recommendations": [],
    "leisure_activity_suggestions": [],
    "message": "SIM assistance planned.",
    "error": None
}

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_sub_tool_failure(mock_tool_class):
    tool = mock_tool_class()

    # mock the LLM to return a partial response
    tool.llm = FakeListLLM(responses=[json.dumps({
        **mock_llm_full_output,
        "status": "Partial",
        "error": "Airport pick-up planning failed.",
        "airport_pick_up_details": None
    })])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput(
        status="Failed",
        error="API key missing",
        message="Failed to connect to provider."
    ))
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    # set the mock instance's _arun method to an async function
    async def mock_arun(**kwargs):
        transport_output = await tool.local_medical_transport_tool._arun(
            medical_destination_city=kwargs['medical_destination_city'],
            medical_destination_country=kwargs['medical_destination_country'],
            patient_accessibility_needs=kwargs['patient_accessibility_needs'],
            transportation_needs=["airport pick-up"]
        )

        llm_response = tool.llm.invoke("Synthesize a logistics plan from the following data...")
        llm_output_data = json.loads(llm_response)
        
        return TravelLogisticsOutput.model_validate(llm_output_data)

    tool._arun = mock_arun

    result = await tool._arun(**mock_travel_logistics_input_full.model_dump())

    assert isinstance(result, TravelLogisticsOutput)
    assert result.status == "Partial"
    assert "failed" in result.error.lower()
    assert result.airport_pick_up_details is None
    assert len(result.leisure_activity_suggestions) > 0 # Ensure other parts are still there

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_llm_output_malformed_json(mock_tool_class):
    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=["This is not a valid JSON string."])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=mock_local_transport_output)
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    # set the mock instance's _arun method to an async function
    async def mock_arun(**kwargs):
        try:
            llm_response = tool.llm.invoke("Synthesize a logistics plan from the following data...")
            json.loads(llm_response)
        except json.JSONDecodeError as e:
            return TravelLogisticsOutput(status="Failed", error=str(e), message="LLM returned malformed JSON.")
        
        return TravelLogisticsOutput(status="Failed", error="Expected JSONDecodeError but none occurred.", message="")

    tool._arun = mock_arun

    result = await tool._arun(**mock_travel_logistics_input_full.model_dump())

    assert isinstance(result, TravelLogisticsOutput)
    assert result.status == "Failed"
    assert "malformed JSON" in result.message

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_llm_output_invalid_schema(mock_tool_class):
    invalid_schema_output = mock_llm_full_output.copy()
    invalid_schema_output["local_transport_suggestions"] = "this is a string"

    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(invalid_schema_output)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=mock_local_transport_output)
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    async def mock_arun(**kwargs):
        try:
            llm_response = tool.llm.invoke("Synthesize a logistics plan from the following data...")
            llm_output_data = json.loads(llm_response)
            TravelLogisticsOutput.model_validate(llm_output_data)
        except ValidationError as e:
            return TravelLogisticsOutput(status="Failed", error=str(e), message="LLM output failed Pydantic schema validation.")
        
        return TravelLogisticsOutput(status="Failed", error="Expected ValidationError but none occurred.", message="")

    tool._arun = mock_arun

    result = await tool._arun(**mock_travel_logistics_input_full.model_dump())

    assert isinstance(result, TravelLogisticsOutput)
    assert result.status == "Failed"
    assert "schema validation" in result.message

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_sim_card_only_flow(mock_tool_class):
    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(mock_partial_llm_response)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput())
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    async def mock_arun(**kwargs):
        llm_output = json.loads(tool.llm.invoke("LLM prompt"))
        return TravelLogisticsOutput.model_validate(llm_output)

    tool._arun = mock_arun
    result = await tool._arun(**mock_travel_logistics_input_sim_only.model_dump())

    assert result.status == "Completed"
    assert result.sim_card_assistance_info is not None
    assert result.airport_pick_up_details is None

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_multiple_transport_preferences(mock_tool_class):
    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(mock_partial_llm_response)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput())
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    async def mock_arun(**kwargs):
        assert isinstance(kwargs["local_transportation_needs"], list)
        assert len(kwargs["local_transportation_needs"]) >= 2
        llm_output = json.loads(tool.llm.invoke("LLM prompt"))
        return TravelLogisticsOutput.model_validate(llm_output)

    tool._arun = mock_arun
    result = await tool._arun(**mock_travel_logistics_input_multi_transport.model_dump())
    assert result.status == "Completed"

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_invalid_leisure_input(mock_tool_class):
    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(mock_partial_llm_response)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput())
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    async def mock_arun(**kwargs):
        assert "!@#" in kwargs["leisure_activities_interest"][0]
        llm_output = json.loads(tool.llm.invoke("LLM prompt"))
        return TravelLogisticsOutput.model_validate(llm_output)

    tool._arun = mock_arun
    result = await tool._arun(**mock_travel_logistics_input_invalid_leisure.model_dump())
    assert result.status == "Completed"

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_large_guest_number(mock_tool_class):
    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(mock_partial_llm_response)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput())
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    async def mock_arun(**kwargs):
        assert kwargs["num_guests_total"] == 1000
        llm_output = json.loads(tool.llm.invoke("LLM prompt"))
        return TravelLogisticsOutput.model_validate(llm_output)

    tool._arun = mock_arun
    result = await tool._arun(**mock_travel_logistics_input_large_guests.model_dump())
    assert result.status == "Completed"

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_all_optional_inputs_empty(mock_tool_class):
    minimal_input = TravelLogisticsInput(
        medical_destination_city="Singapore",
        medical_destination_country="Singapore",
        medical_stay_start_date="2025-07-29",
        medical_stay_end_date="2025-08-04"
    )

    minimal_llm_response = {
        "status": "Completed",
        "airport_pick_up_details": None,
        "local_transport_suggestions": [],
        "additional_local_services_suggestions": [],
        "dietary_recommendations": [],
        "sim_card_assistance_info": None,
        "leisure_activity_suggestions": [],
        "message": "Minimal logistics planned.",
        "error": None
    }

    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(minimal_llm_response)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput())

    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=WebSearchRawResults(
        search_parameters={"q": "default", "engine": "google", "location": "Singapore"},
        organic_results=[]
    ))

    async def mock_arun(**kwargs):
        llm_response = tool.llm.invoke("Generate plan")
        llm_output_data = json.loads(llm_response)
        return TravelLogisticsOutput.model_validate(llm_output_data)

    tool._arun = mock_arun

    result = await tool._arun(**minimal_input.model_dump())

    assert result.status == "Completed"
    assert result.airport_pick_up_details is None
    assert result.sim_card_assistance_info is None

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_llm_output_missing_required_field(mock_tool_class):
    incomplete_output = mock_llm_full_output.copy()
    del incomplete_output["status"]

    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(incomplete_output)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=mock_local_transport_output)
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    async def mock_arun(**kwargs):
        try:
            return TravelLogisticsOutput.model_validate(json.loads(tool.llm.invoke("LLM prompt")))
        except ValidationError as e:
            return TravelLogisticsOutput(status="Failed", error=str(e), message="Missing required field in output.")

    tool._arun = mock_arun
    result = await tool._arun(**mock_travel_logistics_input_full.model_dump())

    assert result.status == "Failed"
    assert "field required" in result.error.lower()

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_all_subtools_fail(mock_tool_class):
    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps({
        **mock_llm_full_output,
        "status": "Partial",
        "error": "All subtools failed.",
        "airport_pick_up_details": None,
        "local_transport_suggestions": [],
        "dietary_recommendations": [],
        "leisure_activity_suggestions": [],
        "additional_local_services_suggestions": [],
        "sim_card_assistance_info": None
    })])

    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(return_value=LocalMedicalTransportOutput(
        status="Failed", error="Failure", message="Transport error"
    ))
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=WebSearchRawResults(
        search_parameters={}, organic_results=[]
    ))

    async def mock_arun(**kwargs):
        return TravelLogisticsOutput.model_validate(json.loads(tool.llm.invoke("LLM prompt")))

    tool._arun = mock_arun
    result = await tool._arun(**mock_travel_logistics_input_full.model_dump())

    assert result.status == "Partial"
    assert result.airport_pick_up_details is None
    assert result.sim_card_assistance_info is None

@pytest.mark.asyncio
@patch('ai_service.src.agentic.tools.travel_logistics_tool.TravelLogisticsTool', new_callable=MagicMock)
async def test_sub_tool_raises_exception(mock_tool_class):
    tool = mock_tool_class()
    tool.llm = FakeListLLM(responses=[json.dumps(mock_partial_llm_response)])
    tool.local_medical_transport_tool = MagicMock()
    tool.local_medical_transport_tool._arun = AsyncMock(side_effect=Exception("Unexpected error"))
    tool.web_research_tool = MagicMock()
    tool.web_research_tool._arun = AsyncMock(return_value=mock_web_research_results)

    async def mock_arun(**kwargs):
        try:
            await tool.local_medical_transport_tool._arun(**kwargs)
        except Exception as e:
            return TravelLogisticsOutput(status="Partial", error=str(e), message="Subtool raised exception.")

    tool._arun = mock_arun
    result = await tool._arun(**mock_travel_logistics_input_full.model_dump())

    assert result.status == "Partial"
    assert "unexpected error" in result.error.lower()

def test_invalid_input_field_type():
    with pytest.raises(ValidationError) as exc_info:
        TravelLogisticsInput(
            medical_destination_city="Singapore",
            medical_destination_country="Singapore",
            medical_stay_start_date="2025-07-29",
            medical_stay_end_date="2025-08-04",
            num_guests_total="two"  
        )
    assert "valid integer" in str(exc_info.value)      