# ai_service/src/agentic/graph/server.py
import sys
import os
import asyncio
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))

if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"🔧 [System] Added project root to sys.path: {project_root}")

env_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path=env_path)

from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.graph.graph import create_main_graph
from ai_service.src.agentic.logger import logging
from ai_service.src.agentic.models import UserProfile
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

# Optional imports for Production
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

class GraphServer:
    """
    [Lifecycle Manager]
    Manages the lifecycle of the Graph Engine and its Persistence Layer.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.graph = None
        self._pool = None
        self._checkpointer = None

    async def initialize(self):
        """
        Initialization: Setup DB Pool and Checkpointer.
        """
        if HAS_POSTGRES:
            try:
                DB_URI = self.config.storage.postgres_uri
                
                if not DB_URI:
                    raise ValueError("POSTGRES_URI is not set in environment variables.")

                logging.info("🐘 Connecting to PostgreSQL for State Management...")
                self._pool = AsyncConnectionPool(
                    conninfo=DB_URI,
                    min_size=1,
                    max_size=5,
                    kwargs={"autocommit": True, "prepare_threshold": 0},
                )

                await self._pool.open()

                self._checkpointer = AsyncPostgresSaver(self._pool)
                await self._checkpointer.setup()
                logging.info("✅ PostgreSQL Checkpointer Ready & Tables Setup.")
            except Exception as e:
                logging.error(f"❌ Failed to init Postgres: {e}. Falling back to MemorySaver.")
                self._checkpointer = MemorySaver()
        else:
            self._checkpointer = MemorySaver()
            logging.info("🧠 Using in-memory checkpointer (Postgres missing).")

        # Compile Graph with the selected checkpointer AND Enable Interrupts for UI
        self.graph = create_main_graph(
            self.config,
            checkpointer=self._checkpointer,
            enable_interrupts=True
        )
        logging.info("✅ Graph Compiled Successfully with HITL enabled.")

    async def shutdown(self):
        """Cleanup logic."""
        if self._pool:
            await self._pool.close()
            logging.info("🛑 Database connection closed.")

async def run_demo():
    """
    Local testing function to verify graph execution.
    """
    config = AppConfig.from_env()
    
    server = GraphServer(config)
    await server.initialize()
    
    app = server.graph
    
    my_user_profile_object = UserProfile(
        user_id="test_user_01",
        session_id="test_session_01",
        name="Demo User",
        nationality="Australian",
        preferences={
            "dietary_needs": ["Vegetarian"],
            "preferred_language": "English"
        }
    )
    
    runtime_config = {
        "configurable": {"thread_id": "test_thread_01", "max_retries": 5},
        "recursion_limit": 50
    }
    
    inputs = {
        "messages": [HumanMessage(content="I need a general medical checkup in a good hospital in Malaysia.")],
        "user_profile": my_user_profile_object,
        "data_update_queue": [],
        "status": "active"
    }
    
    print("\n🚀 Starting Demo Run...\n")
    
    try:
        async for event in app.astream_events(inputs, config=runtime_config, version="v2"):
            kind = event["event"]
            if kind == "on_chain_end":
                print(f"📍 Finished: {event['name']}")
    finally:
        await server.shutdown()

def get_studio_graph():
    """
    A lazy-initialized graph instance, specifically designed for use with LangGraph Studio.
    """
    _config = AppConfig.from_env()
    memory = MemorySaver()
    return create_main_graph(_config, checkpointer=memory, enable_interrupts=True)

studio_graph = get_studio_graph()

if __name__ == "__main__":
    asyncio.run(run_demo())

# run this: langgraph dev --host localhost