# ai_service/rag_setup.py
import sqlite3
import json
import logging
import asyncio
import os
import sys
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# --- Path and Environment Configuration ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from ai_service.src.agentic.config import AppConfig
from ai_service.src.agentic.agents.data_curator_agent import DataCuratorAgent
from ai_service.src.agentic.agents.knowledge_registrar_agent import KnowledgeRegistrarAgent
from ai_service.src.agentic.evaluators.knowledge_validator_agent import KnowledgeValidatorAgent

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Entity Table Structure ---
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_entities (
    entity_id TEXT PRIMARY KEY,
    category TEXT,
    name TEXT,
    full_json TEXT,
    last_updated TEXT
)
"""

def _calculate_source_confidence(url: str) -> float:
    """Helper to score provenance authority."""
    if not url or "Search" in url:
        return 0.70
    # Top-tier authority: Government agencies, educational institutions, WHO
    if ".gov" in url or ".edu" in url or "who.int" in url:
        return 0.98
    # Top-tier medical institutions: Mayo Clinic, Cleveland Clinic, etc.
    elif "mayoclinic.org" in url or "clevelandclinic.org" in url:
        return 0.95
    # Official organizations/non-profit institutions
    elif ".org" in url:
        return 0.85
    # Commercial news, general clinics
    elif ".com" in url or ".net" in url:
        return 0.75
        
    return 0.65
        
def _parse_curator_output(curator_output: Any, name: str) -> dict:
    """Helper: Parse the results of large models in various forms and extract clean JSON data."""
    if not curator_output:
        return {}
    try:
        if isinstance(curator_output, list):
            if len(curator_output) > 0 and isinstance(curator_output[0], dict) and "text" in curator_output[0]:
                raw_str = curator_output[0]["text"]
                clean_str = raw_str.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_str)
            else:
                return curator_output[0] if len(curator_output) > 0 else {}
        elif isinstance(curator_output, dict):
            return curator_output
        elif isinstance(curator_output, str):
            clean_str = curator_output.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_str)
    except Exception as e:
        logging.error(f"❌ Failed to parse Curator output for {name}. Error: {e}")
    return {}

def _get_existing_data(db_path: str, entity_id: str) -> dict:
    """Helper: Retrieve existing entity data from the SQLite database."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_json FROM knowledge_entities WHERE entity_id = ?", (entity_id,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else {}

async def ingest_document(config: AppConfig, db_path: str, entity_id: str, category: str, name: str, raw_text: str, source_url: str):
    """
    [Eager Write-Time Pipeline]
    Reads raw text -> Extracts JSON -> Merges -> Validates -> Saves Golden JSON
    """
    curator = DataCuratorAgent(config)
    registrar = KnowledgeRegistrarAgent(config)
    validator = KnowledgeValidatorAgent(config)

    # Extraction and parsing
    logging.info(f"📖 Curator is reading raw text for {name}...")
    curator_output = await curator.curate_data(category, raw_text)
    new_data = _parse_curator_output(curator_output, name)
    
    if not new_data:
        logging.warning(f"⚠️ Parsed new_data is empty for {name}, skipping merge.")
        return

    # Merging existing data with new data
    existing_data = _get_existing_data(db_path, entity_id)
    logging.info(f"🧠 Registrar is compiling and merging entity: {entity_id}...")
    merged_entity = await registrar.merge_knowledge(existing_data, new_data)

    if not merged_entity:
        return
    
    # Validation
    logging.info(f"🕵️ Validator is inspecting entity: {entity_id} for data corruption...")
    verdict = await validator.validate(existing_data, merged_entity.model_dump())

    if not verdict.is_valid:
        logging.error(f"🚫 [BLOCKED] Entity '{name}' rejected by Validator!")
        for err in verdict.error_log:
            logging.error(f"   👉 Reason: {err}")
        logging.error("Requires Human Review. Skipping database insertion.")
        return

    logging.info("✅ Validator Passed! No anomalies detected.")

    # Saving to database
    merged_entity.entity_id = entity_id
    merged_entity.category = category
    merged_entity.name = name
    merged_entity.provenance.source = "System Seed Data"
    merged_entity.provenance.source_url = source_url
    merged_entity.provenance.confidence_score = _calculate_source_confidence(source_url)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO knowledge_entities (entity_id, category, name, full_json, last_updated) VALUES (?, ?, ?, ?, ?)",
            (merged_entity.entity_id, merged_entity.category, merged_entity.name, merged_entity.model_dump_json(), merged_entity.last_updated)
        )
        conn.commit()
        logging.info(f"✅ Entity '{name}' successfully compiled and saved to SQLite DB.")

