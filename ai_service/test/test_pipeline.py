# ai_service/test/test_pipeline.py
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# --- Path Setup & Env Load ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))

if project_root not in sys.path:
    sys.path.append(project_root)

env_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path=env_path)

from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.graph.graph import create_main_graph
from ai_service.src.agentic.models import UserProfile
from ai_service.src.agentic.utils.models_factory import get_auditor_model
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

def _read_json_sync(file_path: Path) -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json_sync(data: list, file_path: Path) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# LLM-as-a-Judge Semantic assertions
class SemanticVerdict(BaseModel):
    passed: bool = Field(..., description="True if the proposal logically satisfies ALL semantic requirements, False otherwise.")
    reason: str = Field(..., description="Detailed explanation of why it passed or failed.")

async def evaluate_semantics_with_llm(proposal_str: str, requirements: list, llm) -> SemanticVerdict:
    if not requirements:
        return SemanticVerdict(passed=True, reason="No semantic requirements specified.")
    
    prompt = ChatPromptTemplate.from_template("""
    You are a strict QA Test Evaluator.
    Review the following Final Proposal and determine if it satisfies ALL of these specific requirements:
    REQUIREMENTS:
    {requirements}
    
    PROPOSAL TO EVALUATE:
    {proposal}
    
    Be strict. If ANY requirement is ignored or violated, return passed=False.
    """)
    
    chain = prompt | llm.with_structured_output(SemanticVerdict)
    try:
        return await chain.ainvoke({
            "requirements": json.dumps(requirements, indent=2),
            "proposal": proposal_str
        })
    except Exception as e:
        return SemanticVerdict(passed=False, reason=f"LLM Judge failed to execute: {e}")

