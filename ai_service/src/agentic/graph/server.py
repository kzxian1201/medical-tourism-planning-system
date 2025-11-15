# ai_service/src/agentic/graph/server.py
from .graph import create_graph
from langgraph.checkpoint.memory import InMemorySaver
# from langgraph.checkpoint.redis import RedisSaver

# 1. initialize checkpointer
checkpointer = InMemorySaver() 
# checkpointer = RedisSaver.from_url("redis://localhost:6379")

# 2. expose the graph app
app = create_graph(checkpointer=checkpointer)

# run this: langgraph dev --module ai_service.src.agentic.graph.server:app