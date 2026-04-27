# ai_service/src/agentic/tools/medical_knowledge_base_tool.py
import aiosqlite
import json
import os
from langchain_core.tools import tool
from ..logger import logging
from ..models import KnowledgeBaseInput, KnowledgeBaseOutput
from ..config import AppConfig

def _get_db_path() -> str:
    config = AppConfig.from_env()
    return str(config.storage.db_dir / "medical_knowledge.db")

@tool("medical_knowledge_base", args_schema=KnowledgeBaseInput)
async def medical_knowledge_base(category: str, query: str) -> KnowledgeBaseOutput:
    """
    Primary source for pre-compiled knowledge.
    Retrieves COMPLETE entity profiles (Hospitals, Visas, etc.) instead of text chunks.
    """
    db_file = _get_db_path()
    results = []

    logging.info(f"🔍 [Retrieval Trace] Category: '{category}' | Agent Query: '{query}'")
    
    if not os.path.exists(db_file):
        logging.error(f"❌ Entity DB not found at {db_file}")
        return KnowledgeBaseOutput(results=[], message="Database missing.")

    try:
        async with aiosqlite.connect(db_file) as db:
            sql = "SELECT full_json FROM knowledge_entities WHERE category = ?"
            params = [category]
            
            keywords = query.split()
            conditions = []
            for kw in keywords:
                conditions.append("(full_json LIKE ? OR name LIKE ?)")
                params.extend([f"%{kw}%", f"%{kw}%"])
            
            if conditions:
                sql += " AND (" + " AND ".join(conditions) + ")"
            
            sql += " LIMIT 3"

            logging.info(f"⚙️ [Retrieval Trace] Executing Strict SQL: {sql}")
            
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
            
            fallback_triggered = False

            # Search downgrade fallback
            if not rows:
                fallback_triggered = True
                logging.warning(f"⚠️ [Retrieval Trace] Strict match failed for '{query}'. Triggering Fallback!")
                
                # Disregard keywords and directly return any 3 authoritative entities under this category
                fallback_sql = "SELECT full_json FROM knowledge_entities WHERE category = ? LIMIT 3"
                fallback_params = [category]
                
                async with db.execute(fallback_sql, fallback_params) as cursor:
                    rows = await cursor.fetchall()

            # Process results and inject risk controls
            for row in rows:
                full_entity = json.loads(row[0])
                core_data = full_entity.get("data", {})
                
                core_data["_entity_id"] = full_entity.get("entity_id")
                core_data["_last_updated"] = full_entity.get("last_updated")
                if full_entity.get("conflict_warning"):
                    core_data["_ATTENTION_CONFLICT"] = full_entity.get("conflict_warning")
                
                # Inject risk controls
                if fallback_triggered:
                    core_data["_SYSTEM_WARNING"] = (
                        f"CRITICAL: Exact match for '{query}' failed. "
                        "This is a generic fallback recommendation. You MUST inform the user "
                        "that exact matches were not found."
                    )
                    
                core_data["provenance"] = full_entity.get("provenance", {})
                results.append(core_data)

            # Log final recall statistics
            hit_count = len(results)
            logging.info(f"🎯 [Retrieval Trace] Returned {hit_count} entities. (Fallback Used: {fallback_triggered})")

            # Build system message to return to LLM
            msg = f"Retrieved {hit_count} complete pre-compiled entities."
            if fallback_triggered:
                msg += f" WARNING: Strict match failed. Provided generic {category} fallbacks instead."

            return KnowledgeBaseOutput(
                results=results,
                message=msg
            )
    except Exception as e:
        logging.error(f"KB Retrieval Error: {e}", exc_info=True)
        return KnowledgeBaseOutput(results=[], message="Error reading entities.", error=str(e))