# ai_service/test/agents/test_planning_agent.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

import ai_service.src.agentic.agents.planning_agent_terminal as planning_agent

@pytest.mark.asyncio
async def test_terminal_normal_case(monkeypatch):
    """Simulate terminal flow with mocked LLM returning structured JSON."""

    dummy_llm = MagicMock()
    monkeypatch.setattr(planning_agent.LoadModel, "load_llm_model", lambda: dummy_llm)

    fake_response = {
        "output": json.dumps({"message_type": "text", "content": {"prompt": "Test success"}})
    }
    dummy_executor = AsyncMock()
    dummy_executor.ainvoke.return_value = fake_response

    async def fake_get_planning_agent_executor(*args, **kwargs):
        return dummy_executor

    monkeypatch.setattr(planning_agent, "get_planning_agent_executor", fake_get_planning_agent_executor)

    # Directly call executor + _handle_agent_output
    response = await dummy_executor.ainvoke({"input": "hello"})
    final_output = planning_agent._handle_agent_output(response["output"], {})

    assert final_output["message_type"] == "text"
    assert "Test success" in final_output["content"]["prompt"]


@pytest.mark.asyncio
async def test_terminal_invalid_json_output(monkeypatch):
    """Simulate terminal flow where LLM returns invalid JSON string."""

    dummy_llm = MagicMock()
    monkeypatch.setattr(planning_agent.LoadModel, "load_llm_model", lambda: dummy_llm)

    fake_response = {"output": "not a json"}
    dummy_executor = AsyncMock()
    dummy_executor.ainvoke.return_value = fake_response

    async def fake_get_planning_agent_executor(*args, **kwargs):
        return dummy_executor

    monkeypatch.setattr(planning_agent, "get_planning_agent_executor", fake_get_planning_agent_executor)

    # Directly call executor + _handle_agent_output
    response = await dummy_executor.ainvoke({"input": "hello"})
    final_output = planning_agent._handle_agent_output(response["output"], {})

    # Expect error type if JSON decoding fails
    assert final_output["message_type"] == "error"
    assert "Invalid output format" in final_output["content"]["prompt"]

def test_handle_vague_input():
    """Test vague input handler 3 stages."""
    session = {}

    res1 = planning_agent.handle_vague_input("idk", session)
    assert "Could you specify" in res1["content"]["prompt"]

    res2 = planning_agent.handle_vague_input("I don't know", session)
    assert "popular destinations" in res2["content"]["prompt"]

    res3 = planning_agent.handle_vague_input("no idea", session)
    assert "cannot proceed" in res3["content"]["prompt"]


def test_departure_city_consistency_detects_mismatch():
    session_state = {"plan_parameters": {"departure_city": "Beijing"}}
    agent_output = {
        "content": {
            "travel_arrangement_response": {"departure_city": "Shanghai"}
        }
    }
    result = planning_agent.check_departure_city_consistency(agent_output, session_state)
    assert result is not None
    assert "mismatch" in result["content"]["prompt"]


def test_departure_city_consistency_no_issue():
    session_state = {"plan_parameters": {"departure_city": "Beijing"}}
    agent_output = {
        "content": {
            "travel_arrangement_response": {"departure_city": "Beijing"}
        }
    }
    result = planning_agent.check_departure_city_consistency(agent_output, session_state)
    assert result is None


def test_parse_date_valid_formats():
    assert planning_agent.parse_date("2024-05-01") == "2024-05-01"
    assert planning_agent.parse_date("01.05.2024") == "2024-05-01"
    assert planning_agent.parse_date("01-05-2024") == "2024-05-01"
    assert planning_agent.parse_date("05/01/2024") == "2024-05-01"


def test_parse_date_invalid_format():
    assert planning_agent.parse_date("May 1, 2024") is None


def test_handle_agent_output_with_json_and_mismatch(monkeypatch):
    session_state = {"plan_parameters": {"departure_city": "Beijing"}}
    bad_json = json.dumps({
        "content": {"travel_arrangement_response": {"departure_city": "Shanghai"}}
    })
    result = planning_agent._handle_agent_output(bad_json, session_state)
    assert "mismatch" in result["content"]["prompt"]


def test_handle_agent_output_dict(monkeypatch):
    session_state = {"plan_parameters": {"departure_city": "Beijing"}}
    agent_output = {"message_type": "text", "content": {"prompt": "Hello"}}
    result = planning_agent._handle_agent_output(agent_output, session_state)
    assert result == agent_output


def test_load_prompt_file_not_found(tmp_path):
    with pytest.raises(RuntimeError):
        planning_agent.load_prompt(str(tmp_path / "nonexistent.txt"))


def test_load_prompt_success(tmp_path):
    test_file = tmp_path / "prompt.txt"
    test_file.write_text("This is a prompt")
    result = planning_agent.load_prompt(str(test_file))
    assert "This is a prompt" in result
