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


CASE_GAP_DAYS = 7
# Unlike project names, a topic's "tender" or "auction" carries meaning; only filler goes.
_STOP = {"of", "and", "for", "in", "on", "to", "a", "an", "the", "news", "update", "plans", "plan",
         "offshore", "onshore", "wind", "farm", "project"}


def topic_tokens(topic: str | None) -> set[str]:
    """Content words of an event card's topic."""
    return {w for w in re.sub(r"[^\w\s]", " ", str(topic or "").lower()).split() if w not in _STOP and len(w) > 2}


def same_topic(a: str | None, b: str | None) -> bool:
    """'German offshore wind tender reform' and 'German tender changes' share the matter."""
    ta, tb = topic_tokens(a), topic_tokens(b)
    shared = ta & tb
    return len(shared) >= 2 and len(shared) / len(ta | tb) >= 0.4


def _common(values: list[str]) -> str:
    values = [v.strip() for v in values if v and v.strip()]
    return max(set(values), key=lambda v: (values.count(v), -len(v))) if values else ""


def assign_cases(collections: list[dict]) -> list[dict]:
    """Give each story (merged event) a case: stories on the same project or topic, or linked as
    follow-ups, belong together while each new development comes within CASE_GAP_DAYS of the
    previous one. Adds collection["case"] = {key, name, size, signature}; a story that shares
    nothing keeps a case of its own (size 1)."""
    from owis.modules.news.processing.event_cards import stored_cards
    item_ids = [int(i["id"]) for col in collections for i in col.get("items") or []]
    cards = stored_cards(item_ids)
    with get_conn() as conn:
        links = [(r[0], r[1]) for r in conn.execute("SELECT item_a_id, item_b_id FROM news_story_links")]
    owner = {int(i["id"]): col["collection_key"] for col in collections for i in col.get("items") or []}
    parent = {col["collection_key"]: col["collection_key"] for col in collections}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        parent[find(a)] = find(b)

    for a, b in links:
        if a in owner and b in owner:
            union(owner[a], owner[b])

    facts = {}
    for col in collections:
        col_cards = [cards[int(i["id"])] for i in col.get("items") or [] if int(i["id"]) in cards]
        projects = [str(c.get("project") or "") for c in col_cards]
        facts[col["collection_key"]] = {
            "project": _common([project_key(p) for p in projects if project_key(p)]),
            "project_names": [p for p in projects if project_key(p)],
            "topic": _common([str(c.get("topic") or "") for c in col_cards]),
            "when": col.get("latest_published_at"),
        }
    ordered = sorted(collections, key=lambda c: str(c.get("latest_published_at") or ""))
    for i, left in enumerate(ordered):
        fl = facts[left["collection_key"]]
        if not (fl["project"] or fl["topic"]):
            continue
        for right in ordered[i + 1:]:
            gap = _gap_days(fl["when"], right.get("latest_published_at"))
            if gap is None or gap > CASE_GAP_DAYS:
                break
            fr = facts[right["collection_key"]]
            if (fl["project"] and fl["project"] == fr["project"]) or same_topic(fl["topic"], fr["topic"]):
                union(left["collection_key"], right["collection_key"])

    members: dict[str, list[dict]] = {}
    for col in collections:
        members.setdefault(find(col["collection_key"]), []).append(col)
    for root, group in members.items():
        group_facts = [facts[c["collection_key"]] for c in group]
        names = [n for f in group_facts for n in f["project_names"]]
        name = (min(names, key=len) if names else _common([f["topic"] for f in group_facts])) if len(group) > 1 else ""
        ids = sorted(int(i["id"]) for c in group for i in c.get("items") or [])
        for col in group:
            col["case"] = {"key": f"case:{root}", "size": len(group), "name": name,
                           "signature": ",".join(map(str, ids))}
    return collections


def _gap_days(a, b) -> float | None:
    try:
        first = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        second = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
    except ValueError:
        return None
    if not first.tzinfo:
        first = first.replace(tzinfo=timezone.utc)
    if not second.tzinfo:
        second = second.replace(tzinfo=timezone.utc)
    return abs((second - first).total_seconds()) / 86400
