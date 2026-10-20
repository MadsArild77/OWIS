"""View of the eInnsyn monitor's Notion databases.

The separate eInnsyn monitor (github.com/MadsArild77/eInnsyn) writes cases,
journal posts and search terms to Notion. This module reads those databases and
builds an overview for the /einnsyn page. The one thing it writes is a search
term's Status (Aktiv/Pause), from the switches on the page; Notion stays the
single source of truth.
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
PROJECT_FIELD, THEME_FIELD = "Prosjektområde", "Tema"
UNTAGGED = "Uklassifisert"
TAG_SEP = ", "
FOLLOWED = ("Aktiv", "Foreslått")


def _text(prop: dict[str, Any] | None) -> str:
    if not isinstance(prop, dict):
        return ""
    kind = prop.get("type")
    value = prop.get(kind)
    if kind in ("title", "rich_text"):
        return "".join(str(p.get("plain_text") or "") for p in value or []).strip()
    if kind == "select":
        return str((value or {}).get("name") or "")
    if kind == "multi_select":
        return TAG_SEP.join(str(o.get("name") or "") for o in value or [] if o.get("name"))
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


def _tags(row: dict[str, str], field: str) -> list[str]:
    """Project areas or themes of a case; cases without any count as «Uklassifisert»."""
    return [t for t in (row.get(field) or "").split(TAG_SEP) if t.strip()] or [UNTAGGED]


def _log_case_ids(row: dict[str, str]) -> list[str]:
    """Notion pages of the case a journal post belongs to (the «Sak» relation). Case numbers
    alone are not unique: two agencies can both have a case 2025/1234."""
    return [i for i in (row.get("Sak") or "").split(",") if i]


def _case_posts(posts_30d: Counter, case: dict[str, str]) -> int:
    """Posts are counted by case page when the log row links to one, else by case number."""
    return posts_30d.get(case.get("_id", ""), 0) + posts_30d.get("#" + case.get("Saksnummer", ""), 0)


def _case_latest(latest: dict[str, date], case: dict[str, str]) -> date | None:
    days = [d for d in (latest.get(case.get("_id", "")), latest.get("#" + case.get("Saksnummer", ""))) if d]
    return max(days) if days else None


def _facets(saker: list[dict[str, str]], posts_30d: Counter, field: str) -> list[dict[str, Any]]:
    """One box per project or theme: followed cases, suggested cases and new journal posts."""
    boxes: dict[str, dict[str, Any]] = {}
    for s in saker:
        if s.get("Status") not in FOLLOWED:
            continue
        for tag in _tags(s, field):
            box = boxes.setdefault(tag, {"name": tag, "cases": 0, "suggested": 0, "journal_posts_30d": 0})
            box["cases"] += 1
            box["suggested"] += s.get("Status") == "Foreslått"
            box["journal_posts_30d"] += _case_posts(posts_30d, s)
    return sorted(boxes.values(), key=lambda b: (b["name"] == UNTAGGED, -b["cases"], b["name"].lower()))


class EinnsynNotionReader:
    def __init__(self, api_key: str, saker_db: str, logg_db: str, sok_db: str,
                 notion_version: str = "2022-06-28", client: httpx.Client | None = None) -> None:
        self.api_key = api_key.strip()
        self.dbs = {"saker": saker_db.strip(), "logg": logg_db.strip(), "sok": sok_db.strip()}
        self.notion_version = notion_version
        self.client = client or httpx.Client(timeout=60)

    def configured(self) -> bool:
        return bool(self.api_key and all(self.dbs.values()))

    def _send(self, method: str, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """One Notion call, retried on rate limits, server errors and timeouts (both calls are idempotent)."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Notion-Version": self.notion_version}
        for attempt in range(1, 5):
            try:
                resp = self.client.request(method, url, headers=headers, json=body)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 4:
                    raise
            else:
                if resp.status_code not in RETRY_STATUS or attempt == 4:
                    resp.raise_for_status()
                    return resp.json()
            time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    def _query_all(self, database_id: str) -> list[dict[str, Any]]:
        url = f"{NOTION_BASE}/databases/{database_id}/query"
        body: dict[str, Any] = {"page_size": 100}
        pages: list[dict[str, Any]] = []
        while True:
            data = self._send("POST", url, body)
            pages.extend(data.get("results") or [])
            if not data.get("has_more"):
                return pages
            body["start_cursor"] = data.get("next_cursor")

    def load(self) -> dict[str, list[dict[str, str]]]:
        return {name: [_row(p) for p in self._query_all(db)] for name, db in self.dbs.items()}

    def set_status(self, page_id: str, status: str, note: str | None = None) -> None:
        """Sets the Status select of one Notion page (a search term), and its Notat when given."""
        properties: dict[str, Any] = {"Status": {"select": {"name": status}}}
        if note is not None:
            properties["Notat"] = {"rich_text": [{"text": {"content": note[:2000]}}]}
        self._send("PATCH", f"{NOTION_BASE}/pages/{page_id}", {"properties": properties})


