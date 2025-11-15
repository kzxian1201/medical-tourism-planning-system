# ai_service/main.py
import sys
import os
import json
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# --- Custom Imports from local modules ---
from ai_service.src.agentic.logger import logging
from ai_service.src.agentic.exception import CustomException
from ai_service.src.agentic.graph.graph import create_graph 
from langgraph.checkpoint.redis import RedisSaver
from langgraph.checkpoint.memory import MemorySaver
from ai_service.src.agentic.models import NextStepRequest, AgentResponse, LoadSessionRequest
from ai_service.src.agentic.graph.state import AgentState

# Initialize FastAPI app
app = FastAPI(
    title="Medical Tourism AI Agent Service",
    description="API for a unified AI agent, now powered by LangGraph.",
    version="1.1.0",
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
redis_checkpointer = None

@app.on_event("startup")
async def startup_event():
    """
    Event hook that runs once when the application starts.
    We use this to initialize the agent asynchronously.
    """
    global planning_agent_executor, redis_checkpointer
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
    redis_checkpointer = MemorySaver()
    logging.info("Using InMemorySaver checkpointer for stability.")

    planning_agent_executor = create_graph(redis_checkpointer)
    logging.info("LangGraph Supervisor loaded successfully.")

@app.post("/api/v1/plan/next-step", response_model=AgentResponse)
async def next_step(body: NextStepRequest):
    """
    Main endpoint for driving the AI planning conversation.
    Processes user input and current session state to generate the next response.
    """
    global planning_agent_executor
    if planning_agent_executor is None:
        raise HTTPException(status_code=503, detail="Agent Graph has not been initialized.")

    session_id = body.session_id
    logging.info(f"Processing the next step for session {session_id}")

    # --- 1. Define LangGraph configuration ---
    config = {
        "configurable": {
            "thread_id": f"session-{session_id}",   
            "session_id": session_id           
        }
    }
    
    # --- 2. Prepare inputs and invoke the agent ---
    inputs = {
        "user_input": body.user_input,
        "current_stage": body.current_stage
    }
    
    is_start_of_conversation = body.current_stage == "start"

    try:
        if is_start_of_conversation:
            logging.info(f"[{session_id}] STARTING conversation.")
            inputs["user_profile"] = body.session_state.get("profileData", {})
            inputs["chat_history"] = [] 
            
            final_state = await planning_agent_executor.ainvoke(inputs, config)
            
        else:
            logging.info(f"[{session_id}] UPDATING conversation state.")
            
            if body.session_state.get("selected_medical_plan_id"):
                inputs["selected_medical_plan_id"] = body.session_state.get("selected_medical_plan_id")
            if body.session_state.get("selected_flight_id"):
                inputs["selected_flight_id"] = body.session_state.get("selected_flight_id")
            if body.session_state.get("selected_accommodation_id"):
                inputs["selected_accommodation_id"] = body.session_state.get("selected_accommodation_id")

            planning_agent_executor.update_state(config, inputs)
            
            final_state = await planning_agent_executor.ainvoke(None, config)

        # --- 3. Extract response ---
        agent_response = final_state.get("last_agent_message")
        
        if not agent_response:
             raise ValueError("The graph execution is complete, but 'last_agent_message' is empty.")

        updated_session_state = {
            "current_stage": final_state.get("current_stage")
        }
    except (CustomException, Exception) as e:
        logging.error(f"An unexpected error occurred in the next step.: {e}", exc_info=True)
        agent_response = AgentResponse(
            message_type="text",
            content={"prompt": "I'm sorry, a serious error occurred. Please try again."}
        )
        updated_session_state = {"current_stage": "error"}
        
    # --- 4. Return response ---
    return JSONResponse(status_code=200, content={
        "agent_response": agent_response.model_dump() if isinstance(agent_response, AgentResponse) else agent_response,
        "updated_session_state": updated_session_state
    })

# --- New Endpoint for Loading Historical Sessions ---
@app.post("/api/v1/plan/load-session")
async def load_session(body: LoadSessionRequest):
    """
    Load a complete historical session from the Redis persistence layer.
    """
    global redis_checkpointer
    if redis_checkpointer is None:
         raise HTTPException(status_code=503, detail="The persistence layer (Redis Checkpointer) has not yet been initialized.")

    session_id = body.session_id
    config = {"config": {"thread_id": f"session-{session_id}"}}

    try:
        # .get() retrieves the saved state directly from Redis.
        session_data: Optional[AgentState] = redis_checkpointer.get(config)
        
        if session_data is None:
            raise HTTPException(status_code=404, detail=f"Session ID '{session_id}' not found.")

        # Format the chat_history to match the old API response.
        formatted_history = []
        for msg in session_data.get("chat_history", []):
            if isinstance(msg, HumanMessage):
                formatted_history.append({"sender": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                try:
                    parsed_content = json.loads(msg.content)
                    formatted_history.append({"sender": "agent", "content": parsed_content})
                except json.JSONDecodeError:
                     formatted_history.append({"sender": "agent", "content": msg.content})
            
        # Prepare session_state
        session_state_snapshot = {
            "current_stage": session_data.get("current_stage"),
            "plan_parameters": {
                "medical_plan": session_data.get("final_selected_medical_plan"),
                "flight": session_data.get("final_selected_flight"),
                "accommodation": session_data.get("final_selected_accommodation"),
                "local_logistics": session_data.get("final_selected_logistics"),
                "finalized_plan": session_data.get("final_budget"), 
            }
        }
        
        return JSONResponse(status_code=200, content={
            "chat_history": formatted_history,
            "session_state": session_state_snapshot
        })
        
    except Exception as e:
        logging.error(f"Error loading session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred while loading the session: {e}")

# Health check endpoint for verifying API service status
@app.get("/health")
async def health_check():
    """
    Provides a basic health check endpoint to confirm the API service is running.
    """
    return {"status": "ok", "message": "Medical Tourism AI Agent service is running and healthy."}