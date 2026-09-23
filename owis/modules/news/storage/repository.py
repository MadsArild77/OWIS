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

            archived = conn.execute(
                "SELECT 1 FROM news_article_archive WHERE article_url = ?",
                (item["article_url"],),
            ).fetchone()
            if archived:
                return None

            cur = conn.execute(
                """
                INSERT INTO news_raw_items (
                    source_name, article_url, title_raw, summary_raw,
                    content_raw, content_hash, image_url, published_at, fetched_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["source_name"],
                    item["article_url"],
                    item["title_raw"],
                    item.get("summary_raw", ""),
                    item.get("content_raw", ""),
                    item["content_hash"],
                    item.get("image_url", ""),
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
                SELECT p.*, r.source_name, r.article_url, r.image_url, r.published_at
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
                SELECT p.*, r.source_name, r.article_url, r.image_url, r.published_at
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
                SELECT p.*, r.source_name, r.article_url, r.image_url, r.published_at
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
                SELECT p.*, r.source_name, r.article_url, r.image_url, r.published_at
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
                SELECT p.*, r.source_name, r.article_url, r.image_url, r.published_at
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
                SELECT p.*, r.source_name, r.article_url, r.image_url, r.published_at
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                WHERE COALESCE(r.published_at, p.processed_at) >= ?
                ORDER BY COALESCE(r.published_at, p.processed_at) DESC, p.processed_at DESC
                LIMIT ?
                """,
                (since_iso, int(limit)),
            ).fetchall()
            return [dict(row) for row in rows]

    def archive_old_unprotected_items(self, cutoff_iso: str, limit: int = 1000) -> dict[str, int]:
        """
        Move old, non-curated articles into a lightweight archive and remove full text.

        Curated items are deliberately retained in the main tables because they can
        back manual merges, relevance decisions, match-review history, or pair learning.
        """
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.id AS processed_id,
                    p.raw_item_id,
                    p.title,
                    p.theme_tags,
                    p.geography_tags,
                    p.actors,
                    p.signal_score,
                    p.confidence,
                    r.source_name,
                    r.article_url,
                    r.published_at,
                    r.fetched_at,
                    d.domain_bucket
                FROM news_processed_items p
                JOIN news_raw_items r ON r.id = p.raw_item_id
                LEFT JOIN news_domain_classification d ON d.processed_id = p.id
                WHERE julianday(COALESCE(r.published_at, p.processed_at)) < julianday(?)
                  AND NOT EXISTS (SELECT 1 FROM news_collection_overrides o WHERE o.processed_id = p.id)
                  AND NOT EXISTS (SELECT 1 FROM news_item_relevance rel WHERE rel.processed_id = p.id)
                  AND NOT EXISTS (SELECT 1 FROM news_match_review_pairs mr WHERE mr.item_a_id = p.id OR mr.item_b_id = p.id)
                  AND NOT EXISTS (SELECT 1 FROM news_pair_learning pl WHERE pl.item_a_id = p.id OR pl.item_b_id = p.id)
                  AND NOT EXISTS (SELECT 1 FROM news_learning_feedback lf WHERE lf.processed_id = p.id)
                ORDER BY COALESCE(r.published_at, p.processed_at) ASC
                LIMIT ?
                """,
                (cutoff_iso, int(limit)),
            ).fetchall()
            items = [dict(row) for row in rows]
            if not items:
                return {"archived": 0, "deleted_processed": 0, "deleted_raw": 0}

            archived_at = datetime.now(timezone.utc).isoformat()
            for item in items:
                title = str(item.get("title") or "Untitled")
                is_paywalled = 1 if "[paywalled]" in title.lower() else 0
                conn.execute(
                    """
                    INSERT INTO news_article_archive (
                        article_url, source_name, title, published_at, first_seen_at,
                        last_seen_at, archived_at, theme_tags, geography_tags, actors,
                        domain_bucket, signal_score, confidence, is_paywalled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(article_url) DO UPDATE SET
                        source_name = excluded.source_name,
                        title = excluded.title,
                        published_at = excluded.published_at,
                        last_seen_at = excluded.last_seen_at,
                        archived_at = excluded.archived_at,
                        theme_tags = excluded.theme_tags,
                        geography_tags = excluded.geography_tags,
                        actors = excluded.actors,
                        domain_bucket = excluded.domain_bucket,
                        signal_score = excluded.signal_score,
                        confidence = excluded.confidence,
                        is_paywalled = excluded.is_paywalled
                    """,
                    (
                        str(item.get("article_url") or ""),
                        str(item.get("source_name") or "Unknown"),
                        title,
                        item.get("published_at"),
                        item.get("fetched_at"),
                        item.get("fetched_at"),
                        archived_at,
                        str(item.get("theme_tags") or ""),
                        str(item.get("geography_tags") or ""),
                        str(item.get("actors") or ""),
                        item.get("domain_bucket"),
                        int(item.get("signal_score") or 0),
                        float(item.get("confidence") or 0.0),
                        is_paywalled,
                    ),
                )

            processed_ids = [int(item["processed_id"]) for item in items]
            raw_ids = [int(item["raw_item_id"]) for item in items]
            processed_placeholders = ",".join("?" for _ in processed_ids)
            raw_placeholders = ",".join("?" for _ in raw_ids)

            conn.execute(
                f"DELETE FROM news_domain_classification WHERE processed_id IN ({processed_placeholders})",
                tuple(processed_ids),
            )
            processed_cur = conn.execute(
                f"DELETE FROM news_processed_items WHERE id IN ({processed_placeholders})",
                tuple(processed_ids),
            )
            raw_cur = conn.execute(
                f"DELETE FROM news_raw_items WHERE id IN ({raw_placeholders})",
                tuple(raw_ids),
            )
            return {
                "archived": len(items),
                "deleted_processed": int(processed_cur.rowcount),
                "deleted_raw": int(raw_cur.rowcount),
            }

    def archive_summary(self) -> dict[str, int]:
        with get_conn() as conn:
            archive_count = conn.execute("SELECT COUNT(*) AS n FROM news_article_archive").fetchone()
            active_count = conn.execute("SELECT COUNT(*) AS n FROM news_processed_items").fetchone()
            return {
                "active_items": int(active_count["n"] or 0),
                "archived_items": int(archive_count["n"] or 0),
            }

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

    def upsert_collection_master(self, master: dict[str, Any]) -> None:
        collection_key = str(master.get("collection_key") or "").strip()
        if not collection_key:
            return

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO news_collection_masters (
                    collection_key, title, summary, why_it_matters,
                    theme_tags, geography_tags, actors, sources,
                    image_url, lead_item_id, article_count, synthesized_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection_key) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    why_it_matters = excluded.why_it_matters,
                    theme_tags = excluded.theme_tags,
                    geography_tags = excluded.geography_tags,
                    actors = excluded.actors,
                    sources = excluded.sources,
                    image_url = excluded.image_url,
                    lead_item_id = excluded.lead_item_id,
                    article_count = excluded.article_count,
                    synthesized_at = excluded.synthesized_at
                """,
                (
                    collection_key,
                    str(master.get("title") or "Merged story"),
                    str(master.get("summary") or ""),
                    str(master.get("why_it_matters") or ""),
                    str(master.get("theme_tags") or ""),
                    str(master.get("geography_tags") or ""),
                    str(master.get("actors") or ""),
                    str(master.get("sources") or ""),
                    str(master.get("image_url") or ""),
                    int(master.get("lead_item_id") or 0) or None,
                    int(master.get("article_count") or 0),
                    str(master.get("synthesized_at") or datetime.now(timezone.utc).isoformat()),
                ),
            )

    def list_collection_masters(self) -> dict[str, dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT collection_key, title, summary, why_it_matters,
                       theme_tags, geography_tags, actors, sources,
                       image_url, lead_item_id, article_count, synthesized_at
                FROM news_collection_masters
                """
            ).fetchall()
            return {str(row["collection_key"]): dict(row) for row in rows}

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

    def upsert_pair_learning(self, item_a_id: int, item_b_id: int, decision: str, source: str) -> None:
        a, b = sorted([int(item_a_id), int(item_b_id)])
        if a <= 0 or b <= 0 or a == b:
            return
        if decision not in {"merge", "reject"}:
            return

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO news_pair_learning (item_a_id, item_b_id, decision, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(item_a_id, item_b_id) DO UPDATE SET
                    decision = excluded.decision,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    a,
                    b,
                    decision,
                    source,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_pair_learning(self, decision: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if decision:
            where = "WHERE decision = ?"
            params.append(decision)

        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT item_a_id, item_b_id, decision, source, updated_at
                FROM news_pair_learning
                {where}
                """,
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]

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

