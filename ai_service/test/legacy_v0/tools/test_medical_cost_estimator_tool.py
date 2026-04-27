# ai_service/test/tools/test_medical_cost_estimator_tool.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

from ai_service.src.agentic.tools.medical_cost_estimator_tool import MedicalCostEstimatorTool
from ai_service.src.agentic.tools.medical_db_search_tool import MedicalDBSearchTool
from ai_service.src.agentic.models import (
    MedicalCostEstimatorInput,
    MedicalCostEstimatorOutput,
    MedicalCost,
    MedicalDBSearchOutput,
    TreatmentDetails,
)
from ai_service.src.agentic.exception import CustomException
import sys

# Fixture for MedicalCostEstimatorTool instance
@pytest.fixture
def medical_cost_estimator_tool_instance():
    """
    Fixture to provide a MedicalCostEstimatorTool instance with a mocked MedicalDBSearchTool.
    """
    mock_db_searcher = AsyncMock(spec=MedicalDBSearchTool)

    # Define a side effect for the mock _arun method of MedicalDBSearchTool
    # This mock simulates different responses from the database searcher
    def mock_arun_side_effect(tool_input): # Updated to accept tool_input
        if tool_input.type == "treatment":
            if tool_input.name == "Dental Implants":
                return MedicalDBSearchOutput(
                    treatment_results=[
                        TreatmentDetails(
                            id="treat_001",
                            name="Dental Implants",
                            associated_specialties=["Dentistry"],
                            estimated_market_cost_range_usd_min=3000,
                            estimated_market_cost_range_usd_max=6000,
                            cost_unit="per implant"
                        )
                    ]
                )
            elif tool_input.name == "Appendectomy":
                return MedicalDBSearchOutput(
                    treatment_results=[
                        TreatmentDetails(
                            id="treat_002",
                            name="Appendectomy",
                            associated_specialties=["General Surgery"],
                            estimated_market_cost_range_usd_min=10000,
                            estimated_market_cost_range_usd_max=20000,
                            cost_unit="per procedure"
                        )
                    ]
                )
            elif tool_input.name == "Cardiac Bypass":
                return MedicalDBSearchOutput(
                    treatment_results=[
                        TreatmentDetails(
                            id="treat_003",
                            name="Cardiac Bypass",
                            associated_specialties=["Cardiology", "Cardiothoracic Surgery"],
                            estimated_market_cost_range_usd_min=50000,
                            estimated_market_cost_range_usd_max=None,
                            cost_unit="per procedure"
                        )
                    ]
                )
            elif tool_input.name == "Procedure With No Cost":
                return MedicalDBSearchOutput(
                    treatment_results=[
                        TreatmentDetails(
                            id="treat_004",
                            name="Procedure With No Cost",
                            associated_specialties=["General"],
                            estimated_market_cost_range_usd_min=None,
                            estimated_market_cost_range_usd_max=None,
                            cost_unit=None
                        )
                    ]
                )
        return MedicalDBSearchOutput(treatment_results=[])

    mock_db_searcher._arun.side_effect = mock_arun_side_effect
    # The _run mock needs to handle the input object as well
    mock_db_searcher._run.side_effect = lambda tool_input: asyncio.run(mock_arun_side_effect(tool_input))

    return MedicalCostEstimatorTool(db_searcher=mock_db_searcher)

@pytest.mark.asyncio
async def test_valid_procedure_name(medical_cost_estimator_tool_instance):
    procedure_name = "Dental Implants"
    # Call with Pydantic model
    result = await medical_cost_estimator_tool_instance._arun(tool_input=MedicalCostEstimatorInput(procedure_name=procedure_name))
    
    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == "Dental Implants"
    assert result.cost_estimation.estimated_cost_range_usd == "$3000 - $6000"
    assert "Based on 'Dental Implants' from database." in result.cost_estimation.notes

