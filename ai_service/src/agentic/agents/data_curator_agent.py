# ai_service/src/agentic/agents/data_curator_agent.py
import logging
from langchain_core.prompts import ChatPromptTemplate
from ..utils.models_factory import get_gemini_planner
from ..config import AppConfig

class DataCuratorAgent:
    """
    [Data Engineering Layer - Agentic RAG]
    Task: Read FULL unstructured text using Gemini's massive context window.
    No chunking needed. Extracts pure facts into highly structured JSON strings.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm = get_gemini_planner()
        self._load_prompt()

    def _load_prompt(self):
        """Load the extraction instruction prompt."""
        path = self.config.prompts.get_prompt_path("data_curator")
        if not path.exists():
            raise FileNotFoundError(f"CRITICAL: Required prompt file missing at {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

    async def curate_data(self, category: str, raw_text: str) -> str:
        """
        Extracts factual entities from raw text based on the target category.
        Returns a raw JSON string.
        """
        prompt = ChatPromptTemplate.from_template(self.prompt_template)
        chain = prompt | self.llm
        
        try:
            # The entire large model is read through, and the extracted JSON string is directly outputted
            result = await chain.ainvoke({
                "category": category,
                "web_text": raw_text
            })
            return result.content
        except Exception as e:
            logging.error(f"❌ [Curator] Fact extraction failed: {e}")
            return ""