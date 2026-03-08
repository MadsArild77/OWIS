from pathlib import Path
import os


def _default_db_path() -> str:
    return str(Path("platform/data/owi.db"))


def _default_sources_path() -> str:
    return str(Path("platform/modules/news/registry/sources.yaml"))


DB_PATH = os.getenv("OWI_DB_PATH", _default_db_path())
NEWS_SOURCES_PATH = os.getenv("OWI_NEWS_SOURCES", _default_sources_path())

# Optional AI layer for article enrichment.
AI_ENABLED = os.getenv("OWI_AI_ENABLED", "false").lower() in {"1", "true", "yes"}
AI_PROVIDER = os.getenv("OWI_AI_PROVIDER", "openai_compatible")
AI_MODEL = os.getenv("OWI_AI_MODEL", "gpt-4o-mini")
AI_BASE_URL = os.getenv("OWI_AI_BASE_URL", "https://api.openai.com/v1")
AI_ENDPOINT = os.getenv("OWI_AI_ENDPOINT", "/chat/completions")
AI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_INPUT_MAX_CHARS = int(os.getenv("OWI_AI_INPUT_MAX_CHARS", "3500"))
AI_MAX_TOKENS = int(os.getenv("OWI_AI_MAX_TOKENS", "220"))
