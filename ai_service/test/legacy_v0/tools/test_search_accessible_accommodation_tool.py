#ai_service/test/tools/test_search_accessible_accommodation_tool.py
import pytest
import os
import asyncio
from pydantic import ValidationError
from unittest.mock import patch

from ai_service.src.agentic.tools.search_accessible_accommodation_tool import AccessibleAccommodationTool
from ai_service.src.agentic.models import AccessibleAccommodationInput, AccessibleAccommodationOutput

# === Fixtures ===
@pytest.fixture(scope="module")
def tool():
    data_path = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'mock_accommodations.json')
    return AccessibleAccommodationTool(accommodation_data_file_path=data_path)

# === Unit Tests ===
def test_valid_search(tool):
    """
    Test case:
    Search for accommodations with valid input in Kuala Lumpur, Malaysia.
    Expected result: At least one accommodation option returned, no error.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Kuala Lumpur",
        destination_country="Malaysia",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05"
    )
    result = tool._run(tool_input=input_data)
    assert isinstance(result, AccessibleAccommodationOutput)
    assert len(result.accommodation_options) > 0
    assert result.error is None

def test_accessibility_needs_filtering(tool):
    """
    Test case:
    Search accommodations requiring 'Roll-in shower'.
    Expected result: All returned accommodations contain 'roll-in shower' in features.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Kuala Lumpur",
        destination_country="Malaysia",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05",
        accessibility_needs=["Roll-in shower"]
    )
    result = tool._run(tool_input=input_data)

    assert all(
        "roll-in shower" in [f.lower() for f in acc.accessibility_features]
        for acc in result.accommodation_options
    )

def test_accommodation_type_filtering(tool):
    """
    Test case:
    Search for 'serviced_apartment' type accommodations only.
    Expected result: All returned results are serviced apartments.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Kuala Lumpur",
        destination_country="Malaysia",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05",
        accommodation_type=["serviced_apartment"]
    )
    result = tool._run(tool_input=input_data)
    assert all(
        "serviced_apartment" in acc.accommodation_type
        for acc in result.accommodation_options
    )

def test_no_matches_found(tool):
    """
    Test case:
    Search in a non-existent city/country.
    Expected result: No accommodations returned, error message provided.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Nowhere",
        destination_country="Neverland",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05"
    )
    result = tool._run(tool_input=input_data)
    assert result.accommodation_options == []
    assert result.error is not None

def test_invalid_input_raises_validation_error():
    """
    Test case:
    Provide invalid input (wrong types, invalid date format).
    Expected result: Pydantic raises ValidationError.
    """
    with pytest.raises(ValidationError):
        AccessibleAccommodationInput(
            destination_city=123,  # invalid type
            destination_country="Japan",
            check_in_date="not-a-date",  # invalid format
            check_out_date="still-not-a-date"
        )

def test_pydantic_output_model_conformance(tool):
    """
    Test case:
    Ensure tool output conforms to AccessibleAccommodationOutput schema.
    Expected result: Pydantic validation passes without error.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Singapore",
        destination_country="Singapore",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05"
    )
    result = tool._run(tool_input=input_data)
    # Pydantic model will raise if invalid
    AccessibleAccommodationOutput(**result.model_dump())

def test_check_star_rating_range_filter(tool):
    """
    Test case:
    Search accommodations with star rating between 4 and 5.
    Expected result: All results have rating within 4–5.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Bangkok",
        destination_country="Thailand",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05",
        star_rating_min=4,
        star_rating_max=5
    )
    result = tool._run(tool_input=input_data)
    for acc in result.accommodation_options:
        assert 4 <= acc.star_rating <= 5

def test_kitchen_or_pet_friendly_flags(tool):
    """
    Test case:
    Filter accommodations requiring kitchen, then pet-friendly.
    Expected result: First result set only includes kitchen=1, second only pet_friendly=1.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Bangkok",
        destination_country="Thailand",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05",
        with_kitchen_req=True
    )
    result = tool._run(tool_input=input_data)
    for acc in result.accommodation_options:
        assert acc.with_kitchen == 1

    input_data.pet_friendly_req = True
    input_data.with_kitchen_req = None
    result = tool._run(tool_input=input_data)
    for acc in result.accommodation_options:
        assert acc.pet_friendly == 1

def test_landmark_matching(tool):
    """
    Test case:
    Search accommodations near 'Novena'.
    Expected result: All results are located in or mention 'Novena'.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Singapore",
        destination_country="Singapore",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05",
        nearby_landmarks="Novena"
    )
    result = tool._run(tool_input=input_data)
    assert all("novena" in acc.location.lower() or any("novena" in lm.lower() for lm in acc.nearby_landmarks or []) for acc in result.accommodation_options)


