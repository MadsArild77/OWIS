from pathlib import Path
import os


def _default_db_path() -> str:
    return str(Path("platform/data/owi.db"))


def _default_sources_path() -> str:
    return str(Path("platform/modules/news/registry/sources.yaml"))


DB_PATH = os.getenv("OWI_DB_PATH", _default_db_path())
NEWS_SOURCES_PATH = os.getenv("OWI_NEWS_SOURCES", _default_sources_path())
