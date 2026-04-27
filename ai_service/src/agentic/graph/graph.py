# ai_service/src/agentic/graph/graph.py
import logging
import asyncio
import re
import json
import uuid
from typing import Literal, Dict, Any, Set
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
# Production： from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.tools import BaseTool
from ai_service.src.agentic.graph.state import AgentState, GraphConfig, FinalProposal
from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.tools.calculate_budget_tool import create_calculate_budget_tool
from ai_service.src.agentic.evaluators.plan_evaluator import PlanEvaluator
from ai_service.src.agentic.graph.subgraphs.medical_subgraph import create_medical_subgraph
from ai_service.src.agentic.graph.subgraphs.travel_subgraph import create_travel_subgraph
from ai_service.src.agentic.graph.subgraphs.logistics_subgraph import create_logistics_subgraph

RouteResult = Literal["medical_dept", "travel_dept", "logistics_dept", "finalize", "__end__"]

_background_tasks: Set[asyncio.Task] = set()

def fire_and_forget_evaluation(evaluator: PlanEvaluator, run_id: str, plan_data: dict):
    """Safe, Asynchronous Background Task Trigger"""
    task = asyncio.create_task(evaluator.evaluate_run(run_id, plan_data))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

def _parse_budget_data(budget_json: Any) -> tuple[Dict, float]:
    """Helper: Parse budget data and extract total cost"""
    try:
        budget_data = json.loads(budget_json) if isinstance(budget_json, str) else budget_json
        total_budget = float(budget_data.get("total_estimated_budget_usd", 0.0))
        return budget_data, total_budget
    except Exception as e:
        logging.warning(f"Failed to parse budget for total cost: {e}")
        return budget_json, 0.0

def _check_if_flight_mocked(travel_options: Any) -> bool:
    """Helper: Check if flight data is mocked"""
    if not travel_options:
        return False
    
    t_dict = travel_options.model_dump() if hasattr(travel_options, "model_dump") else travel_options
    flight_data = t_dict.get("flight_suggestions", [])
    
    if flight_data and len(flight_data) > 0:
        first_flight = flight_data[0]
        prov = first_flight.get("provenance", {})
        return prov.get("is_mock_data", False)
    return False

def _get_valid_run_id(raw_session_id: str) -> str:
    """Helper: Get a valid UUID with fallback to random if invalid"""
    try:
        return str(uuid.UUID(raw_session_id))
    except (ValueError, TypeError):
        return str(uuid.uuid4())
    
def _build_dynamic_disclaimer(is_flight_mocked: bool, weather_data: Any) -> str:
    """Helper: Generate dynamic disclaimers based on context."""
    disclaimer = "This is an AI-generated itinerary. Please consult medical professionals before proceeding."
    if is_flight_mocked:
        disclaimer += " WARNING: Flight schedules are currently based on system estimates and require verification."
        
    if weather_data and isinstance(weather_data, dict):
        condition = str(weather_data).lower()
        if "rain" in condition or "storm" in condition:
            disclaimer += " [SAFETY ALERT]: Rainy weather detected in destination. To prevent post-op falls, we have prioritized door-to-door GrabAssist transport and indoor recovery activities."
        elif "32" in condition or "33" in condition or "hot" in condition:
            disclaimer += " [HEALTH ALERT]: High temperatures forecasted. Ensure wound areas are kept dry and cool to prevent infection; outdoor activities recommended only for early morning."
            
    return disclaimer

def _print_performance_report(proposal: FinalProposal):
    """Helper: Print performance report with RAG gaps"""
    print("\n" + "📊" * 15)
    print("PERFORMANCE REPORT:")
    gaps = [k for k, v in proposal.itinerary_details.items() if v is None]
    if gaps:
        print(f"⚠️  RAG DATA GAPS: {gaps}")
    print("📊" * 15 + "\n")

