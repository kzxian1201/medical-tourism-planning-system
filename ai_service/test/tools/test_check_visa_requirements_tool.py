# ai_service/test/tools/test_check_visa_requirements_tool.py
import pytest
import asyncio
import json
import os
import sys
from unittest.mock import patch, mock_open
from pydantic import ValidationError

# Ensure sys.path includes the project root for correct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'agentic')))

from ai_service.src.agentic.tools.check_visa_requirements_tool import VisaRequirementsCheckerTool
from ai_service.src.agentic.models import VisaRequirementsInput, VisaRequirementsOutput, VisaInfo

# --- Fixtures ---
@pytest.fixture(autouse=True)
def mock_logging():
    """Mock logging to silence output and allow assertions."""
    with patch('ai_service.src.agentic.tools.check_visa_requirements_tool.logging') as mock_log:
        yield mock_log

@pytest.fixture
def visa_rules_content():
    """Load mock visa rules from test_data/mock_visa_rules.json."""
    test_data_path = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'mock_visa_rules.json')
    try:
        with open(test_data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        pytest.fail(f"mock_visa_rules.json not found at {test_data_path}")

@pytest.fixture
def visa_checker_tool_instance(visa_rules_content):
    """
    Provides a VisaRequirementsCheckerTool with _load_visa_rules patched
    to return mock data instead of reading from file.
    """
    with patch('ai_service.src.agentic.tools.check_visa_requirements_tool.VisaRequirementsCheckerTool._load_visa_rules') as mock_load_rules:
        mock_load_rules.return_value = visa_rules_content
        tool = VisaRequirementsCheckerTool(visa_rules_file_path="dummy.json")
        yield tool

# --- Core Test Cases ---
@pytest.mark.asyncio
async def test_visa_required_medical(visa_checker_tool_instance):
    """Test case: Chinese citizen traveling to Malaysia for medical purposes (visa required)."""
    input_data = VisaRequirementsInput(nationality="chinese", destination_country="malaysia", purpose="medical")
    result = await visa_checker_tool_instance._arun(input_data)
    assert result.visa_info.visa_required is True
    assert result.visa_info.visa_type == "Medical eVisa"

@pytest.mark.asyncio
async def test_visa_not_required_tourism(visa_checker_tool_instance):
    """Test case: Chinese citizen traveling to Malaysia for tourism (visa not required)."""
    input_data = VisaRequirementsInput(nationality="chinese", destination_country="malaysia", purpose="tourism")
    result = await visa_checker_tool_instance._arun(input_data)
    assert result.visa_info.visa_required is False
    assert result.visa_info.visa_type == "Visa-Free"

@pytest.mark.asyncio
async def test_visa_required_tourism(visa_checker_tool_instance):
    """Test case: Indian citizen traveling to Thailand for tourism (visa required)."""
    input_data = VisaRequirementsInput(nationality="indian", destination_country="thailand", purpose="tourism")
    result = await visa_checker_tool_instance._arun(input_data)
    assert result.visa_info.visa_required is True
    assert result.visa_info.visa_type == "Tourist Visa"

@pytest.mark.asyncio
async def test_default_rule_unmatched_combination(visa_checker_tool_instance):
    """Test case: Fallback to default rule if no match is found."""
    input_data = VisaRequirementsInput(nationality="unknown", destination_country="nowhere", purpose="study")
    result = await visa_checker_tool_instance._arun(input_data)
    assert result.visa_info.visa_required is False
    assert result.visa_info.visa_type == "Unknown"

@pytest.mark.asyncio
async def test_invalid_input_schema():
    """Test case: Missing required field should raise ValidationError."""
    with pytest.raises(ValidationError):
        VisaRequirementsInput(destination_country="malaysia", purpose="medical")

@pytest.mark.asyncio
async def test_unsupported_purpose(visa_checker_tool_instance):
    """Test case: Unsupported purpose should use default rule."""
    input_data = VisaRequirementsInput(nationality="chinese", destination_country="malaysia", purpose="work")
    result = await visa_checker_tool_instance._arun(input_data)
    assert result.visa_info.visa_type == "Unknown"

@pytest.mark.asyncio
async def test_case_insensitivity(visa_checker_tool_instance):
    """Test case: Input should be normalized to lowercase."""
    input_data = VisaRequirementsInput(nationality="ChInEsE", destination_country="MaLaYsIa", purpose="medical")
    result = await visa_checker_tool_instance._arun(input_data)
    assert result.nationality == "chinese"
    assert result.destination_country == "malaysia"

# --- New Error Handling Tests ---
def test_file_not_found_error():
    """Test case: Missing visa_rules.json should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        VisaRequirementsCheckerTool(visa_rules_file_path="nonexistent.json")

def test_invalid_json_format(visa_checker_tool_instance):
    """Test case: Invalid JSON input to _run should return VisaRequirementsOutput with error."""
    bad_json = "{invalid json"
    result = visa_checker_tool_instance._run(bad_json)
    assert result.error is not None
    assert "Invalid JSON input" in result.error

@pytest.mark.asyncio
async def test_invalid_rule_data_format(monkeypatch, visa_rules_content):
    """Test case: Malformed visa rule should trigger ValidationError inside _arun."""
    bad_rules = {"chinese_malaysia_medical": {"visa_required": 123}}  # invalid type
    monkeypatch.setattr(VisaRequirementsCheckerTool, "_load_visa_rules", lambda self: bad_rules)
    tool = VisaRequirementsCheckerTool("dummy.json")
    input_data = VisaRequirementsInput(nationality="chinese", destination_country="malaysia", purpose="medical")
    result = await tool._arun(input_data)
    assert result.error is not None
    assert "Invalid visa rule data format" in result.error
    assert result.visa_info.visa_required is True  # fallback path with error note

def test_sync_run_wrapper_handles_event_loop(visa_checker_tool_instance):
    """Test that _run works even if event loop is already running."""
    import asyncio

    async def runner():
        input_data = VisaRequirementsInput(
            nationality="chinese", destination_country="malaysia", purpose="medical"
        )
        # Call sync wrapper inside running loop
        result = visa_checker_tool_instance._run(input_data)
        assert isinstance(result, VisaRequirementsOutput)
        assert result.visa_info is not None

    asyncio.run(runner())

def test_run_handles_runtime_error(monkeypatch, visa_checker_tool_instance):
    """Test that _run gracefully handles unexpected runtime errors."""
    async def broken_arun(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(VisaRequirementsCheckerTool, "_arun", broken_arun)

    input_data = VisaRequirementsInput(
        nationality="chinese", destination_country="malaysia", purpose="medical"
    )
    result = visa_checker_tool_instance._run(input_data)
    assert result.error is not None
    assert "simulated failure" in result.error



