from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from owis.core.storage.db import get_conn


REGIONS = {
    "Norway": "NOR",
    "Nordics": "SWE DNK FIN ISL",
    "UK": "GBR",
    "Europe": "ALB AND AUT BEL BGR BIH BLR CHE CYP CZE DEU ESP EST FRA FRO GGY GIB GRC HRV HUN IMN IRL ITA JEY LIE LTU LUX LVA MCO MDA MKD MLT MNE NLD POL PRT ROU RUS SJM SMR SRB SVK SVN TUR UKR VAT XKX EU EUR EUE",
    "Americas": "ABW AIA ARG ATG BES BHS BLZ BMU BOL BRA BRB CAN CHL COL CRI CUB CUW CYM DMA DOM ECU FLK GLP GRD GRL GTM GUF GUY HND HTI JAM KNA LCA MAF MEX MSR MTQ NIC PAN PER PRI PRY SPM SLV SUR SXM TCA TTO URY USA VCT VEN VGB VIR",
    "Asia-Pacific": "AFG ARM ASM AUS AZE BGD BRN BTN CCK CHN COK CXR FJI FSM GEO GUM HKG HMD IDN IND JPN KAZ KGZ KHM KIR KOR LAO LKA MAC MDV MHL MMR MNG MNP MYS NCL NFK NIU NPL NRU NZL PAK PCN PHL PLW PNG PRK PYF SGP SLB THA TJK TKL TKM TLS TON TUV TWN UMI UZB VNM VUT WLF WSM",
    "Middle East & Africa": "AGO ARE BDI BEN BFA BHR BWA CAF CIV CMR COD COG COM CPV DJI DZA EGY ERI ESH ETH GAB GHA GIN GMB GNB GNQ IRN IRQ ISR JOR KEN KWT LBN LBR LBY LSO MAR MDG MLI MOZ MRT MUS MWI MYT NAM NER NGA OMN PSE QAT REU RWA SAU SDN SEN SHN SLE SOM SSD STP SWZ SYC SYR TCD TGO TUN TZA UGA YEM ZAF ZMB ZWE",
}


def country_region(country: str) -> str:
    return next((region for region, codes in REGIONS.items() if (country or "").upper() in codes.split()), "")


class OpportunitiesRepository:
    @staticmethod
    def _ensure_states(conn):
        conn.execute("""CREATE TABLE IF NOT EXISTS opportunity_item_states (
            raw_item_id INTEGER PRIMARY KEY REFERENCES opportunity_raw_items(id),
            state TEXT NOT NULL CHECK (state IN ('saved', 'hidden', 'none'))
        )""")

    def set_state(self, item_id: int, state: str) -> bool:
        with get_conn() as conn:
            self._ensure_states(conn)
            row = conn.execute("SELECT raw_item_id FROM opportunity_processed_items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                return False
            conn.execute("""INSERT INTO opportunity_item_states (raw_item_id, state) VALUES (?, ?)
                ON CONFLICT(raw_item_id) DO UPDATE SET state = excluded.state""", (row[0], state))
            return True

    def list_items(self, *, view="open", profiles=(), region="", source="", fit="", q="", limit=100):
        today = datetime.now(timezone.utc).date()
        with get_conn() as conn:
            self._ensure_states(conn)
            rows = conn.execute("""SELECT p.*, r.publication_date, r.cpv_codes,
                COALESCE(s.state, 'none') AS state
                FROM opportunity_processed_items p
                JOIN opportunity_raw_items r ON r.id = p.raw_item_id
                LEFT JOIN opportunity_item_states s ON s.raw_item_id = p.raw_item_id""").fetchall()
        total = len(rows)
        matches = []
        for row in rows:
            item = dict(row)
            item["region"] = country_region(item["country"])
            item["fit"] = {"Strong": "High", "Weak": "Low"}.get(item["strategic_fit"], item["strategic_fit"])
            services = (item.get("matched_services") or "").split(",")
            if profiles and not any(p == item["profile_name"] or p in services for p in profiles):
                continue
            if region and item["region"] != region:
                continue
            if source and item["source_name"] != source:
                continue
            if fit and item["fit"].lower() != fit.lower():
                continue
            if q and q.casefold() not in " ".join(str(item.get(k) or "") for k in ("title", "buyer", "summary", "country", "matched_services", "matched_qualifiers")).casefold():
                continue
            matches.append(item)

        def in_view(item, selected):
            if selected in {"saved", "hidden"}:
                return item["state"] == selected
            deadline = (item.get("deadline") or "")[:10]
            if item["state"] == "hidden" or (deadline and deadline < today.isoformat()):
                return False
            if selected == "closing-soon":
                return bool(deadline) and deadline <= (today + timedelta(days=14)).isoformat()
            if selected == "new":
                return (today - timedelta(days=6)).isoformat() <= (item.get("publication_date") or "")[:10] <= today.isoformat()
            return True

        counts = {name: sum(in_view(item, name) for item in matches) for name in ("open", "closing-soon", "new", "saved", "hidden")}
        items = [item for item in matches if in_view(item, view)]
        if view == "new":
            items.sort(key=lambda item: (item.get("publication_date") or "", item["id"]), reverse=True)
        else:
            items.sort(key=lambda item: (item.get("deadline") or "9999-12-31", item["id"]))
        return {"items": items[:limit], "counts": counts, "total": total, "today": today.isoformat()}

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
                    deadline_raw,
                    estimated_value,
                    currency,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    item.get("deadline_raw"),
                    item.get("estimated_value"),
                    item.get("currency"),
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
                    deadline_source,
                    estimated_value,
                    currency,
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    processed.get("deadline_source"),
                    processed.get("estimated_value"),
                    processed.get("currency"),
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

    def save_source_run(self, source_report: dict[str, Any], started_at: str, completed_at: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO opportunity_source_runs
                (source_name, started_at, completed_at, status, error, fetched, new_items, filtered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_report["source"], started_at, completed_at, source_report["status"],
                 source_report.get("error"), source_report.get("items", 0),
                 source_report.get("new_items", 0), source_report.get("filtered", 0)),
            )

    def latest_source_runs(self) -> dict[str, dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute("""SELECT * FROM opportunity_source_runs WHERE id IN
                (SELECT MAX(id) FROM opportunity_source_runs GROUP BY source_name)""").fetchall()
            return {row["source_name"]: dict(row) for row in rows}

    def successful_source_starts(self) -> dict[str, str]:
        with get_conn() as conn:
            rows = conn.execute("""SELECT source_name, MAX(started_at) AS started_at
                FROM opportunity_source_runs WHERE status = 'ok' GROUP BY source_name""").fetchall()
            return {row["source_name"]: row["started_at"] for row in rows}