def make_input_guard_node(config: AppConfig):
    """Factory: Create input guard node"""
    def node_input_guard(state: AgentState) -> Dict[str, Any]:
        if not state.get("messages"):
            return {"status": "active"}
            
        last_msg = state["messages"][-1]
        content = str(last_msg.content).lower() if hasattr(last_msg, "content") else ""
        
        if any(kw in content for kw in config.domain.banned_keywords):
            logging.warning(f"⛔ Blocked input: {content[:50]}...")
            return {
                "status": "blocked",
                "error_message": "Policy Violation: Request contains prohibited keywords."
            }
        return {"status": "active"}
    return node_input_guard

def make_finalize_node(budget_tool: BaseTool, evaluator: PlanEvaluator):
    """Factory: Create finalize proposal node"""
    async def node_finalize_proposal(state: AgentState) -> Dict[str, Any]:
        try:
            if state.get("status") in ["error", "blocked"] or state.get("error_message"):
                error_msg = state.get("error_message", "Unknown system error occurred.")
                proposal = FinalProposal(
                    document_title="MediJourney Itinerary - ERROR",
                    status="Plan_Failed",
                    total_estimated_budget_usd=0.0,
                    currency="USD",
                    itinerary_details={
                        "medical": None,
                        "travel": None,
                        "logistics": None,
                        "budget_summary": None
                    },
                    disclaimer="This plan could not be generated due to a critical missing requirement.",
                    next_steps=["Please provide alternative dates or consult an agent."],
                )
                proposal.disclaimer = f"SYSTEM ERROR / VALIDATION FAILED: {error_msg}"
                return {"final_proposal": proposal, "status": "completed"}
            
            # Budget Calculation
            budget_json = await budget_tool.ainvoke({"session_state": state})
            budget_data, total_budget = _parse_budget_data(budget_json)

            # Determine Business Status & Next Steps
            current_status = state.get("status")
            is_insufficient = (current_status == "budget_insufficient")
            final_status = "Budget_Insufficient" if is_insufficient else "Plan_Finalized"
            next_steps = ["Revise Budget", "Consult Alternative Treatments"] if is_insufficient else ["Verify Visa Requirements", "Confirm Medical Appointment", "Book Flights"]

            # Dynamic Disclaimer Generation
            is_flight_mocked = _check_if_flight_mocked(state.get("travel_options"))
            disclaimer = _build_dynamic_disclaimer(is_flight_mocked, state.get("weather_info"))

            # Build Final Proposal Object
            proposal = FinalProposal(
                document_title="MediJourney Itinerary",
                status=final_status,
                total_estimated_budget_usd=total_budget,
                currency="USD",
                itinerary_details={
                    "medical": state.get("final_selected_medical_plan"),
                    "travel": state.get("travel_options"),
                    "logistics": state.get("logistics_plan"),
                    "budget_summary": budget_data
                },
                disclaimer=disclaimer,
                next_steps=next_steps
            )

            # Print Reporting & Trigger Evaluation
            _print_performance_report(proposal)
            run_id = _get_valid_run_id(str(state.get("session_id", "")))
            fire_and_forget_evaluation(evaluator, run_id, proposal.model_dump())
            
            return {"final_proposal": proposal, "status": "completed"}

        except Exception as e:
            logging.error(f"Finalize Failed: {e}", exc_info=True)
            return {"error_message": str(e), "status": "error"}
            
    return node_finalize_proposal

