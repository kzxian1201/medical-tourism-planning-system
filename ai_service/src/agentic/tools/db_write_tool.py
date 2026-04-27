# ai_service/src/agentic/tools/db_write_tool.py
import json
import shutil
import uuid
import hashlib
import asyncio
from datetime import datetime
from langchain_core.tools import tool
from ..logger import logging
from ..config import AppConfig

def create_db_write_tool(config: AppConfig):
    """
    [Factory] Creates the DB Write Tool.
    Writes verified data into a persistent storage (JSON File simulation).
    Features Atomic Writes (ACID-like) and Checksums for Data Integrity.
    """

    def _calculate_checksum(data: dict) -> str:
        """Generates a SHA256 checksum for the given data dictionary."""
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _write_sync(category: str, data: dict) -> str:
        """Blocking write logic."""
        file_path = config.storage.pending_review_file
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing
        current_data = {}
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_data = json.load(f)
            except json.JSONDecodeError:
                current_data = {}

        if category not in current_data:
            current_data[category] = []

        # Metadata Injection
        enriched_data = data.copy()
        enriched_data['meta_id'] = f"pending_{uuid.uuid4().hex[:8]}"
        enriched_data['meta_status'] = "PENDING_HUMAN_REVIEW"
        enriched_data['meta_created_at'] = datetime.now().isoformat()
        enriched_data['meta_source_agent'] = "MediJourney_Agent_v1"
        enriched_data['meta_checksum'] = _calculate_checksum(data)

        # Append
        current_data[category].append(enriched_data)

        # Atomic Write
        temp_file = str(file_path) + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, indent=2, ensure_ascii=False)
        
        shutil.move(temp_file, file_path)
        return f"✅ [Safe Write] Queued new {category} data with Checksum: {enriched_data['meta_checksum'][:8]}..."

    @tool("db_write_tool")
    async def db_write(category: str, data: dict) -> str:
        """Writes verified new data into the 'pending_review' database for human audit."""
        try:
            return await asyncio.to_thread(_write_sync, category, data)
        except Exception as e:
            logging.error(f"DB Write Failed: {e}", exc_info=True)
            return f"Failed to write data: {e}"

    return db_write