# ai_service/main.py
import os
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.graph.server import GraphServer
from ai_service.src.agentic.models import NextStepRequest, UserProfile

# Load .env
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

TARGET_STATUS_NODES = {"medical_dept", "travel_dept", "logistics_dept", "finalize", "verifier"}

# LIFESPAN MANAGER
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle of the application: Startup -> Run -> Shutdown.
    """
    logger.info("🚀 Starting MediJourney AI Service...")
    
    try:
        # 1. Load Config
        config = AppConfig.from_env()
        config.validate()
        
        # 2. Initialize Graph Server
        # Store in app.state to avoid global variables
        server = GraphServer(config)
        await server.initialize()
        
        app.state.graph_server = server
        app.state.config = config
        
        logger.info("✅ Service is Ready.")
        yield # Application runs here
        
    except Exception as e:
        logger.critical(f"❌ Critical Startup Error: {e}", exc_info=True)
        raise e
    finally:
        # 3. Shutdown Logic
        logger.info("🛑 Shutting down...")
        if hasattr(app.state, "graph_server") and app.state.graph_server:
            await app.state.graph_server.shutdown()
        logger.info("👋 Goodbye.")

# Initialize App with Lifespan
app = FastAPI(
    title="MediJourney Architect API",
    version="3.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _check_data_gaps(output: Dict[str, Any], event_name: str):
    """Check RAG data gaps"""
    def find_nulls(obj, prefix=""):
        nulls = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if v is None:
                    nulls.append(f"{prefix}{k}")
                else:
                    nulls.extend(find_nulls(v, f"{prefix}{k}."))
        return nulls
    
    null_fields = find_nulls(output)
    if null_fields:
        print(f"\n📡 [NODE MONITOR] Finished: {event_name}")
        print(f"⚠️  DATA GAP DETECTED: {null_fields}")
        print("💡 Action: Update your JSON files in ai_service/src/data/.")

def _print_usage_metadata(metadata: Dict[str, Any], event_name: str):
    """Print Token usage metadata"""
    usage = metadata.get("usage_metadata")
    if usage:
        print(f"\n📊 [USAGE REPORT] Node: {event_name}")
        print(f"🪙  Tokens: Total={usage.get('total_tokens')} "
            f"(P={usage.get('prompt_tokens')}, C={usage.get('completion_tokens')})")
        print("-" * 30)

def _process_graph_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Helper: Transforms a raw LangGraph event into a frontend SSE data string.
    Complexity reduced from 31 to < 10.
    """
    event_type = event.get("event")
    event_name = event.get("name")
    data = event.get("data", {})
    metadata = event.get("metadata", {})

    # 1. Process start status
    if event_type == "on_chain_start" and event_name in TARGET_STATUS_NODES:
        display_name = event_name.replace("_dept", "").capitalize() + " Agent"
        return json.dumps({'type': 'status', 'content': f"Activate {display_name}..."})

    # 2. Process end status (monitor logs)
    if event_type == "on_chain_end" and event_name in TARGET_STATUS_NODES:
        output = data.get("output", {})
        _check_data_gaps(output, event_name)
        _print_usage_metadata(metadata, event_name)

    # 3. Process final result
    if event_type == "on_chain_end" and event_name == "finalize":
        proposal = data.get("output", {}).get("final_proposal")
        if proposal:
            proposal_dict = proposal.model_dump() if hasattr(proposal, "model_dump") else proposal
            return json.dumps({'type': 'result', 'data': proposal_dict})

    # 4. Process streaming Token
    if event_type == "on_chat_model_stream":
        content = getattr(data.get("chunk"), "content", "")
        if content:
            return json.dumps({'type': 'token', 'content': content})

    return None

# 📡 ENDPOINTS
@app.get("/health")
async def health_check():
    server_ready = hasattr(app.state, "graph_server") and app.state.graph_server.graph is not None
    return {
        "status": "ok" if server_ready else "initializing",
        "environment": os.getenv("ENV", "development"),
        "components": {
            "graph_engine": "ready" if server_ready else "not_ready"
        }
    }

@app.post(
    "/chat",
    responses={
        500: {"description": "Internal Server Error"},
        503: {"description": "Service not ready"}
    }
)
async def chat_endpoint(request: NextStepRequest):
    """
    Standard Request-Response Chat Endpoint.
    """
    server: GraphServer = getattr(app.state, "graph_server", None)
    if not server or not server.graph:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        # 1. Construct State Delta
        initial_state = {
            "messages": [("user", request.user_input)], # LangGraph accepts tuples for messages
            "user_input": request.user_input, # Legacy field support
            "user_profile": UserProfile(
                user_id=request.session_id,
                session_id=request.session_id,
                name="Guest",
                nationality="Unknown"
            )
        }

        # 2. Runtime Config
        config = {"configurable": {"thread_id": request.session_id}}

        # 3. Execute Graph
        final_state = await server.graph.ainvoke(initial_state, config=config)
        
        # 4. Extract Result
        final_proposal = final_state.get("final_proposal")
        
        if not final_proposal:
            # Check if we have a blocking error or just processing
            error = final_state.get("error_message")
            return {
                "status": "error" if error else "processing", 
                "message": error or "Workflow processed but no final proposal generated."
            }

        return final_proposal.model_dump()

    except Exception as e:
        logger.error(f"Chat Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/chat/stream",
    responses={503: {"description": "Service not ready"}}
)
async def chat_stream_endpoint(request: NextStepRequest):
    """🌊 Streaming Endpoint for Real-time Feedback."""
    server: GraphServer = getattr(app.state, "graph_server", None)
    if not server or not server.graph:
        raise HTTPException(status_code=503, detail="Service not ready")

    async def event_generator():
        initial_state = {
            "messages": [("user", request.user_input)],
            "user_profile": UserProfile(
                user_id=request.session_id,
                session_id=request.session_id
            )
        }
        config = {"configurable": {"thread_id": request.session_id}}

        try:
            async for event in server.graph.astream_events(initial_state, config=config, version="v2"):
                sse_data = _process_graph_event(event)
                if sse_data:
                    yield f"data: {sse_data}\n\n"

        except Exception as e:
            logger.error("Stream Error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Workflow failed'})}\n\n"
        
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")