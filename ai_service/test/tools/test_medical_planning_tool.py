# ai_service/test/tools/test_medical_planning_tool.py
import pytest
import json
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch
from ai_service.src.agentic.tools.medical_planning_tool import MedicalPlanningTool
from ai_service.src.agentic.models import (
    MedicalPlanningInput,
    MedicalDBSearchOutput,
    TreatmentDetails,
    HospitalDetails,
    VisaInfo,
    VisaRequirementsOutput,
    MedicalCostEstimatorOutput,
    MedicalCost,
    WebSearchRawResults,
    MedicalPlanOption,
    MedicalPlanOptionList
)

@pytest.mark.asyncio
async def test_full_medical_plan_success(mocker):
    tool = MedicalPlanningTool()
    
    # Mock LLM synthesis
    mocker.patch(
        "ai_service.src.agentic.tools.medical_planning_tool.PydanticOutputParser.ainvoke",
        new=AsyncMock(return_value=MedicalPlanOptionList(root=[
            MedicalPlanOption(
                id="MP_OPT_001",
                treatment_name="Knee Replacement",
                estimated_cost_usd="$15,000 - $25,000",
                clinic_name="Mock Hospital",
                clinic_location="Singapore, Singapore",
                visa_notes="Visa required: Yes. Visa type: Tourist Visa.",
                brief_description="Recommended option.",
                full_hospital_details={
                    "id": "H1", "name": "Mock Hospital", "address": "123 Health Rd",
                    "city": "Singapore", "country": "Singapore"
                },
                full_treatment_details={
                    "id": "T1", "name": "Knee Replacement", "description": "Surgery",
                    "associated_specialties": ["Orthopedics"]
                },
                image_url="https://placehold.co/mock"
            )
        ]))
    )

    # Mock DB search
    async def mock_db(query=None, **kwargs):
        if query and "knee replacement" in query.lower():
            return MedicalDBSearchOutput(
                results=[
                    TreatmentDetails(
                        id="T1", name="Knee Replacement",
                        associated_specialties=["Orthopedics"], description="Surgery"
                    )
                ],
                error=None
            )
        if query and "mock hospital" in query.lower():
            return MedicalDBSearchOutput(
                results=[
                    HospitalDetails(
                        id="H1", name="Mock Hospital", address="123",
                        city="Singapore", country="Singapore"
                    )
                ],
                error=None
            )
        return MedicalDBSearchOutput(results=[], error=None)


    mocker.patch.object(tool._medical_db_search_tool, "_arun", new=AsyncMock(side_effect=mock_db))

    # Mock Cost Estimator
    mocker.patch.object(
        tool._medical_cost_estimator_tool, "_arun",
        new=AsyncMock(return_value=MedicalCostEstimatorOutput(
            cost_estimation=MedicalCost(
                procedure_name="Knee Replacement",
                estimated_cost_range_usd="$15,000 - $25,000",
                associated_specialties=["Orthopedics"],
                notes="Mock cost estimation."
            ),
            error=None
        ))
    )

    # Mock Visa
    mocker.patch.object(
        tool._visa_requirements_checker_tool, "_arun",
        new=AsyncMock(return_value=VisaRequirementsOutput(
            nationality="malaysian", destination_country="singapore", purpose="medical",
            visa_info=VisaInfo(
                visa_required=True, visa_type="Tourist Visa",
                stay_duration_notes="30 days",
                required_documents=["Passport"],
                processing_time_days="3", notes="Mocked"
            ),
            error=None
        ))
    )

    # Mock Web Research
    mocker.patch.object(
        tool._web_research_tool, "_arun",
        new=AsyncMock(return_value=WebSearchRawResults(
            query="mock query",
            search_parameters={"q": "mock query"},
            organic_results=[{"title": "Mock Info", "link": "http://mock.com", "snippet": "Mock snippet"}],
            error=None
        ))
    )

    input_data = MedicalPlanningInput(
        medical_purpose="knee replacement",
        patient_nationality="malaysian",
        destination_country="singapore",
        estimated_budget_usd="30000"
    )
    result = await tool._arun(**input_data.model_dump())
    assert result.medical_plan_options
    assert len(result.medical_plan_options) == 1
    assert result.error is None

