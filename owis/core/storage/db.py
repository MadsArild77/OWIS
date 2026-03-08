import sqlite3
from pathlib import Path

from owis.core.config.settings import DB_PATH


def get_conn() -> sqlite3.Connection:
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS news_raw_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                article_url TEXT NOT NULL UNIQUE,
                title_raw TEXT NOT NULL,
                summary_raw TEXT,
                content_raw TEXT,
                content_hash TEXT NOT NULL,
                published_at TEXT,
                fetched_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new'
            );

            CREATE TABLE IF NOT EXISTS news_processed_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_item_id INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                summary TEXT NOT NULL,
                theme_tags TEXT NOT NULL,
                geography_tags TEXT NOT NULL,
                actors TEXT NOT NULL,
                why_it_matters TEXT NOT NULL,
                signal_score INTEGER NOT NULL,
                confidence REAL NOT NULL,
                linkedin_angle TEXT NOT NULL,
                linkedin_candidate INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                FOREIGN KEY(raw_item_id) REFERENCES news_raw_items(id)
            );

            CREATE TABLE IF NOT EXISTS source_fetch_health (
                source_name TEXT PRIMARY KEY,
                health_score INTEGER NOT NULL,
                health_color TEXT NOT NULL,
                last_items INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS news_collection_overrides (
                processed_id INTEGER PRIMARY KEY,
                collection_key TEXT NOT NULL,
                note TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(processed_id) REFERENCES news_processed_items(id)
            );

            CREATE TABLE IF NOT EXISTS opportunity_raw_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notice_id TEXT NOT NULL UNIQUE,
                source_name TEXT NOT NULL,
                notice_url TEXT NOT NULL,
                title_raw TEXT NOT NULL,
                buyer_raw TEXT,
                country_raw TEXT,
                publication_date TEXT,
                description_raw TEXT,
                cpv_codes TEXT,
                content_hash TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new'
            );

            CREATE TABLE IF NOT EXISTS opportunity_processed_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_item_id INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                buyer TEXT,
                country TEXT,
                summary TEXT NOT NULL,
                opportunity_family TEXT NOT NULL,
                mechanism_type TEXT NOT NULL,
                deadline TEXT,
                strategic_fit TEXT NOT NULL,
                competition_level TEXT NOT NULL,
                matched_services TEXT NOT NULL,
                matched_qualifiers TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                why_it_matters TEXT NOT NULL,
                signal_score INTEGER NOT NULL,
                confidence REAL NOT NULL,
                profile_name TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                FOREIGN KEY(raw_item_id) REFERENCES opportunity_raw_items(id)
            );
            """
        )
