from __future__ import annotations

import hashlib
import json
from typing import Any

from owis.core.storage.db import get_conn


class OpportunitiesRepository:
    def upsert_raw_item(self, item: dict[str, Any]) -> bool:
        notice_id = str(item.get("id") or "").strip()
        if not notice_id:
            return False

        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        buyer = str(item.get("buyer") or "").strip()
        description = str(item.get("description") or "").strip()
        cpv_codes = item.get("cpv_codes") or []

        if not title or not url:
            return False

        content_hash = hashlib.sha256(f"{notice_id}|{title}|{url}".encode("utf-8")).hexdigest()

        with get_conn() as conn:
            exists = conn.execute(
                "SELECT id FROM opportunity_raw_items WHERE notice_id = ?",
                (notice_id,),
            ).fetchone()
            if exists:
                return False

            conn.execute(
                """
                INSERT INTO opportunity_raw_items (
                    notice_id,
                    source_name,
                    notice_url,
                    title_raw,
                    buyer_raw,
                    country_raw,
                    publication_date,
                    description_raw,
                    cpv_codes,
                    content_hash,
                    fetched_at,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notice_id,
                    str(item.get("source") or "UNKNOWN").upper(),
                    url,
                    title,
                    buyer,
                    str(item.get("country") or "").upper(),
                    str(item.get("publication_date") or ""),
                    description,
                    json.dumps(cpv_codes, ensure_ascii=True),
                    content_hash,
                    str(item.get("fetched_at") or ""),
                    "new",
                ),
            )
            return True

    def list_unprocessed_raw(self, limit: int = 100) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM opportunity_raw_items
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
                "UPDATE opportunity_raw_items SET status = 'processed' WHERE id = ?",
                (raw_id,),
            )

    def mark_raw_rejected(self, raw_id: int) -> None:
        with get_conn() as conn:
            conn.execute(
                "UPDATE opportunity_raw_items SET status = 'rejected' WHERE id = ?",
                (raw_id,),
            )

    def save_processed_item(self, processed: dict[str, Any]) -> int:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT OR REPLACE INTO opportunity_processed_items (
                    raw_item_id,
                    title,
                    source_name,
                    source_url,
                    buyer,
                    country,
                    summary,
                    opportunity_family,
                    mechanism_type,
                    deadline,
                    strategic_fit,
                    competition_level,
                    matched_services,
                    matched_qualifiers,
                    recommended_action,
                    why_it_matters,
                    signal_score,
                    confidence,
                    profile_name,
                    processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    processed["raw_item_id"],
                    processed["title"],
                    processed["source_name"],
                    processed["source_url"],
                    processed.get("buyer", ""),
                    processed.get("country", ""),
                    processed["summary"],
                    processed["opportunity_family"],
                    processed["mechanism_type"],
                    processed.get("deadline"),
                    processed["strategic_fit"],
                    processed["competition_level"],
                    processed["matched_services"],
                    processed["matched_qualifiers"],
                    processed["recommended_action"],
                    processed["why_it_matters"],
                    processed["signal_score"],
                    processed["confidence"],
                    processed.get("profile_name", ""),
                    processed["processed_at"],
                ),
            )
            return int(cur.lastrowid)

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.notice_id, r.publication_date
                FROM opportunity_processed_items p
                JOIN opportunity_raw_items r ON r.id = p.raw_item_id
                ORDER BY COALESCE(r.publication_date, p.processed_at) DESC, p.processed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def upcoming_deadlines(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.notice_id, r.publication_date
                FROM opportunity_processed_items p
                JOIN opportunity_raw_items r ON r.id = p.raw_item_id
                WHERE p.deadline IS NOT NULL AND p.deadline >= DATE('now')
                ORDER BY p.deadline ASC, p.signal_score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def high_relevance(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, r.notice_id, r.publication_date
                FROM opportunity_processed_items p
                JOIN opportunity_raw_items r ON r.id = p.raw_item_id
                ORDER BY p.signal_score DESC, p.processed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT p.*, r.notice_id, r.publication_date
                FROM opportunity_processed_items p
                JOIN opportunity_raw_items r ON r.id = p.raw_item_id
                WHERE p.id = ?
                """,
                (item_id,),
            ).fetchone()
            return dict(row) if row else None