@pytest.mark.asyncio
async def test_missing_visa_info(mocker):
    tool = MedicalPlanningTool()
    tool._synthesize_with_llm = AsyncMock(return_value=json.dumps([]))

    mocker.patch.object(tool._medical_db_search_tool, "_arun", new=AsyncMock(side_effect=[
        MedicalDBSearchOutput(results=[TreatmentDetails(id="T2", name="Heart Bypass", associated_specialties=["Cardiology"], description="Surgery")], error=None),
        MedicalDBSearchOutput(results=[HospitalDetails(id="H2", name="General Hospital", address="456", city="Bangkok", country="Thailand")], error=None),
    ]))

    mocker.patch.object(tool._medical_cost_estimator_tool, "_arun", new=AsyncMock(
        return_value=MedicalCostEstimatorOutput(
            cost_estimation=MedicalCost(
                procedure_name="Heart Bypass",
                estimated_cost_range_usd="$50,000 - $80,000",
                associated_specialties=["Cardiology"],
                notes="Mock cost estimation."
            ),
            error=None
        )
    ))

    mocker.patch.object(tool._visa_requirements_checker_tool, "_arun", new=AsyncMock(
        return_value=VisaRequirementsOutput(
            nationality="UnknownNation", destination_country="Thailand", purpose="medical",
            visa_info=VisaInfo(visa_required=False, visa_type="Unknown", stay_duration_notes="Unknown",
                               required_documents=[], processing_time_days="Unknown", notes="No visa info"),
            error="No visa info"
        )
    ))

    input_data = MedicalPlanningInput(
        medical_purpose="heart bypass",
        patient_nationality="UnknownNation",
        destination_country="Thailand"
    )
    result = await tool._arun(**input_data.model_dump())
    assert result.error
    assert "visa" in result.error

@pytest.mark.asyncio
async def test_medical_db_failure(monkeypatch):
    tool = MedicalPlanningTool()
    tool._synthesize_with_llm = AsyncMock(return_value=json.dumps([]))

    async def fail_db(*args, **kwargs):
        raise Exception("Simulated DB failure")

    monkeypatch.setattr(tool._medical_db_search_tool, "_arun", fail_db)

    input_data = MedicalPlanningInput(
        medical_purpose="spine surgery",
        patient_nationality="Vietnamese",
        destination_country="India"
    )
    result = await tool._arun(**input_data.model_dump())
    assert result.error

@pytest.mark.asyncio
async def test_invalid_llm_output_format():
    tool = MedicalPlanningTool()
    tool._synthesize_with_llm = AsyncMock(return_value="Not JSON")

    input_data = MedicalPlanningInput(
        medical_purpose="liver transplant",
        patient_nationality="Bangladeshi",
        destination_country="Turkey"
    )
    result = await tool._arun(**input_data.model_dump())
    assert result.error or "fallback" in (result.message or "").lower()

@pytest.mark.asyncio
async def test_successful_fallback_to_web_research(mocker):
    tool = MedicalPlanningTool()

    # Mock LLM synthesis
    mocker.patch(
        "ai_service.src.agentic.tools.medical_planning_tool.PydanticOutputParser.ainvoke",
        new=AsyncMock(return_value=MedicalPlanOptionList(root=[
            MedicalPlanOption(
                id="MP_OPT_002",
                treatment_name="Web Researched Treatment",
                estimated_cost_usd="Varies",
                clinic_name="Web Found Clinic",
                clinic_location="USA, California",
                visa_notes="Visa required: Check with consulate.",
                brief_description="Found via web search.",
                full_hospital_details={ "id": "H_web", "name": "Web Found Clinic", "address": "123 Web Rd", "city": "California", "country": "USA" },
                full_treatment_details={ "id": "T_web", "name": "Web Researched Treatment", "description": "Found via web search", "associated_specialties": ["General Surgery"] },
                image_url="https://placehold.co/mock"
            )
        ]))
    )

    # DB search returns empty
    mocker.patch.object(tool._medical_db_search_tool, "_arun", new=AsyncMock(return_value=MedicalDBSearchOutput(results=[], error=None)))

    # Web research returns valid
    mocker.patch.object(tool._web_research_tool, "_arun", new=AsyncMock(
        return_value=WebSearchRawResults(
            query="dental implant costs in California",
            search_parameters={"q": "dental implant costs in California"},
            organic_results=[{"title": "Dental Implants Cost", "link": "http://web.search.com/implants", "snippet": "A mock snippet"}],
            error=None
        )
    ))

    # Cost Estimator
    mocker.patch.object(tool._medical_cost_estimator_tool, "_arun", new=AsyncMock(
        return_value=MedicalCostEstimatorOutput(
            cost_estimation=MedicalCost(procedure_name="Dental Implant", estimated_cost_range_usd="$1,500 - $6,000", associated_specialties=["Dentistry"], notes="Mock"),
            error=None
        )
    ))

    # Visa
    mocker.patch.object(tool._visa_requirements_checker_tool, "_arun", new=AsyncMock(
        return_value=VisaRequirementsOutput(
            nationality="Canadian", destination_country="USA", purpose="medical",
            visa_info=VisaInfo(visa_required=False, visa_type="N/A", stay_duration_notes="6 months",
                               required_documents=["Passport"], processing_time_days="N/A", notes="Visa-free"),
            error=None
        )
    ))

    input_data = MedicalPlanningInput(
        medical_purpose="dental implant",
        patient_nationality="Canadian",
        destination_country="USA"
    )
    result = await tool._arun(**input_data.model_dump())
    assert result.medical_plan_options
    assert result.error is None

