# ai_service/src/agentic/agents/knowledge_registrar_agent.py
import logging
import json
from pydantic import ValidationError
from langchain_core.prompts import ChatPromptTemplate
from ..utils.models_factory import get_gemini_planner
from ..models import KnowledgeEntity
from ..config import AppConfig

class KnowledgeRegistrarAgent:
    """
    [Entity-Centric RAG - Core]
    Reads new facts, compares with existing DB entity, resolves conflicts, and writes a golden JSON.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm = get_gemini_planner()
        self._load_prompt()

    def _load_prompt(self):
        path = self.config.prompts.get_prompt_path("knowledge_registrar")
        with open(path, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

    async def merge_knowledge(self, existing_data: dict, new_data: dict) -> KnowledgeEntity | None:
        prompt = ChatPromptTemplate.from_template(self.prompt_template)
        # Forced structured output completely eliminates formatting errors.
        structured_llm = self.llm.with_structured_output(KnowledgeEntity)
        chain = prompt | structured_llm

        try:
            result = await chain.ainvoke({
                "existing_data": json.dumps(existing_data, default=str),
                "new_data": json.dumps(new_data, default=str)
            })
            return result
        except ValidationError as e:
            logging.error(f"❌ [Registrar] Schema Validation Failed during merge: {e}")
            return None
        except Exception as e:
            logging.error(f"❌ [Registrar] Unexpected Error: {e}")
            return None