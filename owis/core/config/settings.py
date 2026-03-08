from pathlib import Path
import os


def _default_db_path() -> str:
    return str(Path("owis/data/owi.db"))


def _default_sources_path() -> str:
    return str(Path("owis/modules/news/registry/sources.yaml"))


def _default_opportunities_profiles_path() -> str:
    return str(Path("owis/modules/opportunities/registry/profiles.yaml"))


DB_PATH = os.getenv("OWI_DB_PATH", _default_db_path())
NEWS_SOURCES_PATH = os.getenv("OWI_NEWS_SOURCES", _default_sources_path())
OPPORTUNITIES_PROFILES_PATH = os.getenv(
    "OWI_OPPORTUNITIES_PROFILES",
    _default_opportunities_profiles_path(),
)
OPPORTUNITIES_ENABLED_SOURCES = [
    s.strip().upper()
    for s in os.getenv("OWI_OPP_ENABLED_SOURCES", "TED,DOFFIN,WORLDBANK").split(",")
    if s.strip()
]
OPPORTUNITIES_ACTIVE_PROFILES = [
    p.strip().upper()
    for p in os.getenv("OWI_OPP_ACTIVE_PROFILES", "AGR,MAV").split(",")
    if p.strip()
]
OPPORTUNITIES_DAYS_BACK = int(os.getenv("OWI_OPP_DAYS_BACK", "30"))
TED_API_KEY = os.getenv("TED_API_KEY", "")

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_OPPORTUNITIES_DB_ID = os.getenv(
    "OWI_NOTION_OPPORTUNITIES_DB_ID",
    os.getenv("NOTION_OPPORTUNITIES_DB_ID", ""),
)
NOTION_VERSION = os.getenv("OWI_NOTION_VERSION", "2022-06-28")
OPPORTUNITIES_NOTION_EXPORT_ENABLED = os.getenv("OWI_OPP_NOTION_EXPORT_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}

# Optional AI layer for article enrichment.
AI_ENABLED = os.getenv("OWI_AI_ENABLED", "false").lower() in {"1", "true", "yes"}
AI_PROVIDER = os.getenv("OWI_AI_PROVIDER", "openai_compatible")
AI_MODEL = os.getenv("OWI_AI_MODEL", "gpt-4o-mini")
AI_BASE_URL = os.getenv("OWI_AI_BASE_URL", "https://api.openai.com/v1")
AI_ENDPOINT = os.getenv("OWI_AI_ENDPOINT", "/chat/completions")
AI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_INPUT_MAX_CHARS = int(os.getenv("OWI_AI_INPUT_MAX_CHARS", "3500"))
AI_MAX_TOKENS = int(os.getenv("OWI_AI_MAX_TOKENS", "220"))