@pytest.mark.asyncio
async def test_procedure_with_location(medical_cost_estimator_tool_instance):
    procedure_name = "Appendectomy"
    location = "Kuala Lumpur"
    # Call with Pydantic model
    result = await medical_cost_estimator_tool_instance._arun(tool_input=MedicalCostEstimatorInput(procedure_name=procedure_name, location=location))

    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == "Appendectomy"
    assert result.cost_estimation.estimated_cost_range_usd == "$10000 - $20000"
    assert "Based on 'Appendectomy' from database." in result.cost_estimation.notes

@pytest.mark.asyncio
async def test_procedure_not_found(medical_cost_estimator_tool_instance):
    procedure_name = "NonExistent Procedure"
    # Call with Pydantic model
    result = await medical_cost_estimator_tool_instance._arun(tool_input=MedicalCostEstimatorInput(procedure_name=procedure_name))
    
    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == procedure_name
    assert result.cost_estimation.estimated_cost_range_usd == "N/A"
    assert "Cost information not found in the database for the exact procedure." in result.cost_estimation.notes
    assert result.cost_estimation.associated_specialties is None or result.cost_estimation.associated_specialties == []

@pytest.mark.asyncio
async def test_procedure_with_only_min_cost(medical_cost_estimator_tool_instance):
    procedure_name = "Cardiac Bypass"
    # Call with Pydantic model
    result = await medical_cost_estimator_tool_instance._arun(tool_input=MedicalCostEstimatorInput(procedure_name=procedure_name))
    
    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == "Cardiac Bypass"
    assert result.cost_estimation.estimated_cost_range_usd == "$50000"
    assert "Based on 'Cardiac Bypass' from database." in result.cost_estimation.notes

@pytest.mark.asyncio
async def test_procedure_with_no_cost_info_in_db_result(medical_cost_estimator_tool_instance):
    procedure_name = "Procedure With No Cost"
    # Call with Pydantic model
    result = await medical_cost_estimator_tool_instance._arun(tool_input=MedicalCostEstimatorInput(procedure_name=procedure_name))
    
    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == "Procedure With No Cost"
    assert result.cost_estimation.estimated_cost_range_usd == "N/A"
    assert "No specific cost information available for 'Procedure With No Cost'." in result.cost_estimation.notes

@pytest.mark.asyncio
async def test_pydantic_input_validation():
    mock_db_searcher = AsyncMock(spec=MedicalDBSearchTool)
    tool = MedicalCostEstimatorTool(db_searcher=mock_db_searcher)

    # Test missing procedure_name (handled by _arun directly for an informative error)
    # Call with Pydantic model
    result = await tool._arun(tool_input=MedicalCostEstimatorInput(procedure_name=""))
    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.error == "Missing 'procedure_name'."
    assert "Please provide a 'procedure_name' to estimate cost." in result.cost_estimation.notes
    assert result.cost_estimation.estimated_cost_range_usd == "N/A"

    # Test with valid input directly through the Pydantic schema
    valid_input = MedicalCostEstimatorInput(procedure_name="Test Procedure")
    assert valid_input.procedure_name == "Test Procedure"

    # Test what happens if non-string is passed to procedure_name (Pydantic will catch this)
    with pytest.raises(ValidationError):
        MedicalCostEstimatorInput(procedure_name=123)

@pytest.mark.asyncio
async def test_error_handling_db_search_tool_error():
    mock_db_searcher = AsyncMock(spec=MedicalDBSearchTool)

    def mock_error_side_effect(tool_input): # Updated to accept tool_input
        if tool_input.name.lower() == "procedure_error_mock":
            raise CustomException(
                error_message="Mocked MedicalDBSearchTool error",
                error_detail_sys=sys
            )
        return MedicalDBSearchOutput(treatment_results=[])

    mock_db_searcher._arun.side_effect = mock_error_side_effect
    mock_db_searcher._run.side_effect = lambda tool_input: asyncio.run(mock_error_side_effect(tool_input))

    tool = MedicalCostEstimatorTool(db_searcher=mock_db_searcher)

    procedure_name = "procedure_error_mock"
    # Call with Pydantic model
    result = await tool._arun(tool_input=MedicalCostEstimatorInput(procedure_name=procedure_name))

    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == procedure_name
    assert result.cost_estimation.estimated_cost_range_usd == "N/A"
    assert "An internal error occurred:" in result.cost_estimation.notes
    assert "Mocked MedicalDBSearchTool error" in result.error

