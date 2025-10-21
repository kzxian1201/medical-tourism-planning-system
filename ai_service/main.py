# ai_service/main.py
import sys
import logging
import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# --- Custom Imports from local modules ---
from ai_service.src.agentic.logger import logging
from ai_service.src.agentic.exception import CustomException
from ai_service.src.agentic.agents.planning_agent import get_planning_agent_executor, _handle_agent_output
from ai_service.src.agentic.models import NextStepRequest, AgentResponse, LoadSessionRequest 

# Initialize a simple in-memory database for session state and history
sessions_db: Dict[str, Dict[str, Any]] = {}

# Initialize FastAPI app
app = FastAPI(
    title="Medical Tourism AI Agent Service",
    description="API for a unified AI agent designed for comprehensive medical tourism planning.",
    version="1.0.0",
)

# Middleware to handle CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A global variable to hold the agent executor instance
planning_agent_executor = None

@app.on_event("startup")
async def startup_event():
    """
    Event hook that runs once when the application starts.
    We use this to initialize the agent asynchronously.
    """
    global planning_agent_executor
    try:
        logging.info("Initializing Planning Agent...")
        planning_agent_executor = await get_planning_agent_executor()
        logging.info("Planning Agent initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Planning Agent: {e}", exc_info=True)
        # In a production app, you might want to raise an exception to halt startup
        # For now, we'll just log and continue, but the agent won't work.

@app.post("/api/v1/plan/next-step", response_model=AgentResponse)
async def next_step(body: NextStepRequest):
    """
    Main endpoint for driving the AI planning conversation.
    Processes user input and current session state to generate the next response.
    """
    global planning_agent_executor
    if planning_agent_executor is None:
        raise HTTPException(status_code=503, detail="Agent is not yet initialized.")

    session_id = body.session_id
    user_input = body.user_input

    # --- Step 1: Handle Session State ---
    if session_id not in sessions_db:
        logging.info(f"Initializing new session for ID: {session_id}")
        sessions_db[session_id] = {
            "chat_history": [],
            "session_state": {
                "current_stage": "initial_welcome",
                "plan_parameters": {}
            }
        }
        profile_data = body.session_state.get("profileData", {})
        if profile_data:
            injected_message = (
                f"User Profile data received and confirmed: "
                f"Nationality: {profile_data.get('nationality', 'N/A')}, "
                f"Medical Purpose: {profile_data.get('medicalPurpose', 'N/A')}, "
                f"Estimated Budget: {profile_data.get('estimatedBudget', 'N/A')}, "
                f"Departure City: {profile_data.get('departureCity', 'N/A')}. "
                f"Based on this, start the conversation by confirming these details with the user and asking for confirmation before proceeding."
            )
            sessions_db[session_id]["chat_history"].append(SystemMessage(content=injected_message))
    
    # Load state from mock database
    session_data = sessions_db[session_id]
    lc_chat_history = session_data["chat_history"]
    session_state = session_data["session_state"]
    
    # Append the new user input to the chat history
    lc_chat_history.append(HumanMessage(content=user_input))

    # --- Step 2: Invoke the Agent with the Full Context ---
    fallback_response = {
        "message_type": "text",
        "content": {"prompt": "I'm sorry, a critical error occurred while processing your request. Please try again or rephrase your input."}
    }
    processed_output = fallback_response

    try:
        response = await planning_agent_executor.ainvoke({
            "input": user_input,
            "session_state": json.dumps(session_state),
            "chat_history": lc_chat_history
        })

        raw_output = response.get('output')

        processed_output = _handle_agent_output(raw_output, session_state)
        
        if not isinstance(processed_output, dict) or "message_type" not in processed_output or "content" not in processed_output:
            raise ValueError("Processed output from agent is malformed.")
        
        agent_content = processed_output.get("content", {})
        message_type = processed_output.get("message_type")

        # Update session state based on the message type
        next_stage = session_state["current_stage"]
        if message_type == "summary_cards":
            planning_type = agent_content.get("planning_type")
            if planning_type == "medical_plans":
                # Assuming the medical planning tool returns a list of options
                session_state["plan_parameters"]["medical_plan_options"] = agent_content.get("payload", {}).get("output", [])
                next_stage = "medical_plan_selection"
            elif planning_type == "travel_arrangements":
                # The travel arrangement tool returns a single plan, not options
                session_state["plan_parameters"]["travel_arrangements_plan"] = agent_content.get("payload", {})
                next_stage = "travel_arrangement_selection"
            elif planning_type == "travel_logistics":
                # The local logistics tool returns a single plan, not options
                session_state["plan_parameters"]["local_logistics_plan"] = agent_content.get("payload", {})
                next_stage = "local_logistics_review"
        elif message_type == "final_plan":
            session_state["plan_parameters"]["finalized_plan"] = agent_content
            next_stage = "final_report_display"

        session_state["current_stage"] = next_stage
        
        # We should append the agent's full processed output object to the history,
        # not just a single string, so the frontend can correctly display it.
        # This is a critical change for displaying structured output like summary cards.
        lc_chat_history.append(AIMessage(content=json.dumps(processed_output)))

    except (CustomException, Exception) as e:
        logging.error(f"Unexpected error in next_step: {e}", exc_info=True)
        processed_output = fallback_response
        lc_chat_history.append(AIMessage(content=json.dumps(fallback_response)))
        
    # --- Step 3: Update and Save Session State ---
    sessions_db[session_id]["chat_history"] = lc_chat_history
    sessions_db[session_id]["session_state"] = session_state

    # Return a standardized JSON response to the frontend
    return JSONResponse(status_code=200, content={
        "agent_response": processed_output,
        "updated_session_state": session_state
    })

# --- New Endpoint for Loading Historical Sessions ---
@app.post("/api/v1/plan/load-session")
async def load_session(body: LoadSessionRequest):
    """
    Loads a complete session from the backend database for a historical plan.
    """
    session_id = body.session_id
    
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail=f"Session with ID '{session_id}' not found.")
        
    session_data = sessions_db[session_id]
    
    # return the raw chat history and session state
    return JSONResponse(status_code=200, content={
        "chat_history": [
            {"sender": "user", "content": msg.content} if isinstance(msg, HumanMessage) else {"sender": "agent", "content": msg.content}
            for msg in session_data["chat_history"]
        ],
        "session_state": session_data["session_state"]
    })

# Health check endpoint for verifying API service status
@app.get("/health")
async def health_check():
    """
    Provides a basic health check endpoint to confirm the API service is running.
    """
    return {"status": "ok", "message": "Medical Tourism AI Agent service is running and healthy."}