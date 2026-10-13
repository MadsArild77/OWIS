"""Stories about the same project, and same-day reports the AI calls follow-ups.

Event cards name each story's project. Stories naming the same project within
the window form a thread, shown with each story ("Same project"), so separate
events - one stake sale, then another - are seen together without being merged.
This uses the stored cards only; no AI calls.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from owis.core.storage.db import get_conn

THREAD_DAYS = 90
_GENERIC = re.compile(r"\b(offshore|onshore|wind|farm|park|project|prosjekt|vindpark|havvind|zone|area|site|phase|the|"
                      r"floating|flytende|solar|hybrid|battery|storage|portfolio|pipeline|tender|auction|round)\b")


def project_key(name: str | None) -> str:
    """'Five Estuaries offshore wind farm' and 'Five Estuaries' give the same key."""
    words = _GENERIC.sub(" ", re.sub(r"[^\w\s]", " ", str(name or "").lower()))
    key = " ".join(words.split())
    return key if len(key) >= 3 else ""


def _company_keys(names) -> set[str]:
    """Names plus initials, so 'CIP' meets 'Copenhagen Infrastructure Partners'."""
    keys = set()
    for name in names or []:
        words = re.findall(r"[a-z0-9]+", str(name).lower())
        if words:
            keys.add(" ".join(words))
            if len(words) > 1:
                keys.add("".join(w[0] for w in words))
    return keys


def _published(item: dict) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(item.get("published_at") or "").replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def same_action_reported_twice(item_a: dict, item_b: dict) -> bool:
    """Two reports within two days of the same kind of event, project and party.

    The AI sometimes reads a paywalled headline ("CIP buys into ...") as an earlier
    step of the full report ("CIP acquires stake ..."); a follow-up needs a new
    action, which rarely comes within two days under the same project and party.
    """
    card_a, card_b = item_a.get("event_card") or {}, item_b.get("event_card") or {}
    day_a, day_b = _published(item_a), _published(item_b)
    if not (card_a and card_b and day_a and day_b) or abs(day_a - day_b) > timedelta(days=2):
        return False
    key = project_key(card_a.get("project"))
    return (bool(key) and key == project_key(card_b.get("project"))
            and card_a.get("event_type") == card_b.get("event_type")
            and bool(_company_keys(card_a.get("companies")) & _company_keys(card_b.get("companies"))))


def thread_for(item_id: int) -> list[dict]:
    """Other stories naming the same project in the last THREAD_DAYS, one per merged story, newest first."""
    since = (datetime.now(timezone.utc) - timedelta(days=THREAD_DAYS)).isoformat()
    with get_conn() as conn:
        own = conn.execute("SELECT card_json FROM news_event_cards WHERE processed_id=?", (item_id,)).fetchone()
        if not own:
            return []
        key = project_key(json.loads(own["card_json"]).get("project"))
        if not key:
            return []
        group = conn.execute("SELECT collection_key FROM news_collection_overrides WHERE processed_id=?", (item_id,)).fetchone()
        rows = conn.execute('''SELECT p.id, p.title, r.source_name, r.article_url, r.published_at, e.card_json, o.collection_key
            FROM news_event_cards e JOIN news_processed_items p ON p.id = e.processed_id
            JOIN news_raw_items r ON r.id = p.raw_item_id
            LEFT JOIN news_collection_overrides o ON o.processed_id = p.id
            WHERE p.id != ? AND COALESCE(r.published_at, r.fetched_at) >= ?
            ORDER BY COALESCE(r.published_at, r.fetched_at) DESC''', (item_id, since)).fetchall()
    seen, out = {group["collection_key"]} if group and group["collection_key"] else set(), []
    for row in rows:
        if project_key(json.loads(row["card_json"]).get("project")) != key:
            continue
        story = row["collection_key"] or f"item:{row['id']}"
        if story in seen:
            continue
        seen.add(story)
        out.append({k: row[k] for k in ("id", "title", "source_name", "article_url", "published_at")})
    return out
