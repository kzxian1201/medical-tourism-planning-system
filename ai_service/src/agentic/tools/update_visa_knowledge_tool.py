# ai_service/src/agentic/tools/update_visa_knowledge_tool.py
import logging
import contextvars
from langchain_core.tools import tool
from ..config import AppConfig

visa_queue_ctx = contextvars.ContextVar("visa_queue", default=None)

def create_update_visa_knowledge_tool(config: AppConfig):
    """
    [Factory] Creates the tool to push outdated visa rules into the update queue.
    """
    @tool("update_visa_knowledge_tool")
    async def update_visa_knowledge(nationality: str, destination: str, latest_rules: str) -> dict:
        """Use this tool when the RAG visa information is missing, returns 'Check Embassy', or is older than 30 days.
        It pushes the freshly researched visa rules into the system's data curation queue for future offline updates.
        """
        logging.info(f"📥 Queuing new visa rules for offline review at: {config.storage.pending_review_file}")
        
        update_item = {
            "category": "visa",
            "id": f"{nationality.lower()}_{destination.lower()}_medical",
            "new_content": latest_rules,
            "status": "pending_review"
        }

        # Safely insert data into the ContextVar of the current concurrent request
        queue = visa_queue_ctx.get()
        if queue is not None:
            queue.append(update_item)

        return {
            "status": "update_queued",
            "message": "Latest visa rules successfully queued for database update."
        }
    
    return update_visa_knowledge