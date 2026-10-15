"""Read-only view of the eInnsyn monitor's Notion databases.

The separate eInnsyn monitor (github.com/MadsArild77/eInnsyn) writes cases,
journal posts and search terms to Notion. This module only reads those
databases and builds an overview for the /einnsyn page; it never writes, so
Notion stays the single source of truth.
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

NOTION_BASE = "https://api.notion.com/v1"
RETRY_STATUS = {429, 500, 502, 503, 504}
SUGGESTION_MARK = "Forslag fra ukentlig sjekk"


def _text(prop: dict[str, Any] | None) -> str:
    if not isinstance(prop, dict):
        return ""
    kind = prop.get("type")
    value = prop.get(kind)
    if kind in ("title", "rich_text"):
        return "".join(str(p.get("plain_text") or "") for p in value or []).strip()
    if kind == "select":
        return str((value or {}).get("name") or "")
    if kind == "url":
        return str(value or "")
    if kind == "date":
        return str((value or {}).get("start") or "")[:10]
    if kind == "relation":
        return ",".join(str(r.get("id") or "") for r in value or [])
    return ""


def _row(page: dict[str, Any]) -> dict[str, str]:
    row = {name: _text(prop) for name, prop in (page.get("properties") or {}).items()}
    row["_id"] = str(page.get("id") or "")
    row["_url"] = str(page.get("url") or "")
    row["_created"] = str(page.get("created_time") or "")[:10]
    return row


def _parse_day(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


class EinnsynNotionReader:
    def __init__(self, api_key: str, saker_db: str, logg_db: str, sok_db: str,
                 notion_version: str = "2022-06-28", client: httpx.Client | None = None) -> None:
        self.api_key = api_key.strip()
        self.dbs = {"saker": saker_db.strip(), "logg": logg_db.strip(), "sok": sok_db.strip()}
        self.notion_version = notion_version
        self.client = client or httpx.Client(timeout=60)

    def configured(self) -> bool:
        return bool(self.api_key and all(self.dbs.values()))

    def _query_all(self, database_id: str) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Notion-Version": self.notion_version}
        url = f"{NOTION_BASE}/databases/{database_id}/query"
        body: dict[str, Any] = {"page_size": 100}
        pages: list[dict[str, Any]] = []
        while True:
            for attempt in range(1, 5):
                try:
                    resp = self.client.post(url, headers=headers, json=body)
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 4:
                        raise
                else:
                    if resp.status_code not in RETRY_STATUS or attempt == 4:
                        resp.raise_for_status()
                        break
                time.sleep(2 ** attempt)
            data = resp.json()
            pages.extend(data.get("results") or [])
            if not data.get("has_more"):
                return pages
            body["start_cursor"] = data.get("next_cursor")

    def load(self) -> dict[str, list[dict[str, str]]]:
        return {name: [_row(p) for p in self._query_all(db)] for name, db in self.dbs.items()}


def build_overview(data: dict[str, list[dict[str, str]]], today: date | None = None) -> dict[str, Any]:
    """Summarise the three databases. Pure function, so it is easy to test."""
    today = today or datetime.now(timezone.utc).date()
    saker, logg, sok = data.get("saker", []), data.get("logg", []), data.get("sok", [])
    case_names = {s.get("Saksnummer", ""): s.get("Name", "") for s in saker if s.get("Saksnummer")}

    def published(row: dict[str, str]) -> date | None:
        return _parse_day(row.get("Publisert") or row.get("Journaldato") or row.get("Dato") or "")

    recent_cut, active_cut, sender_cut = (today - timedelta(days=d) for d in (14, 30, 90))
    recent = sorted((r for r in logg if (published(r) or date.min) >= recent_cut),
                    key=lambda r: published(r) or date.min, reverse=True)

    active = Counter(r.get("Saksnummer", "") for r in logg
                     if r.get("Saksnummer") and (published(r) or date.min) >= active_cut)
    senders = Counter(r.get("Fra", "") for r in logg
                      if r.get("Fra") and (published(r) or date.min) >= sender_cut)

    status = Counter(s.get("Status", "") for s in saker)
    suggested = sorted((s for s in saker if s.get("Status") == "Foreslått"),
                       key=lambda s: s.get("_created", ""), reverse=True)
    keyword_suggestions = [k for k in sok if k.get("Status") == "Pause" and SUGGESTION_MARK in k.get("Notat", "")]
    keywords = [k for k in sok if k not in keyword_suggestions]

    return {
        "summary": {
            "active_cases": status.get("Aktiv", 0),
            "suggested_cases": status.get("Foreslått", 0),
            "log_entries": len(logg),
            "journal_posts_7d": sum(1 for r in logg if (published(r) or date.min) >= today - timedelta(days=7)),
            "journal_posts_30d": sum(active.values()),
            "active_keywords": sum(1 for k in keywords if k.get("Status") == "Aktiv"),
            "keyword_suggestions": len(keyword_suggestions),
        },
        "suggested_cases": [
            {"title": s.get("Name", ""), "case_number": s.get("Saksnummer", ""), "comment": s.get("Kommentar", ""),
             "url": s.get("URL", ""), "notion_url": s.get("_url", ""), "added": s.get("_created", "")}
            for s in suggested[:50]
        ],
        "recent_journal_posts": [
            {"title": r.get("Name", ""), "case_number": r.get("Saksnummer", ""),
             "case_title": case_names.get(r.get("Saksnummer", ""), ""), "from": r.get("Fra", ""),
             "to": r.get("Til", ""), "type": r.get("Journalposttype", ""),
             "published": str(published(r) or ""), "url": r.get("URL", "")}
            for r in recent[:60]
        ],
        "most_active_cases": [
            {"case_number": num, "title": case_names.get(num, ""), "journal_posts": n}
            for num, n in active.most_common(15)
        ],
        "top_senders": [{"name": name, "journal_posts": n} for name, n in senders.most_common(15)],
        "keywords": sorted(
            ({"query": k.get("Name", ""), "status": k.get("Status", ""), "note": k.get("Notat", ""),
              "last_run": k.get("Sist kjørt", ""), "notion_url": k.get("_url", "")} for k in keywords),
            key=lambda k: (k["status"] != "Aktiv", k["query"].lower())),
        "keyword_suggestions": [
            {"query": k.get("Name", ""), "note": k.get("Notat", ""), "notion_url": k.get("_url", "")}
            for k in keyword_suggestions
        ],
    }


class OverviewCache:
    """Keeps the overview for a while so page loads do not hit Notion every time."""

    def __init__(self, reader: EinnsynNotionReader, ttl_seconds: int = 1800) -> None:
        self.reader, self.ttl = reader, ttl_seconds
        self._value: dict[str, Any] | None = None
        self._loaded_at = 0.0
        self._lock = threading.Lock()

    def get(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if refresh or self._value is None or time.time() - self._loaded_at > self.ttl:
                overview = build_overview(self.reader.load())
                overview["loaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                self._value, self._loaded_at = overview, time.time()
            return self._value