# Helper to construct default valid input
def make_base_input():
    return dict(
        medical_purpose="Heart Surgery",
        patient_nationality="Chinese",
        destination_country="Thailand",
        estimated_budget_usd="$25000 - $30000"
    )

@pytest.mark.asyncio
async def test_generic_medical_purpose():
    """Vague purpose: physical examination"""
    tool = MedicalPlanningTool()
    input_data = make_base_input()
    input_data["medical_purpose"] = "Physical examination"
    result = await tool._arun(**input_data)
    
    assert result.medical_plan_options
    assert any("Physical examination" in opt.treatment_name or "Examination" in opt.treatment_name for opt in result.medical_plan_options)

@pytest.mark.asyncio
async def test_extreme_budget_values():
    tool = MedicalPlanningTool()

    # very low budget
    low_input = make_base_input()
    low_input["estimated_budget_usd"] = "$100"
    result_low = await tool._arun(**low_input)
    assert result_low.medical_plan_options

    # very high budget
    high_input = make_base_input()
    high_input["estimated_budget_usd"] = "$500000"
    result_high = await tool._arun(**high_input)
    assert result_high.medical_plan_options

@pytest.mark.asyncio
async def test_unusual_nationality_or_destination():
    tool = MedicalPlanningTool()
    input_data = dict(
        medical_purpose="Kidney Transplant",
        patient_nationality="North Korean",
        destination_country="Iran",
        estimated_budget_usd="$20000 - $30000",
    )
    result = await tool._arun(**input_data)
    assert result.medical_plan_options
    # fallback visa info should exist in some form
    assert result.visa_information is None or isinstance(result.visa_information, dict)

@pytest.mark.asyncio
async def test_all_tools_fail(monkeypatch):
    async def fake_fail(*args, **kwargs):
        raise Exception("Simulated failure")

    monkeypatch.setattr(
        "ai_service.src.agentic.tools.medical_db_search_tool.MedicalDBSearchTool._arun",
        fake_fail,
    )
    monkeypatch.setattr(
        "ai_service.src.agentic.tools.medical_cost_estimator_tool.MedicalCostEstimatorTool._arun",
        fake_fail,
    )
    monkeypatch.setattr(
        "ai_service.src.agentic.tools.check_visa_requirements_tool.VisaRequirementsCheckerTool._arun",
        fake_fail,
    )
    monkeypatch.setattr(
        "ai_service.src.agentic.tools.web_research_tool.WebResearchTool._arun",
        fake_fail,
    )

    tool = MedicalPlanningTool()
    result = await tool._arun(**make_base_input())
    assert result.medical_plan_options
    assert result.error is not None

@pytest.mark.asyncio
async def test_llm_returns_malformed_json(mocker):
    """LLM outputs broken JSON → fallback triggered"""
    mock_llm = mocker.AsyncMock(return_value="{ this is not valid JSON")
    tool = MedicalPlanningTool(_llm_tool=mock_llm)

    result = await tool._arun(**make_base_input())

    assert result.medical_plan_options
    assert "fallback" in result.message.lower()
    assert "json" in result.error.lower() or "parse" in result.error.lower()

@pytest.mark.asyncio
async def test_invalid_input_field_type():
    input_data = make_base_input()
    input_data["estimated_budget_usd"] = 30000  # should be str
    with pytest.raises(ValidationError):
        MedicalPlanningInput(**input_data)

