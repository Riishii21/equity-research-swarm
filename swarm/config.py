"""Central configuration. All runtime switches live here."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    model_provider: str = os.getenv("MODEL_PROVIDER", "mock")
    model_name: str = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    data_mode: str = os.getenv("DATA_MODE", "sample")
    rag_embeddings: str = os.getenv("RAG_EMBEDDINGS", "lexical")
    max_revisions: int = int(os.getenv("MAX_REVISIONS", "2"))

    # live-data settings
    metrics_provider: str = os.getenv("METRICS_PROVIDER", "fmp")  # fmp | alphavantage
    fmp_api_key: str = os.getenv("FMP_API_KEY", "")
    alphavantage_api_key: str = os.getenv("ALPHAVANTAGE_API_KEY", "")
    sec_user_agent: str = os.getenv("SEC_USER_AGENT", "")  # EDGAR requires an email

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")


CONFIG = Config()
