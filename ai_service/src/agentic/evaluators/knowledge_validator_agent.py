# ai_service/src/agentic/evaluators/knowledge_validator_agent.py
import logging
import json
from langchain_core.prompts import ChatPromptTemplate
from ..utils.models_factory import get_auditor_model
from ..models import ValidationVerdict
from ..config import AppConfig

class KnowledgeValidatorAgent:
    """
    [Ingestion QA Layer]
    Acts as a Red Team interceptor before compiled data is committed to the database.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm = get_auditor_model()
        self._load_prompt()

    def _load_prompt(self):
        try:
            path = self.config.prompts.get_prompt_path("knowledge_validator")
        except Exception:
            path = self.config.prompts.prompt_dir / "knowledge_validator_prompt.txt"
            
        with open(path, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

    async def validate(self, old_data: dict, new_data: dict) -> ValidationVerdict:
        if not old_data:
            return ValidationVerdict(is_valid=True, requires_human_review=False, error_log=[])

        prompt = ChatPromptTemplate.from_template(self.prompt_template)
        chain = prompt | self.llm.with_structured_output(ValidationVerdict)

        try:
            result = await chain.ainvoke({
                "old_data": json.dumps(old_data, default=str),
                "new_data": json.dumps(new_data, default=str)
            })
            return result
        except Exception as e:
            logging.error(f"❌ [Validator] Evaluation failed: {e}")
            return ValidationVerdict(is_valid=False, requires_human_review=True, error_log=[f"Validator Crash: {e}"])