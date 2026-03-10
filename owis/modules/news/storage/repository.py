from datetime import datetime, timezone
import json
from typing import Any

from owis.core.storage.db import get_conn


class NewsRepository:
    @staticmethod
    def _clean_ids(values: list[int]) -> list[int]:
        cleaned = {int(x) for x in values if int(x) > 0}
        return sorted(cleaned)

    @staticmethod
    def _clean_source_name(source_name: str | None) -> str | None:
        if source_name is None:
            return None
        cleaned = str(source_name).strip()
        return cleaned or None

    def upsert_raw_item_get_id(self, item: dict[str, Any]) -> int | None:
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM news_raw_items WHERE article_url = ?",
                (item["article_url"],),
            ).fetchone()
            if existing:
                return None

            cur = conn.execute(
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
            return int(cur.lastrowid)

    def upsert_raw_item(self, item: dict[str, Any]) -> bool:
        return self.upsert_raw_item_get_id(item) is not None

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

    def list_unprocessed_raw_by_ids(self, raw_ids: list[int]) -> list[dict[str, Any]]:
        cleaned = self._clean_ids(raw_ids)
        if not cleaned:
            return []

        placeholders = ",".join("?" for _ in cleaned)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM news_raw_items
                WHERE id IN ({placeholders}) AND status IN ('new', 'parsed')
                ORDER BY fetched_at DESC
                """,
                tuple(cleaned),
            ).fetchall()
            return [dict(row) for row in rows]

    def latest_raw_checkpoint(self) -> str | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(published_at), MAX(fetched_at)) AS checkpoint
                FROM news_raw_items
                """
            ).fetchone()
            if not row:
                return None
            value = row["checkpoint"]
            return str(value) if value else None

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

    def latest(self, limit: int = 20, source_name: str | None = None) -> list[dict[str, Any]]:
        source = self._clean_source_name(source_name)
        where = "WHERE LOWER(r.source_name) = LOWER(?)" if source else ""
        params: list[Any] = [source] if source else []
        params.append(limit)

        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                {where}
                ORDER BY COALESCE(r.published_at, p.processed_at) DESC, p.processed_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]

    def top_signals(self, limit: int = 20, source_name: str | None = None) -> list[dict[str, Any]]:
        source = self._clean_source_name(source_name)
        where = "WHERE LOWER(r.source_name) = LOWER(?)" if source else ""
        params: list[Any] = [source] if source else []
        params.append(limit)

        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                {where}
                ORDER BY p.signal_score DESC, p.processed_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]

    def linkedin_candidates(self, limit: int = 20, source_name: str | None = None) -> list[dict[str, Any]]:
        source = self._clean_source_name(source_name)
        where = "WHERE p.linkedin_candidate = 1"
        params: list[Any] = []
        if source:
            where += " AND LOWER(r.source_name) = LOWER(?)"
            params.append(source)
        params.append(limit)

        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                {where}
                ORDER BY p.signal_score DESC, p.processed_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_relevance_map(self, processed_ids: list[int]) -> dict[int, int]:
        cleaned = self._clean_ids(processed_ids)
        if not cleaned:
            return {}

        placeholders = ",".join("?" for _ in cleaned)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT processed_id, relevance
                FROM news_item_relevance
                WHERE processed_id IN ({placeholders})
                """,
                tuple(cleaned),
            ).fetchall()
            return {int(row["processed_id"]): int(row["relevance"]) for row in rows}

    def set_relevance(self, processed_ids: list[int], relevance: int | None) -> int:
        cleaned = self._clean_ids(processed_ids)
        if not cleaned:
            return 0

        placeholders = ",".join("?" for _ in cleaned)
        with get_conn() as conn:
            if relevance is None:
                cur = conn.execute(
                    f"DELETE FROM news_item_relevance WHERE processed_id IN ({placeholders})",
                    tuple(cleaned),
                )
                return int(cur.rowcount)

            updated_at = datetime.now(timezone.utc).isoformat()
            for processed_id in cleaned:
                conn.execute(
                    """
                    INSERT INTO news_item_relevance (processed_id, relevance, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(processed_id) DO UPDATE SET
                        relevance = excluded.relevance,
                        updated_at = excluded.updated_at
                    """,
                    (processed_id, int(relevance), updated_at),
                )
            return len(cleaned)

    def set_linkedin_candidate(self, processed_ids: list[int], qualified: bool) -> int:
        return self.set_relevance(processed_ids, 1 if qualified else 0)

    def list_domain_map(self, processed_ids: list[int]) -> dict[int, dict[str, Any]]:
        cleaned = self._clean_ids(processed_ids)
        if not cleaned:
            return {}

        placeholders = ",".join("?" for _ in cleaned)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT processed_id, domain_bucket, domain_confidence, classified_at
                FROM news_domain_classification
                WHERE processed_id IN ({placeholders})
                """,
                tuple(cleaned),
            ).fetchall()
            return {
                int(row["processed_id"]): {
                    "domain_bucket": row["domain_bucket"],
                    "domain_confidence": float(row["domain_confidence"] or 0.0),
                    "classified_at": row["classified_at"],
                }
                for row in rows
            }

    def upsert_domain_classification(self, processed_id: int, domain_bucket: str, domain_confidence: float) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO news_domain_classification (processed_id, domain_bucket, domain_confidence, classified_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(processed_id) DO UPDATE SET
                    domain_bucket = excluded.domain_bucket,
                    domain_confidence = excluded.domain_confidence,
                    classified_at = excluded.classified_at
                """,
                (
                    int(processed_id),
                    str(domain_bucket),
                    float(domain_confidence),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

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

    def list_processed_by_ids(self, processed_ids: list[int]) -> list[dict[str, Any]]:
        cleaned = self._clean_ids(processed_ids)
        if not cleaned:
            return []

        placeholders = ",".join("?" for _ in cleaned)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                WHERE p.id IN ({placeholders})
                """,
                tuple(cleaned),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_processed_since(self, since_iso: str, limit: int = 400) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.source_name, r.article_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                WHERE COALESCE(r.published_at, p.processed_at) >= ?
                ORDER BY COALESCE(r.published_at, p.processed_at) DESC, p.processed_at DESC
                LIMIT ?
                """,
                (since_iso, int(limit)),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_collection_overrides(self) -> dict[int, dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT processed_id, collection_key, note, updated_at
                FROM news_collection_overrides
                """
            ).fetchall()
            return {int(row["processed_id"]): dict(row) for row in rows}

    def set_collection_overrides(self, processed_ids: list[int], collection_key: str, note: str | None = None) -> int:
        cleaned = self._clean_ids(processed_ids)
        if not cleaned:
            return 0

        key = collection_key.strip()
        if not key:
            return 0

        updated_at = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            for processed_id in cleaned:
                conn.execute(
                    """
                    INSERT INTO news_collection_overrides (processed_id, collection_key, note, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(processed_id) DO UPDATE SET
                        collection_key = excluded.collection_key,
                        note = excluded.note,
                        updated_at = excluded.updated_at
                    """,
                    (processed_id, key, note, updated_at),
                )
        return len(cleaned)

    def clear_collection_overrides(self, processed_ids: list[int]) -> int:
        cleaned = self._clean_ids(processed_ids)
        if not cleaned:
            return 0

        placeholders = ",".join("?" for _ in cleaned)
        with get_conn() as conn:
            cur = conn.execute(
                f"DELETE FROM news_collection_overrides WHERE processed_id IN ({placeholders})",
                tuple(cleaned),
            )
            return int(cur.rowcount)

    def upsert_match_review_pair(
        self,
        item_a_id: int,
        item_b_id: int,
        ai_same_story: str,
        ai_confidence: float,
        reason_short: str,
        overlap_entities: list[str],
        overlap_timeframe: str,
    ) -> int:
        a, b = sorted([int(item_a_id), int(item_b_id)])
        created_at = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO news_match_review_pairs (
                    item_a_id, item_b_id, ai_same_story, ai_confidence,
                    reason_short, overlap_entities, overlap_timeframe,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                ON CONFLICT(item_a_id, item_b_id) DO UPDATE SET
                    ai_same_story = excluded.ai_same_story,
                    ai_confidence = excluded.ai_confidence,
                    reason_short = excluded.reason_short,
                    overlap_entities = excluded.overlap_entities,
                    overlap_timeframe = excluded.overlap_timeframe
                """,
                (
                    a,
                    b,
                    str(ai_same_story),
                    float(ai_confidence),
                    str(reason_short or ""),
                    json.dumps(overlap_entities or []),
                    str(overlap_timeframe or ""),
                    created_at,
                ),
            )
            row = conn.execute(
                "SELECT id FROM news_match_review_pairs WHERE item_a_id = ? AND item_b_id = ?",
                (a, b),
            ).fetchone()
            return int(row["id"])

    def list_match_review_pairs(
        self,
        status: str = "pending",
        domain_bucket: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [status]
        domain_sql = ""
        if domain_bucket and domain_bucket != "all":
            domain_sql = "AND dca.domain_bucket = ? AND dcb.domain_bucket = ?"
            params.extend([domain_bucket, domain_bucket])
        params.append(int(limit))

        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.id,
                    p.item_a_id,
                    p.item_b_id,
                    p.ai_same_story,
                    p.ai_confidence,
                    p.reason_short,
                    p.overlap_entities,
                    p.overlap_timeframe,
                    p.status,
                    p.decided_by,
                    p.decided_at,
                    p.created_at,
                    a.title AS item_a_title,
                    a.summary AS item_a_summary,
                    ra.source_name AS item_a_source,
                    ra.article_url AS item_a_url,
                    ra.published_at AS item_a_published_at,
                    b.title AS item_b_title,
                    b.summary AS item_b_summary,
                    rb.source_name AS item_b_source,
                    rb.article_url AS item_b_url,
                    rb.published_at AS item_b_published_at,
                    dca.domain_bucket AS item_a_domain_bucket,
                    dcb.domain_bucket AS item_b_domain_bucket
                FROM news_match_review_pairs p
                JOIN news_processed_items a ON a.id = p.item_a_id
                JOIN news_raw_items ra ON ra.id = a.raw_item_id
                JOIN news_processed_items b ON b.id = p.item_b_id
                JOIN news_raw_items rb ON rb.id = b.raw_item_id
                LEFT JOIN news_domain_classification dca ON dca.processed_id = p.item_a_id
                LEFT JOIN news_domain_classification dcb ON dcb.processed_id = p.item_b_id
                WHERE p.status = ?
                {domain_sql}
                ORDER BY p.ai_confidence DESC, p.created_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

            out: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["overlap_entities"] = json.loads(str(item.get("overlap_entities") or "[]"))
                except Exception:
                    item["overlap_entities"] = []
                out.append(item)
            return out

    def get_match_review_pair(self, pair_id: int) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT id, item_a_id, item_b_id, status
                FROM news_match_review_pairs
                WHERE id = ?
                """,
                (int(pair_id),),
            ).fetchone()
            return dict(row) if row else None

    def decide_match_review_pair(self, pair_id: int, decision: str, actor: str | None = None) -> int:
        status = "accepted" if decision == "accept" else "rejected"
        with get_conn() as conn:
            cur = conn.execute(
                """
                UPDATE news_match_review_pairs
                SET status = ?, decided_by = ?, decided_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    actor,
                    datetime.now(timezone.utc).isoformat(),
                    int(pair_id),
                ),
            )
            return int(cur.rowcount)

    def log_learning_feedback(
        self,
        feedback_type: str,
        feedback_value: str,
        processed_id: int | None = None,
        pair_id: int | None = None,
        actor: str | None = None,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO news_learning_feedback (processed_id, pair_id, feedback_type, feedback_value, actor, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(processed_id) if processed_id else None,
                    int(pair_id) if pair_id else None,
                    str(feedback_type),
                    str(feedback_value),
                    actor,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

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

    def list_source_health_states(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT source_name, health_score, health_color, last_items, last_error, updated_at
                FROM source_fetch_health
                ORDER BY source_name ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

