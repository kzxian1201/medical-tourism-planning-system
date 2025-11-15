# ai_service/src/agentic/graph/test_graph.py
import asyncio
from .graph import create_graph
from ..logger import logging 
from langgraph.checkpoint.memory import InMemorySaver

logging.info("--- [Graph Test] Initializing Checkpointer (main thread) ---")

async def run_test(): 
    """
    An independent asynchronous function used for unit testing our Graph.
    """
    logging.info("[Graph Test] Forcing InMemorySaver for stability.")
    memory = InMemorySaver()
    await _run_test_with(memory)

async def _run_test_with(checkpointer):
    logging.info("--- [Graph Test] Start unit test (inside async) ---")

    test_app = create_graph(checkpointer)
    config = {"configurable": {"thread_id": "test-session-12345"}}

    logging.info("[Graph Test] --- STAGE 1: STARTING PLAN ---")
    inputs_step1 = {
        "user_input": "I want to start planning",
        "user_profile": {
            "nationality": "Chinese",
            "medicalPurpose": "Heart Bypass Surgery",
            "estimatedBudget": "20000",
            "departureCity": "Beijing",
            "destination_country": "Malaysia",
            "departureDate": "2025-08-01",
            "returnDate": "2025-08-15", 
            "accompanyingGuests": 1
        },
        "current_stage": "start"
    }
    
    step1_output = await test_app.ainvoke(inputs_step1, config)
    logging.info(f"[Graph Test] Stage 1 Output Stage: {step1_output['current_stage']}")
    logging.info(f"[Graph Test] Stage 1 Message: {step1_output['last_agent_message'].content}")

    logging.info("[Graph Test] --- STAGE 2: SELECTING MEDICAL PLAN ---")
    
    test_app.update_state(
        config,
        {
            "user_input": "I'll choose MP_OPT_001",
            "current_stage": "medical_selection_pending",
            "selected_medical_plan_id": "MP_OPT_FALLBACK_001" 
        }
    )
    step2_output = await test_app.ainvoke(None, config) 
    
    logging.info(f"[Graph Test] Stage 2 Output Stage: {step2_output['current_stage']}")
    logging.info(f"[Graph Test] Stage 2 Message: {step2_output['last_agent_message'].content}")

    logging.info("[Graph Test] --- STAGE 3: SELECTING TRAVEL ---")
    
    test_app.update_state(
        config,
        {
            "user_input": "I'll take FLIGHT_001 and ACC_001",
            "current_stage": "travel_selection_pending",
            "selected_flight_id": "FLIGHT_FALLBACK_001", 
            "selected_accommodation_id": "ACC_FALLBACK_001" 
        }
    )
    step3_output = await test_app.ainvoke(None, config)
    
    logging.info(f"[Graph Test] Stage 3 Output Stage: {step3_output['current_stage']}")

    logging.info("[Graph Test] --- STAGE 4: CONFIRMING PLAN ---")
    
    test_app.update_state(
        config,
        {
            "user_input": "Yes, I confirm this plan.",
            "current_stage": "final_confirmation_pending"
        }
    )
    step4_output = await test_app.ainvoke(None, config)

    logging.info(f"[Graph Test] Stage 4 Output Stage: {step4_output['current_stage']}")
    
    final_state = await test_app.aget_state(config)
    logging.info(f"Final state keys: {final_state.values.keys()}")
    logging.info(f"Final selected medical plan: {final_state.values.get('final_selected_medical_plan')}")
    logging.info(f"Final budget: {final_state.values.get('final_budget')}")

if __name__ == "__main__":
    asyncio.run(run_test())