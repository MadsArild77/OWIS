"""Links between eInnsyn cases and news stories, via the projects and companies they name.

News event cards name each story's project and companies (news.processing.event_cards).
An eInnsyn case is linked to a story when its title or journal posts mention one of
them. Generic words are removed the same way the news threads do (threads.project_key),
and single-word company names are left out, so «Equinor» alone links nothing.
No AI calls.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from owis.core.storage.db import get_conn
from owis.modules.news.processing.threads import project_key

NEWS_DAYS = 180
_FOLD = str.maketrans({"ø": "o", "å": "a", "æ": "ae", "ö": "o", "ä": "a", "é": "e", "ü": "u"})
_SUFFIX = re.compile(r"\b(as|asa|da|sf|ab|a s|ltd|limited|plc|gmbh|bv|nv|inc|llc)\b")


def fold(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", str(text or "").lower().translate(_FOLD)).split())


def keys_for_card(card: dict) -> set[str]:
    keys = set()
    for name in [card.get("project")]:
        key = fold(project_key(name))
        if len(key) >= 5:
            keys.add(key)
    for company in card.get("companies") or []:
        key = " ".join(_SUFFIX.sub(" ", fold(company)).split())
        if len(key.split()) >= 2 and len(key) >= 6:
            keys.add(key)
    return keys


def _contains(haystack: str, key: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(key)}(?!\w)", haystack) is not None


def recent_cards() -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=NEWS_DAYS)).isoformat()
    with get_conn() as conn:
        rows = conn.execute('''SELECT c.processed_id, c.card_json, p.title, r.article_url, r.source_name, r.published_at
            FROM news_event_cards c JOIN news_processed_items p ON p.id = c.processed_id
            JOIN news_raw_items r ON r.id = p.raw_item_id
            WHERE COALESCE(r.published_at, p.processed_at) >= ? ORDER BY r.published_at DESC''', (since,)).fetchall()
    out = []
    for r in rows:
        try:
            card = json.loads(r["card_json"])
        except ValueError:
            continue
        keys = keys_for_card(card)
        if keys:
            out.append({"id": r["processed_id"], "title": r["title"], "url": r["article_url"], "source": r["source_name"],
                        "published": str(r["published_at"] or "")[:10], "keys": keys})
    return out


def news_for_case(case: dict, limit: int = 8) -> list[dict]:
    """News stories naming a project or company that this case mentions, newest first."""
    text = fold(" ".join([case.get("title", "")] + [p.get("title", "") + " " + p.get("from", "") + " " + p.get("to", "")
                                                     for p in case.get("journal_posts") or []]))
    found, seen = [], set()
    for item in recent_cards():
        matched = sorted(k for k in item["keys"] if _contains(text, k))
        if matched and item["title"] not in seen:
            seen.add(item["title"])
            found.append({k: item[k] for k in ("id", "title", "url", "source", "published")} | {"matched_on": matched})
        if len(found) >= limit:
            break
    return found


def cases_for_news(item_ids: list[int], saker: list[dict], limit: int = 8) -> list[dict]:
    """eInnsyn cases (rows from the Notion cache) mentioning the projects or companies of these news items."""
    from owis.modules.news.processing.event_cards import stored_cards
    keys = set().union(*[keys_for_card(c) for c in stored_cards(item_ids).values()] or [set()])
    if not keys:
        return []
    found = []
    for row in saker:
        if row.get("Status") in ("Ikke relevant", "Arkivert"):
            continue
        matched = sorted(k for k in keys if _contains(fold(row.get("Name", "")), k))
        if matched:
            found.append({"title": row.get("Name", ""), "case_number": row.get("Saksnummer", ""),
                          "status": row.get("Status", ""), "url": row.get("URL", ""), "matched_on": matched})
    found.sort(key=lambda r: (r["status"] != "Aktiv", r["case_number"]), reverse=False)
    return found[:limit]
