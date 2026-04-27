# ai_service/src/agentic/config.py
import os
import logging
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent

REQUIRED_MSG = "Must be provided"

@dataclass
class PromptConfig:
    """
    [Experiment Layer] Prompt Config with Caching and Validation.
    """
    base_dir: Path = CURRENT_DIR / "prompt"
    version: str = "default"

    # ✅ Cache for prompt contents
    _cache: Dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def get_prompt_path(self, agent_name: str) -> Path:
        """Dynamically obtain the Prompt file path."""
        suffix = "" if self.version == "default" else f"_{self.version}"
        filename = f"{agent_name}_prompt{suffix}.txt"
        return self.base_dir / filename
    
    def list_versions(self, agent_name: str) -> List[str]:
        """List available prompt versions for an agent."""
        return [
            f.stem.replace(f"{agent_name}_prompt", "").strip("_") or "default"
            for f in self.base_dir.glob(f"{agent_name}_prompt*.txt")
        ]
    
    def load_prompt(self, agent_name: str) -> str:
        """Load prompt with caching."""
        cache_key = f"{agent_name}_{self.version}"
        
        if cache_key not in self._cache:
            path = self.get_prompt_path(agent_name)

            if not path.exists():
                available = self.list_versions(agent_name)
                raise FileNotFoundError(
                    f"Prompt not found: {path}\n"
                    f"Available versions: {available}"
                )
            
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if not content.strip():
                raise ValueError(f"Empty prompt file: {path}")
            
            self._cache[cache_key] = content
            logging.info(f"📝 Loaded prompt: {agent_name} (version={self.version})")
            
        return self._cache[cache_key]

    def get_prompt_hash(self, agent_name: str) -> str:
        """Get hash for LangSmith tagging."""
        content = self.load_prompt(agent_name)
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
@dataclass
class StorageConfig:
    """Storage and database paths configuration."""
    data_dir: Path = PROJECT_ROOT / "ai_service" / "src" / "data"
    db_dir: Path = PROJECT_ROOT / "ai_service" / "src" / "db"
    
    postgres_uri: str = ""
    medical_rag_db: Path = field(init=False)
    chroma_vector_store: Path = field(init=False)
    pending_review_file: Path = field(init=False)
    users_db_file: Path = field(init=False)
    
    def __post_init__(self):
        self.medical_rag_db = self.db_dir / "medical_rag.db"
        self.chroma_vector_store = self.db_dir / "chroma_vector_store"
        self.pending_review_file = self.data_dir / "pending_review.json"
        self.users_db_file = self.db_dir / "users.json"

class APIKeysConfig(BaseSettings):
    serper_api_key: str = Field(..., alias="SERPER_API_KEY", description=REQUIRED_MSG)
    groq_api_key: str = Field(..., alias="GROQ_API_KEY", description=REQUIRED_MSG)
    rapid_api_key: str = Field(..., alias="RAPID_API_KEY", description=REQUIRED_MSG)
    skyscanner_cookie: str = Field(default="", alias="SKYSCANNER_COOKIE")
    
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

@dataclass
class DomainConfig:
    """Domain-specific business logic constants."""
    default_destination_city: str = "Kuala Lumpur"
    default_destination_country: str = "Malaysia"
    default_origin_city: str = "Beijing"
    
    # Budget calculation constants
    default_recovery_days: int = 21
    local_transport_daily_cost_usd: float = 20.0
    
    # Compliance guardrail blacklist
    banned_keywords: List[str] = field(default_factory=lambda: [
        "organ trade", "buy kidney", "sell kidney", "illegal drug", "suicide", "euthanasia"
    ])

    @property
    def dynamic_default_date(self):
        from datetime import datetime, timedelta
        return (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

@dataclass
class AppConfig:
    """Application global configuration."""
    environment: str = "development"
    storage: StorageConfig = field(default_factory=StorageConfig)
    api: Optional[APIKeysConfig] = None
    domain: DomainConfig = field(default_factory=DomainConfig)
    prompts: PromptConfig = field(default_factory=PromptConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from system environment variables."""
        config = cls()
        config.environment = os.getenv("ENV", "development")
        
        config.api = APIKeysConfig()

        # load API Keys
        config.api.serper_api_key = os.getenv("SERPER_API_KEY", "")
        config.api.groq_api_key = os.getenv("GROQ_API_KEY", "")
        config.api.rapid_api_key = os.getenv("RAPID_API_KEY", "")
        config.api.skyscanner_cookie = os.getenv("SKYSCANNER_COOKIE", "")

        # load Postgres URI
        config.storage.postgres_uri = os.getenv("POSTGRES_URI", "")

        # load experiment version
        config.prompts.version = os.getenv("PROMPT_VERSION", "default")

        return config

    def validate(self):
        """Fail-Fast: Checks for missing critical configurations during startup."""
        missing_keys = []
        if not self.api.serper_api_key: missing_keys.append("SERPER_API_KEY")
        if not self.api.groq_api_key: missing_keys.append("GROQ_API_KEY")
        if not self.api.rapid_api_key: missing_keys.append("RAPID_API_KEY")
        if not self.storage.postgres_uri: missing_keys.append("POSTGRES_URI")
        if not self.prompts.version: missing_keys.append("PROMPT_VERSION")
        
        if missing_keys:
            raise ValueError(f"🚨 Fatal Error: Missing critical environment variables: {', '.join(missing_keys)}")
            
        self.storage.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage.db_dir.mkdir(parents=True, exist_ok=True)