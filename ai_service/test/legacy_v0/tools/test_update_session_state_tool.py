#ai_service/test/tools/test_update_session_state_tool.py
import pytest
from pydantic import ValidationError
from ai_service.src.agentic.tools.update_session_state_tool import UpdateSessionStateTool, UpdateSessionStateInput

@pytest.fixture
def sample_session_state():
    return {
        "plan_parameters": {"medical_plan": {"id": "MP_001"}, "flight": {"id": "FL_001"}},
        "user_profile": {"name": "John Doe"}
    }

@pytest.fixture
def update_tool():
    return UpdateSessionStateTool()

# ---------------------- Tests ----------------------
def test_update_session_existing_plan(update_tool, sample_session_state):
    """Update an existing plan parameter in session state."""
    new_state = update_tool._run(session_state=sample_session_state, type="medical_plan", id="MP_999")
    assert new_state["plan_parameters"]["medical_plan"]["id"] == "MP_999"

def test_update_session_existing_user_profile(update_tool, sample_session_state):
    """Update an existing field in user profile."""
    new_state = update_tool._run(session_state=sample_session_state, type="name", id="Jane Doe")
    assert new_state["user_profile"]["name"] == "Jane Doe"

def test_update_session_new_field(update_tool, sample_session_state):
    """Add a new top-level field if type not in plan_parameters or user_profile."""
    new_state = update_tool._run(session_state=sample_session_state, type="insurance_plan", id="INS_001")
    assert new_state["insurance_plan"] == "INS_001"

def test_update_session_invalid_input(update_tool):
    """Invalid Pydantic input should raise ValidationError."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        update_tool.args_schema(type="", id="")

def test_update_session_arun_async(update_tool, sample_session_state):
    """Async _arun returns updated session state correctly."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result_state = loop.run_until_complete(update_tool._arun(session_state=sample_session_state, type="flight", id="FL_123"))
    assert result_state["plan_parameters"]["flight"]["id"] == "FL_123"
    loop.close()

def test_update_session_missing_plan_parameters(update_tool):
    """If session_state missing plan_parameters, should add new top-level field."""
    session_state = {"user_profile": {"name": "Alice"}}
    new_state = update_tool._run(session_state=session_state, type="medical_plan", id="MP_001")
    assert new_state["medical_plan"] == "MP_001"