def _read_json_sync(file_path: Path) -> Any:
    """Helper: Read JSON file synchronously"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

async def _process_parsed_data(config: AppConfig, db_path: str, category: str, id_field: str, raw_data: Any) -> None:
    """Helper: Parse and process JSON data"""
    if isinstance(raw_data, list):
        for item in raw_data:
            if category == "accommodation" and "accommodations" in item:
                for acc in item["accommodations"]:
                    await process_item(config, db_path, category, acc, "id")
            else:
                await process_item(config, db_path, category, item, id_field)
                
    elif isinstance(raw_data, dict):
        for key, value in raw_data.items():
            await process_item(config, db_path, category, value, entity_id=key)

async def seed_all_data(config: AppConfig, db_path: str) -> None:
    """
    [The Master Seeder] Automatically seeds all JSON files.
    Processes each file, extracts JSON data, and seeds it into the database.
    Handles special cases like nested accommodations.
    """
    data_dir = config.storage.data_dir
    
    # Define task configurations: (Filename, Category, ID field name)
    tasks = [
        ("hospitals.json", "hospital", "id"),
        ("doctors.json", "doctor", "id"),
        ("treatments.json", "treatment", "id"),
        ("accommodations.json", "accommodation", "id"),
        ("visa_rules.json", "visa", None),
        ("country_metadata.json", "metadata", None),
        ("airports_offline_cache.json", "airport", "iata"),
    ]

    for file_name, category, id_field in tasks:
        file_path = data_dir / file_name
        if not file_path.exists():
            logging.warning(f"⏩ Skipping {file_name}: File not found.")
            continue

        logging.info(f"🚀 Seeding category '{category}' from {file_name}...")
        
        raw_data = await asyncio.to_thread(_read_json_sync, file_path)
        
        await _process_parsed_data(config, db_path, category, id_field, raw_data)

async def process_item(config: AppConfig, db_path: str, category: str, item_dict: dict, id_field: str=None, entity_id: str=None):
    """Helper function: Processes a single JSON object and automatically selects the fast and slow lanes."""
    eid = entity_id or item_dict.get(id_field)
    if not eid:
        return
        
    name = item_dict.get("name") or eid
    
    # Fast Track
    if category in ["airport", "metadata"]:
        fast_entity_json = {
            "entity_id": eid,
            "category": category,
            "name": name,
            "data": item_dict,
            "last_updated": datetime.now().isoformat(),
            "provenance": {
                "source": "Local Static Cache",
                "source_url": "internal://seed_file",
                "timestamp": datetime.now().isoformat(),
                "confidence_score": 1.0,
                "is_mock_data": False
            }
        }
        
        with sqlite3.connect(db_path, timeout=15.0, isolation_level="EXCLUSIVE") as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("BEGIN EXCLUSIVE")
                cursor.execute(
                    "INSERT OR REPLACE INTO knowledge_entities (entity_id, category, name, full_json, last_updated) VALUES (?, ?, ?, ?, ?)",
                    (eid, category, name, json.dumps(fast_entity_json, ensure_ascii=False), fast_entity_json["last_updated"])
                )
                conn.commit()
            except sqlite3.OperationalError as e:
                logging.error(f"Database locked, write failed for {eid}: {e}")
                conn.rollback()
            
        return

    # Slow Track
    logging.info(f"🧠 [LLM Compiling] Entity: {name}")
    text = json.dumps(item_dict, ensure_ascii=False)
    await ingest_document(config, db_path, eid, category, name, text, "internal://seed_file")

if __name__ == "__main__":
    app_config = AppConfig.from_env()
    app_config.storage.db_dir.mkdir(parents=True, exist_ok=True)
    target_db = str(app_config.storage.db_dir / "medical_knowledge.db")
    
    with sqlite3.connect(target_db) as conn:
        conn.execute(CREATE_TABLE_SQL)
    
    logging.info(f"✅ Database initialized at {target_db}")
    asyncio.run(seed_all_data(app_config, target_db))
    logging.info("✨ ALL SEED DATA COMPILED SUCCESSFULLY!")

# python -m ai_service.rag_setup