def build_overview(data: dict[str, list[dict[str, str]]], today: date | None = None,
                   project: str = "", theme: str = "") -> dict[str, Any]:
    """Summarise the three databases, optionally for one project and/or theme.
    Pure function, so it is easy to test."""
    today = today or datetime.now(timezone.utc).date()
    all_saker, all_logg, sok = data.get("saker", []), data.get("logg", []), data.get("sok", [])

    def has(row: dict[str, str], field: str, value: str) -> bool:
        return not value or value in _tags(row, field)

    def published(row: dict[str, str]) -> date | None:
        return _parse_day(row.get("Publisert") or row.get("Journaldato") or row.get("Dato") or "")

    posts_30d: Counter = Counter()
    latest: dict[str, date] = {}  # newest journal post per case page (or «#case number»)
    for r in all_logg:
        keys = _log_case_ids(r) or (["#" + r["Saksnummer"]] if r.get("Saksnummer") else [])
        day = published(r)
        if (day or date.min) >= today - timedelta(days=30):
            posts_30d.update(keys)
        for key in keys if day else []:
            latest[key] = max(latest.get(key, day), day)
    # Each row of boxes is counted within the other filter, so «Utsira Nord» shows how many
    # of its cases fall under the chosen theme, and the other way round.
    projects = _facets([s for s in all_saker if has(s, THEME_FIELD, theme)], posts_30d, PROJECT_FIELD)
    themes = _facets([s for s in all_saker if has(s, PROJECT_FIELD, project)], posts_30d, THEME_FIELD)

    saker = [s for s in all_saker if has(s, PROJECT_FIELD, project) and has(s, THEME_FIELD, theme)]
    logg = all_logg
    if project or theme:
        ids = {s.get("_id") for s in saker}
        numbers = {s.get("Saksnummer") for s in saker if s.get("Saksnummer")}
        logg = [r for r in all_logg
                if (set(_log_case_ids(r)) & ids if _log_case_ids(r) else r.get("Saksnummer") in numbers)]
    case_names = {s.get("Saksnummer", ""): s.get("Name", "") for s in saker if s.get("Saksnummer")}
    case_urls = {s.get("Saksnummer", ""): s.get("URL", "") for s in saker if s.get("Saksnummer") and s.get("URL")}

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
        "filter": {"project": project, "theme": theme},
        "projects": projects,
        "themes": themes,
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
             "case_title": case_names.get(r.get("Saksnummer", ""), ""),
             "case_url": case_urls.get(r.get("Saksnummer", ""), ""), "from": r.get("Fra", ""),
             "to": r.get("Til", ""), "type": r.get("Journalposttype", ""),
             "published": str(published(r) or ""), "url": r.get("URL", "")}
            for r in recent[:60]
        ],
        # Every followed case in the selection, most recently active first
        "cases": [
            {"title": c.get("Name", ""), "case_number": c.get("Saksnummer", ""), "status": c.get("Status", ""),
             "url": c.get("URL", ""), "notion_url": c.get("_url", ""),
             "projects": [t for t in _tags(c, PROJECT_FIELD) if t != UNTAGGED],
             "themes": [t for t in _tags(c, THEME_FIELD) if t != UNTAGGED],
             "latest": str(_case_latest(latest, c) or ""), "journal_posts_30d": _case_posts(posts_30d, c)}
            for c in sorted((c for c in saker if c.get("Status") in FOLLOWED),
                            key=lambda c: (_case_latest(latest, c) or date.min, c.get("Saksnummer", "")), reverse=True)
        ],
        "most_active_cases": [
            {"case_number": num, "title": case_names.get(num, ""), "url": case_urls.get(num, ""), "journal_posts": n}
            for num, n in active.most_common(15)
        ],
        "top_senders": [{"name": name, "journal_posts": n} for name, n in senders.most_common(15)],
        "keywords": sorted(
            ({"query": k.get("Name", ""), "status": k.get("Status", ""), "note": k.get("Notat", ""),
              "last_run": k.get("Sist kjørt", ""), "notion_url": k.get("_url", ""), "id": k.get("_id", "")}
             for k in keywords),
            key=lambda k: (k["status"] != "Aktiv", k["query"].lower())),
        "keyword_suggestions": [
            {"query": k.get("Name", ""), "note": k.get("Notat", ""), "notion_url": k.get("_url", ""),
             "id": k.get("_id", "")}
            for k in keyword_suggestions
        ],
    }


