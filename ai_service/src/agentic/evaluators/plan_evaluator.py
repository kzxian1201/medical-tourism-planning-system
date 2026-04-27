# ai_service/src/agentic/evaluators/plan_evaluator.py
import json
import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from ..logger import logging
from ..utils.models_factory import get_auditor_model
from ..models import AuditorVerdict
from ..config import AppConfig

def load_prompt_content(config: AppConfig, agent_name: str) -> str:
    """Helper: Load raw prompt text from file based on experiment config."""
    path = config.prompts.get_prompt_path(agent_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Audit this plan: {plan}"

class PlanEvaluator:
    """
    [Offline Evaluation Layer]
    Independent Auditor using Meta's Llama 3.3 (70B) via Groq.
    Refactored for Config Injection.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = Client()
        self.auditor = None
        
        # Load Prompt via Config
        self.template = load_prompt_content(config, "evaluator")

        # Check API Key via Config
        if not self.config.api.groq_api_key:
            logging.warning("⚠️ GROQ_API_KEY missing in Config. Auditor disabled.")
        else:
            # We assume get_auditor_model handles the key injection or env var
            # Better practice: pass key to factory if supported, or set env var temporarily
            # For now, assuming factory reads env var or we can patch it here if needed.
            self.auditor = get_auditor_model()

    async def evaluate_run(self, run_id: str, plan_data: dict):
        """
        Executes the audit asynchronously.
        """
        if not self.auditor or not run_id:
            return

        logging.info(f"🦁 [Auditor] Llama-3.3 (Meta) is auditing Run ID: {run_id}...")
        
        try:
            plan_str = json.dumps(plan_data, indent=2, ensure_ascii=False)
            
            chain = (
                ChatPromptTemplate.from_template(self.template)
                | self.auditor.with_structured_output(AuditorVerdict)
            )
            
            result = await chain.ainvoke({"plan": plan_str})
            
            # Wrap the synchronous LangSmith call in a thread
            await asyncio.to_thread(
                self.client.create_feedback,
                run_id=run_id,
                key="audit_llama_3_3",
                score=result.score,
                comment=result.reason,
                value=str(result.is_pass)
            )
            
            status_icon = "✅" if result.is_pass else "❌"
            logging.info(f"{status_icon} [Auditor Verdict] Score: {result.score}/5. Reason: {result.reason}")
            
            return result

        except Exception as e:
            logging.error(f"Auditor Error: {e}", exc_info=True)