# Helper 1: Execute the word graph stream and grab events
async def _run_single_attempt(app, inputs: dict, runtime_config: dict) -> tuple[list, list, dict]:
    """Responsible for listening astream_events and collect route nodes, tool calls, and final state."""
    executed_nodes = []
    called_tools = []
    final_state = None
    
    try:
        async for event in app.astream_events(inputs, config=runtime_config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")
            
            if kind == "on_chain_end" and name in ["medical_dept", "travel_dept", "logistics_dept", "finalize"]:
                executed_nodes.append(name)
                
            if kind == "on_tool_start" and name not in ["LangGraph", "RunnableSequence", "medical_dept", "travel_dept", "logistics_dept"]:
                called_tools.append(name)
                
            if kind == "on_chain_end" and name == "LangGraph":
                final_state = event["data"].get("output", {})
    except Exception as e:
        raise RuntimeError(f"System Crash: {str(e)}")
        
    return executed_nodes, list(set(called_tools)), final_state

def _check_status_match(proposal: any, expected: dict) -> tuple[bool, str]:
    """Check if the status of the proposal matches the expected status."""
    if "must_trigger_status" not in expected:
        return True, ""
        
    actual_status = proposal.status if hasattr(proposal, 'status') else proposal.get("status", "Unknown")
    if actual_status != expected["must_trigger_status"]:
        return False, f"Status mismatch. Expected: {expected['must_trigger_status']}, Got: {actual_status}"
    return True, ""

def _check_forbidden_routes(expected: dict, executed_nodes: list) -> tuple[bool, list]:
    """Check if the proposal triggers any forbidden routes."""
    reasons = []
    if "forbidden_routes" in expected:
        for route in expected["forbidden_routes"]:
            if route in executed_nodes:
                reasons.append(f"Hit forbidden route: {route}")
    return len(reasons) == 0, reasons

def _check_required_tools(expected: dict, unique_tools: list) -> tuple[bool, list]:
    """Check if the proposal calls all required tools."""
    reasons = []
    if "must_call_tools" in expected:
        for req_tool in expected["must_call_tools"]:
            if req_tool not in unique_tools:
                reasons.append(f"Failed to call required tool: {req_tool}")
    return len(reasons) == 0, reasons

async def _evaluate_assertions(proposal: any, expected: dict, executed_nodes: list, unique_tools: list, judge_llm) -> tuple[bool, list]:
    """Evaluate the assertions on the proposal."""
    passed = True
    reasons = []
    
    # 1. Status assertion
    stat_pass, stat_reason = _check_status_match(proposal, expected)
    if not stat_pass:
        passed = False
        reasons.append(stat_reason)
            
    # 2. Route assertion
    route_pass, route_reasons = _check_forbidden_routes(expected, executed_nodes)
    if not route_pass:
        passed = False
        reasons.extend(route_reasons)
            
    # 3. Tool assertion
    tool_pass, tool_reasons = _check_required_tools(expected, unique_tools)
    if not tool_pass:
        passed = False
        reasons.extend(tool_reasons)
            
    # 4. Semantic assertion
    if passed and "semantic_requirements" in expected:
        proposal_str = proposal.model_dump_json() if hasattr(proposal, "model_dump_json") else json.dumps(proposal)
        print("   🤖 Invoking LLM Judge for semantic checks...")
        verdict = await evaluate_semantics_with_llm(proposal_str, expected["semantic_requirements"], judge_llm)
        if not verdict.passed:
            passed = False
            reasons.append(f"Semantic Check Failed: {verdict.reason}")
        else:
            print(f"   ✅ LLM Judge approved: {verdict.reason}")
            
    return passed, reasons

def _build_test_inputs(tc: dict) -> dict:
    """Build the initial state input for the test."""
    return {
        "messages": [HumanMessage(content=tc["user_input"])],
        "user_profile": UserProfile(**tc["profile"]),
        "data_update_queue": [],
        "status": "active",
        "current_stage": "init"
    }

async def _run_single_attempt_and_evaluate(inputs: dict, tc: dict, attempt: int, app, judge_llm) -> tuple[bool, list, str]:
    """Run a single LangGraph attempt and evaluate the results."""
    test_id = tc["test_id"]
    expected = tc.get("expected_behavior", {})
    
    runtime_config = {
        "configurable": {"thread_id": f"test_{test_id}_{uuid.uuid4().hex[:6]}"},
        "recursion_limit": 50
    }
    
    try:
        executed_nodes, unique_tools, final_state = await _run_single_attempt(app, inputs, runtime_config)
    except RuntimeError as e:
        return False, [str(e)], "Unknown"

    print(f"   🗺️ Path [Attempt {attempt}]: {' -> '.join(executed_nodes)}")
    print(f"   🛠️ Tools [Attempt {attempt}]: {unique_tools if unique_tools else 'None'}")

    if not final_state or "final_proposal" not in final_state:
        return False, ["No final proposal generated."], "Unknown"
        
    proposal = final_state["final_proposal"]
    actual_status = proposal.status if hasattr(proposal, 'status') else proposal.get("status", "Unknown")
    
    passed_this_attempt, current_reasons = await _evaluate_assertions(
        proposal, expected, executed_nodes, unique_tools, judge_llm
    )
    
    return passed_this_attempt, current_reasons, actual_status

async def _execute_test_case_with_retry(tc: dict, app, judge_llm, max_attempts: int = 2) -> dict:
    """Execute a single test case with retry logic."""
    test_id = tc["test_id"]
    print(f"\n⏳ Running Test: {test_id} - {tc['description']}")
    
    inputs = _build_test_inputs(tc)
    
    attempt = 1
    passed_final = False
    final_reasons = []
    actual_status = "Unknown"
    
    while attempt <= max_attempts and not passed_final:
        if attempt > 1:
            print(f"   ⚠️ Retrying {test_id} (Attempt {attempt}/{max_attempts})...")
            
        passed_this_attempt, current_reasons, status = await _run_single_attempt_and_evaluate(
            inputs, tc, attempt, app, judge_llm
        )
        
        actual_status = status
        if passed_this_attempt:
            passed_final = True
        else:
            final_reasons = current_reasons
            
        attempt += 1

    if passed_final:
        print(f"   🎉 RESULT: PASSED! (Status: {actual_status})")
    else:
        print(f"   ❌ RESULT: FAILED! Reasons: {final_reasons}")
        
    return {
        "test_id": test_id,
        "passed": passed_final,
        "attempts_used": attempt - 1,
        "status": actual_status,
        "errors": final_reasons
    }

# Main Test Pipeline Scheduler
async def run_evaluations():
    print("\n" + "="*60)
    print("🚀 INITIATING ADVANCED GOLDEN DATASET EVALUATION")
    print("   [Features: White-box Routing | Tool Auditing | LLM-as-a-Judge | Retry Loop]")
    print("="*60 + "\n")

    config = AppConfig.from_env()
    app = create_main_graph(config)
    judge_llm = get_auditor_model()
    
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    try:
        test_cases = await asyncio.to_thread(_read_json_sync, dataset_path)
    except FileNotFoundError:
        print(f"❌ Error: Dataset not found at {dataset_path}")
        return

    results_report = []

    for tc in test_cases:
        result = await _execute_test_case_with_retry(tc, app, judge_llm)
        results_report.append(result)

    print("\n" + "="*60)
    print("📊 TEST EXECUTION SUMMARY")
    print("="*60)
    total = len(results_report)
    passed_count = sum(1 for r in results_report if r["passed"])
    print(f"Total Cases: {total}")
    print(f"Passed:      {passed_count} ({passed_count/total*100:.1f}%)")
    print(f"Failed:      {total - passed_count}")
    
    report_path = Path(__file__).parent / "test_report.json"
    await asyncio.to_thread(_write_json_sync, results_report, report_path)
    print(f"📄 Detailed JSON report saved to {report_path}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_evaluations())

# run this: python -m ai_service.test.test_pipeline