class OverviewCache:
    """Keeps the overview for a while so page loads do not hit Notion every time."""

    def __init__(self, reader: EinnsynNotionReader, ttl_seconds: int = 1800) -> None:
        self.reader, self.ttl = reader, ttl_seconds
        self._value: dict[str, Any] | None = None
        self._data: dict[str, list[dict[str, str]]] = {}
        self._loaded_at = 0.0
        self._lock = threading.Lock()

    def get(self, refresh: bool = False, project: str = "", theme: str = "") -> dict[str, Any]:
        with self._lock:
            if refresh or self._value is None or time.time() - self._loaded_at > self.ttl:
                self._data = self.reader.load()
                overview = build_overview(self._data)
                overview["loaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                self._value, self._loaded_at = overview, time.time()
            if not (project or theme):
                return self._value
            filtered = build_overview(self._data, project=project, theme=theme)
            filtered["loaded_at"] = self._value["loaded_at"]
            return filtered

    def set_keyword_status(self, page_id: str, active: bool) -> str:
        """Turns a search term on (Aktiv) or off (Pause) in Notion and in the cached overview, so the
        page shows the change at once. Only pages in the search-term database can be changed."""
        status = "Aktiv" if active else "Pause"
        with self._lock:
            row = next((k for k in self._data.get("sok", []) if k.get("_id") == page_id), None)
            if row is None:
                raise KeyError(page_id)
            # An accepted suggestion loses its suggestion mark, so pausing it later keeps it a (paused) search term
            note = None
            if active and SUGGESTION_MARK in row.get("Notat", ""):
                note = (f"Tatt i bruk fra OWIS {datetime.now(timezone.utc).date().isoformat()}. "
                        + row["Notat"].replace(SUGGESTION_MARK, SUGGESTION_MARK.lower()))
            self.reader.set_status(page_id, status, note)
            row["Status"] = status
            if note is not None:
                row["Notat"] = note
            if self._value is not None:
                loaded_at = self._value.get("loaded_at")
                self._value = build_overview(self._data)
                self._value["loaded_at"] = loaded_at
        return status

    def sok(self) -> list[dict[str, str]]:
        """The search-term rows behind the current overview."""
        self.get()
        return self._data.get("sok", [])

    def saker(self) -> list[dict[str, str]]:
        """The case rows behind the current overview (loads them if needed)."""
        self.get()
        return self._data.get("saker", [])