def make_output_guard_node():
    """Factory: Create output guard node (DLP + JSON Strict Validation)"""
    def node_output_guard(state: AgentState) -> Dict[str, Any]:
        """Node Logic: Sanitize and validate the final proposal output."""
        logging.info("🛡️ Running Output Guard (DLP & JSON Check)...")
        proposal = state.get("final_proposal")
        
        if not proposal:
            return {}

        try:
            safe_json_str = proposal.model_dump_json()
            safe_dict = json.loads(safe_json_str)
        except Exception as e:
            logging.error(f"❌ Output Guard JSON Validation Failed: {e}")
            return {"error_message": "Final proposal format corrupted.", "status": "error"}

        passport_pattern = re.compile(r'\b[A-Z]{1,2}\d{6,8}\b')
        
        def sanitize_strings(obj: Any) -> Any:
            """Recursively sanitize sensitive strings in a dictionary"""
            if isinstance(obj, str):
                return passport_pattern.sub("[REDACTED]", obj)
            elif isinstance(obj, dict):
                return {k: sanitize_strings(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_strings(i) for i in obj]
            return obj

        sanitized_dict = sanitize_strings(safe_dict)
        proposal_cleaned = FinalProposal(**sanitized_dict)
        
        return {"final_proposal": proposal_cleaned}
    return node_output_guard

def route_after_input_guard(state: AgentState) -> RouteResult:
    """Determine next route based on input guard status."""
    if state.get("status") == "blocked":
        return "finalize"
    return "medical_dept"

def route_after_medical(state: AgentState) -> RouteResult:
    """Check if medical planning was successful"""
    if state.get("status") == "error" or state.get("error_message"):
        logging.error(f"⛔ Route: Medical Error -> Routing to Finalize. Error: {state.get('error_message')}")
        return "finalize"
            
    if not state.get("final_selected_medical_plan"):
        logging.error("⛔ Route: No medical plan -> Routing to Finalize.")
        return "finalize"
    
    if state.get("status") == "budget_insufficient":
        logging.warning("🛑 Route: Budget Insufficient -> Skipping Travel & Logistics, routing to Finalize.")
        return "finalize"
            
    return "travel_dept"

def route_after_travel(state: AgentState) -> RouteResult:
    """Check travel planning status"""
    if state.get("status") == "error" or state.get("error_message"):
        logging.error(f"⛔ Route: Travel Error -> Routing to Finalize. Error: {state.get('error_message')}")
        return "finalize"
            
    flight = state.get("final_selected_flight")
    hotel = state.get("final_selected_accommodation")
        
    if not flight and not hotel:
        logging.warning("⚠️ Route: No travel options found -> Routing to Finalize.")
        return "finalize"
            
    return "logistics_dept"
    
def create_main_graph(config: AppConfig, checkpointer=None, enable_interrupts: bool = False):
    """
    [Master Graph Factory]
    CEO-level orchestrator: Assemble departmental subgraphs and compliance layers.
    """
    # Infrastructure Initialization
    budget_tool = create_calculate_budget_tool(config)
    plan_evaluator = PlanEvaluator(config)

    # Graph Declaration
    workflow = StateGraph(AgentState, config_schema=GraphConfig)

    # Node Registration
    workflow.add_node("input_guard", make_input_guard_node(config))
    workflow.add_node("medical_dept", create_medical_subgraph(config))
    workflow.add_node("travel_dept", create_travel_subgraph(config))
    workflow.add_node("logistics_dept", create_logistics_subgraph(config))
    workflow.add_node("finalize", make_finalize_node(budget_tool, plan_evaluator))
    workflow.add_node("output_guard", make_output_guard_node())

    # Connection and Routing Logic
    workflow.add_edge(START, "input_guard")
    
    workflow.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {"medical_dept": "medical_dept", "__end__": END})
    
    workflow.add_conditional_edges(
        "medical_dept",
        route_after_medical,
        {
            "travel_dept": "travel_dept",
            "finalize": "finalize",
            "__end__": END
        }
    )
    
    workflow.add_conditional_edges(
        "travel_dept",
        route_after_travel,
        {
            "logistics_dept": "logistics_dept",
            "finalize": "finalize",
            "__end__": END
        }
    )
    
    workflow.add_edge("logistics_dept", "finalize")
    workflow.add_edge("finalize", "output_guard")
    workflow.add_edge("output_guard", END)

    interrupt_nodes = []
    if enable_interrupts:
        if checkpointer is not None:
            interrupt_nodes = ["travel_dept", "logistics_dept", "finalize"]
            logging.info(f"🛑 HITL Interrupts Enabled before: {interrupt_nodes}")
        else:
            logging.warning("⚠️ enable_interrupts is True, but no checkpointer provided. Interrupts disabled.")

    if checkpointer is not None:
        app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_nodes if enable_interrupts else None
        )
    else:
        app = workflow.compile()
        
    return app