def test_estimated_total_cost_range_logic(tool):
    """
    Test case:
    Validate total cost estimation across multiple nights.
    Expected result: Correct cost range or single fixed value.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Jakarta",
        destination_country="Indonesia",
        check_in_date="2025-08-01",
        check_out_date="2025-08-06",  # 5 nights
    )
    result = tool._run(tool_input=input_data)
    for acc in result.accommodation_options:
        if " - " in acc.total_cost_estimate_usd:
            parts = acc.total_cost_estimate_usd.replace("$", "").split(" - ")
            min_val = float(parts[0])
            max_val = float(parts[1])
            assert max_val >= min_val
        elif acc.total_cost_estimate_usd.startswith("$"):
            value = float(acc.total_cost_estimate_usd.strip("$"))
            assert value >= 0

def test_build_accommodation_option_valid(tool):
    """
    Test case:
    Build accommodation option with valid cost and dates.
    Expected result: Correct total cost calculation.
    """
    mock_data = {
        "id": "acc001",
        "name": "Wheelchair Paradise",
        "location": "Downtown",
        "country": "Singapore",
        "city": "Singapore",
        "min_cost_per_night_usd": 100.0,
        "max_cost_per_night_usd": 150.0,
        "accessibility_features": ["Roll-in shower"],
        "availability": "Available for selected dates",
        "notes": "Fully accessible.",
    }
    tool._accommodation_options_db = [mock_data]
    
    input_data = AccessibleAccommodationInput(
        destination_city="Singapore",
        destination_country="Singapore",
        check_in_date="2025-08-01",
        check_out_date="2025-08-06"
    )

    result = tool._run(tool_input=input_data)
    assert len(result.accommodation_options) == 1
    acc = result.accommodation_options[0]
    assert acc.total_cost_estimate_usd == "$500.00 - $750.00"

def test_build_accommodation_option_skips_malformed_data(tool):
    """
    Test case:
    Skip malformed accommodation entry (missing cost).
    Expected result: No results returned, error message included.
    """
    malformed_data = {
        "id": "acc002",
        "name": "Broken Hotel",
        "location": "Uptown",
        "country": "Singapore",
        "city": "Singapore",
        "accessibility_features": ["Grab bars"],
        "availability": "Unknown",
        "notes": "Cost missing!"
    }
    tool._accommodation_options_db = [malformed_data]

    input_data = AccessibleAccommodationInput(
        destination_city="Singapore",
        destination_country="Singapore",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05"
    )
    result = tool._run(tool_input=input_data)
    assert len(result.accommodation_options) == 0
    assert result.error is not None or result.message.startswith("Search completed")

# === Async Event Loop & Runtime Error Handling ===
def test_run_handles_runtime_error():
    """
    Ensures the tool raises FileNotFoundError during initialization
    when the provided JSON file path does not exist.
    """
    with pytest.raises(FileNotFoundError) as exc_info:
        AccessibleAccommodationTool(accommodation_data_file_path="non_existent_file.json")
    
    assert "Accommodation data file not found" in str(exc_info.value)
    
def test_sync_run_wrapper_handles_event_loop(tool):
    # Simulate an existing running event loop (e.g., in Jupyter)
    async def mock_main():
        input_data = AccessibleAccommodationInput(
            destination_city="Singapore",
            destination_country="Singapore",
            check_in_date="2025-08-01",
            check_out_date="2025-08-05"
        )
        # Nested run
        return tool._run(tool_input=input_data)

    result = asyncio.run(mock_main())
    assert isinstance(result, AccessibleAccommodationOutput)

def test_invalid_date_range_returns_empty(tool):
    """
    Test case:
    Check-out date earlier than check-in date.
    Expected result: Accommodation skipped, empty results.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Singapore",
        destination_country="Singapore",
        check_in_date="2025-08-05",
        check_out_date="2025-08-01"
    )
    result = tool._run(tool_input=input_data)
    assert result.accommodation_options == []


def test_partial_feature_match_not_included(tool):
    """
    Test case:
    Accessibility needs require full match (e.g., 'Roll-in shower' and 'Grab bars').
    Expected result: Accommodations missing one of the features are excluded.
    """
    input_data = AccessibleAccommodationInput(
        destination_city="Kuala Lumpur",
        destination_country="Malaysia",
        check_in_date="2025-08-01",
        check_out_date="2025-08-05",
        accessibility_needs=["Roll-in shower", "Grab bars"]
    )
    result = tool._run(tool_input=input_data)
    assert all(
        all(need.lower() in [f.lower() for f in acc.accessibility_features] for need in ["Roll-in shower", "Grab bars"])
        for acc in result.accommodation_options
    )