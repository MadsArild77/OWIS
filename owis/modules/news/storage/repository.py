from typing import Any

from owis.core.storage.db import get_conn


class NewsRepository:
    def upsert_raw_item(self, item: dict[str, Any]) -> bool:
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM news_raw_items WHERE article_url = ?",
                (item["article_url"],),
            ).fetchone()
            if existing:
                return False

            conn.execute(
                """
                INSERT INTO news_raw_items (
                    source_name, article_url, title_raw, summary_raw,
                    content_raw, content_hash, published_at, fetched_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["source_name"],
                    item["article_url"],
                    item["title_raw"],
                    item.get("summary_raw", ""),
                    item.get("content_raw", ""),
                    item["content_hash"],
                    item.get("published_at"),
                    item["fetched_at"],
                    "new",
                ),
            )
            return True

    def list_unprocessed_raw(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM news_raw_items
                WHERE status IN ('new', 'parsed')
                ORDER BY fetched_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_raw_processed(self, raw_id: int) -> None:
        with get_conn() as conn:
            conn.execute(
                "UPDATE news_raw_items SET status = 'processed' WHERE id = ?",
                (raw_id,),
            )

    def save_processed_item(self, processed: dict[str, Any]) -> int:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT OR REPLACE INTO news_processed_items (
                    raw_item_id, title, cleaned_text, summary, theme_tags,
                    geography_tags, actors, why_it_matters,
                    signal_score, confidence, linkedin_angle,
                    linkedin_candidate, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    processed["raw_item_id"],
                    processed["title"],
                    processed["cleaned_text"],
                    processed["summary"],
                    processed["theme_tags"],
                    processed["geography_tags"],
                    processed["actors"],
                    processed["why_it_matters"],
                    processed["signal_score"],
                    processed["confidence"],
                    processed["linkedin_angle"],
                    processed["linkedin_candidate"],
                    processed["processed_at"],
                ),
            )
            return int(cur.lastrowid)

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                ORDER BY COALESCE(r.published_at, p.processed_at) DESC, p.processed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def top_signals(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                ORDER BY p.signal_score DESC, p.processed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def linkedin_candidates(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                WHERE p.linkedin_candidate = 1
                ORDER BY p.signal_score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_item(self, processed_id: int) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                WHERE p.id = ?
                """,
                (processed_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_source_health_state(self, source_name: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT source_name, health_score, health_color, last_items, last_error, updated_at
                FROM source_fetch_health
                WHERE source_name = ?
                """,
                (source_name,),
            ).fetchone()
            return dict(row) if row else None

    def upsert_source_health_state(
        self,
        source_name: str,
        health_score: int,
        health_color: str,
        last_items: int,
        last_error: str | None,
        updated_at: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO source_fetch_health (
                    source_name, health_score, health_color, last_items, last_error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    health_score = excluded.health_score,
                    health_color = excluded.health_color,
                    last_items = excluded.last_items,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (source_name, health_score, health_color, last_items, last_error, updated_at),
            )