@pytest.mark.asyncio
async def test_error_handling_general_exception():
    mock_db_searcher = AsyncMock(spec=MedicalDBSearchTool)
    
    mock_db_searcher._arun.side_effect = Exception("Simulated internal database error")

    tool = MedicalCostEstimatorTool(db_searcher=mock_db_searcher)

    procedure_name = "Procedure Causing Internal Error"
    # Call with Pydantic model
    result = await tool._arun(tool_input=MedicalCostEstimatorInput(procedure_name=procedure_name))

    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == procedure_name
    assert result.cost_estimation.estimated_cost_range_usd == "N/A"
    assert "An internal error occurred:" in result.cost_estimation.notes
    assert "Simulated internal database error" in result.error
    
    mock_db_searcher._arun.assert_called_once()

def test_sync_run_wrapper_handles_event_loop_cases(monkeypatch):
    mock_db_search_tool = MagicMock(spec=MedicalDBSearchTool)
    tool = MedicalCostEstimatorTool(db_searcher=mock_db_search_tool)

    tool._arun = AsyncMock(return_value=MedicalCostEstimatorOutput(
        cost_estimation=MedicalCost(
            procedure_name="Dental Implants",
            estimated_cost_range_usd="$1000 - $2000",
            notes="Mocked output"
        )
    ))

    def fake_asyncio_run(_):
        raise RuntimeError("Simulated asyncio.run() failure")

    monkeypatch.setattr(asyncio, "run", fake_asyncio_run)

    # Call with Pydantic model
    result = tool._run(tool_input=MedicalCostEstimatorInput(procedure_name="Dental Implants"))
    assert result.cost_estimation.estimated_cost_range_usd == "$1000 - $2000"

def test_run_handles_runtime_error(monkeypatch):
    class MockMedicalDBSearchTool(MedicalDBSearchTool):
        async def _arun(self, *args, **kwargs):
            return []

    async def fake_arun(self, tool_input): # Updated to accept tool_input
        return MedicalCostEstimatorOutput(
            cost_estimation=MedicalCost(
                procedure_name=tool_input.procedure_name,
                estimated_cost_range_usd="$5000 - $7000",
                notes="Based on mock data."
            ),
            error=None
        )

    class FakeLoop:
        def is_running(self): return False
        def run_until_complete(self, coro): return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)
        def set_debug(self, debug): pass

    monkeypatch.setattr("asyncio.get_event_loop", lambda: (_ for _ in ()).throw(RuntimeError("No loop")))
    monkeypatch.setattr("asyncio.new_event_loop", lambda: FakeLoop())
    monkeypatch.setattr("asyncio.set_event_loop", lambda loop: None)
    monkeypatch.setattr(
        "ai_service.src.agentic.tools.medical_cost_estimator_tool.MedicalCostEstimatorTool._arun",
        fake_arun
    )

    tool = MedicalCostEstimatorTool(db_searcher=MockMedicalDBSearchTool())
    # Call with Pydantic model
    result = tool._run(tool_input=MedicalCostEstimatorInput(procedure_name="Knee Replacement", location="Malaysia"))

    assert isinstance(result, MedicalCostEstimatorOutput)
    assert result.cost_estimation.procedure_name == "Knee Replacement"
    assert result.cost_estimation.estimated_cost_range_usd == "$5000 - $7000"