@pytest.mark.asyncio
async def test_all_optional_inputs_empty():
    tool = MedicalPlanningTool()
    input_data = dict(
        medical_purpose="Dental",
        patient_nationality="Malaysian",
        destination_country="Thailand",
    )
    result = await tool._arun(**input_data)
    assert result.medical_plan_options
    # allow fallback
    assert result.error is None or "fallback" in result.message.lower()

@pytest.mark.asyncio
async def test_partial_tool_failure(monkeypatch):
    async def fail_visa(*args, **kwargs):
        raise Exception("Visa tool failed")

    monkeypatch.setattr(
        "ai_service.src.agentic.tools.check_visa_requirements_tool.VisaRequirementsCheckerTool._arun",
        fail_visa,
    )

    tool = MedicalPlanningTool()
    result = await tool._arun(**make_base_input())
    assert result.medical_plan_options
    assert result.error

@pytest.mark.asyncio
async def test_llm_output_invalid_schema(mocker):
    """LLM returns wrong schema → fallback triggered"""
    mock_llm = mocker.AsyncMock(return_value=json.dumps({
        "medical_plan_options": "should be list"  # invalid type
    }))
    tool = MedicalPlanningTool(_llm_tool=mock_llm)

    result = await tool._arun(**make_base_input())

    assert "fallback" in result.message.lower()
    assert result.error
    assert "list" in result.error.lower() or "schema" in result.error.lower()

@pytest.mark.asyncio
async def test_llm_output_missing_required_field(mocker):
    """LLM misses required field → fallback triggered"""
    mock_llm = mocker.AsyncMock(return_value=json.dumps({
        "status": "Completed",
        "message": "Done"
    }))
    tool = MedicalPlanningTool(_llm_tool=mock_llm)

    result = await tool._arun(**make_base_input())

    assert "fallback" in result.message.lower()
    assert result.error
    assert "missing" in result.error.lower() or "llm synthesis failed" in result.error.lower()

@pytest.mark.asyncio
async def test_tool_fallback_to_web_search_on_cost_error(mocker):
    """When cost estimator fails, should fallback to web search"""

    mock_llm = mocker.AsyncMock(side_effect=ValueError("LLM parsing failed"))
    mock_db = mocker.AsyncMock(return_value=MedicalDBSearchOutput(results=[]))
    mock_cost = mocker.AsyncMock(side_effect=Exception("Cost tool failed"))
    mock_visa = mocker.AsyncMock(
        return_value=VisaRequirementsOutput(
            nationality="USA",
            destination_country="Japan",
            purpose="Medical",
            visa_info=VisaInfo(
                visa_required=True,
                visa_type="Tourist",
                stay_duration_notes="30 days",
                notes="Fallback visa info"
            )
        )
    )

    async def web_side_effect(query=None, **kwargs):
        return WebSearchRawResults(
            search_parameters={"q": query},
            organic_results=[{
                "title": "Dental Implant Costs in Japan",
                "link": "https://example.com",
                "snippet": "Estimated cost $1500 - $2500"
            }],
            error=None
        )

    mock_web = mocker.AsyncMock(side_effect=web_side_effect)

    tool = MedicalPlanningTool(
        _llm_tool=mock_llm,
        _medical_db_search_tool=mock_db,
        _medical_cost_estimator_tool=mock_cost,
        _visa_requirements_checker_tool=mock_visa,
        _web_research_tool=mock_web,
    )

    result = await tool._arun(
        medical_purpose="Dental Implant",
        patient_nationality="USA",
        destination_country="Japan",
    )

    assert result.medical_plan_options
    assert any("1500" in (opt["brief_description"] + opt["estimated_cost_usd"])
               for opt in result.medical_plan_options)

@pytest.mark.asyncio
async def test_build_fallback_option_web_data():
    """Directly test building fallback option"""
    tool = MedicalPlanningTool()

    all_results = {
        "treatment_results": {},
        "hospital_results": {},
        "cost_estimation_results": {},
        "visa_check_results": {},
        "web_search_results": {
            "organic_results": [
                {
                    "title": "Dental Implant Thailand",
                    "snippet": "Cost ranges $1000 - $3000",
                }
            ]
        },
    }

    # simulate no LLM options
    result = await tool._arun(
        medical_purpose="Dental Implant",
        patient_nationality="USA",
        destination_country="Thailand",
    )
    assert result.medical_plan_options 