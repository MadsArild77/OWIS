"""Self-learning source quality and recommendations.

Each source's weight in the signal score is learned from what it actually delivers
over the last 30 days: the share of offshore wind and related stories, plus the
reader's own relevance feedback. The prior (trade-press credibility) dominates
until a source has enough articles, so one odd week does not swing it.

Recommendations to add come from websites that keep supplying verified coverage
of relevant stories (open versions of paywalled stories, research sources).
Recommendations to pause come from sources that are mostly off-focus, failing or
silent. Adding and removing is always the reader's decision.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from owis.core.storage.db import get_conn
from owis.modules.news.processing import signal

WINDOW_DAYS = 30
PRIOR_STRENGTH = 25          # articles needed before observed quality outweighs the prior
MIN_ARTICLES_TO_JUDGE = 20   # before recommending a pause for being off-focus
OFF_FOCUS_SHARE = 0.4        # below this share of offshore wind + related: recommend pause
MIN_STORIES_TO_ADD = 2       # distinct relevant stories before a website is recommended
IGNORED_HOSTS = {
    "google.com", "news.google.com", "linkedin.com", "youtube.com", "x.com", "twitter.com", "facebook.com",
    "wikipedia.org", "en.wikipedia.org", "no.wikipedia.org", "reddit.com", "medium.com", "t.co",
}


def host_of(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _since(days: int = WINDOW_DAYS) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _registry() -> list[dict]:
    from owis.modules.news.registry.source_discovery import load_source_registry
    return [{"index": i, **s} for i, s in enumerate(load_source_registry())]


def learned_weight(prior: int, articles: int, offshore_share: float, focus_share: float,
                   positive: int = 0, negative: int = 0) -> int:
    """Blend the credibility prior with observed relevance (0-10 scale)."""
    quality = 0.5 * offshore_share + 0.5 * focus_share
    if positive + negative >= 3:
        quality = 0.7 * quality + 0.3 * ((positive + 1) / (positive + negative + 2))
    observed = 10 * quality
    weight = (PRIOR_STRENGTH * prior + articles * observed) / (PRIOR_STRENGTH + articles)
    return int(max(2, min(10, round(weight))))


def source_scorecard(days: int = WINDOW_DAYS) -> list[dict]:
    since = _since(days)
    with get_conn() as conn:
        rows = conn.execute('''SELECT r.source_name, d.domain_bucket, p.signal_score
            FROM news_processed_items p JOIN news_raw_items r ON r.id = p.raw_item_id
            LEFT JOIN news_domain_classification d ON d.processed_id = p.id
            WHERE COALESCE(r.published_at, r.fetched_at) >= ?''', (since,)).fetchall()
        feedback = conn.execute('''SELECT r.source_name, e.value FROM news_editorial_state s
            JOIN news_editorial_events e ON e.id = s.event_id AND e.undone = 0
            JOIN news_processed_items p ON p.id = s.processed_id JOIN news_raw_items r ON r.id = p.raw_item_id
            WHERE e.value IN ('relevant', 'non_relevant')''').fetchall()
        legacy = conn.execute('''SELECT r.source_name, v.relevance FROM news_item_relevance v
            JOIN news_processed_items p ON p.id = v.processed_id JOIN news_raw_items r ON r.id = p.raw_item_id''').fetchall()
        health = {r["source_name"]: dict(r) for r in conn.execute("SELECT * FROM source_fetch_health")}
    stats = defaultdict(lambda: {"articles": 0, "offshore": 0, "focus": 0, "strong": 0, "positive": 0, "negative": 0})
    for row in rows:
        s = stats[row["source_name"]]
        s["articles"] += 1
        bucket = row["domain_bucket"] or "other_energy"
        s["offshore"] += bucket == "offshore_wind"
        s["focus"] += bucket in {"offshore_wind", "adjacent_energy"}
        s["strong"] += int(row["signal_score"] or 0) >= 70
    for row in feedback:
        stats[row["source_name"]]["positive" if row["value"] == "relevant" else "negative"] += 1
    for row in legacy:
        stats[row["source_name"]]["positive" if int(row["relevance"]) == 1 else "negative"] += 1

    card = []
    for source in _registry():
        name = source.get("name") or ""
        s = stats.get(name, stats.default_factory())
        n = s["articles"]
        offshore_share = s["offshore"] / n if n else 0.0
        focus_share = s["focus"] / n if n else 0.0
        prior = signal.source_weight(name, learned=False)
        h = health.get(name) or {}
        card.append({
            "index": source["index"], "name": name, "enabled": bool(source.get("enabled", True)),
            "homepage": source.get("homepage") or source.get("url") or "", "type": source.get("type") or "",
            "articles": n, "offshore_share": round(offshore_share, 2), "focus_share": round(focus_share, 2),
            "strong_signals": s["strong"], "positive_feedback": s["positive"], "negative_feedback": s["negative"],
            "prior_weight": prior,
            "learned_weight": learned_weight(prior, n, offshore_share, focus_share, s["positive"], s["negative"]) if n else prior,
            "health": h.get("health_color") or "gray", "last_error": h.get("last_error") or "",
            "health_updated_at": h.get("updated_at") or "",
        })
    return card


def refresh_learned_weights() -> dict[str, int]:
    """Recompute and store learned weights; the scorer reads them for new articles."""
    card = source_scorecard()
    weights = {row["name"]: row["learned_weight"] for row in card if row["articles"]}
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO news_registry_meta(key, value) VALUES('learned_source_weights', ?)",
                     (json.dumps(weights, ensure_ascii=False),))
    signal.set_learned_source_weights(weights)
    return weights


def load_learned_weights() -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM news_registry_meta WHERE key='learned_source_weights'").fetchone()
    signal.set_learned_source_weights(json.loads(row["value"]) if row else {})


def _decisions() -> dict[str, str]:
    with get_conn() as conn:
        return {r["key"]: r["decision"] for r in conn.execute("SELECT key, decision FROM news_source_advice_decisions")}


def record_decision(key: str, decision: str) -> None:
    if decision not in {"dismissed", "kept", "added", "paused"}:
        raise ValueError("Unknown decision")
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO news_source_advice_decisions(key, decision, decided_at) VALUES(?,?,?)",
                     (key, decision, datetime.now(timezone.utc).isoformat()))


def removal_recommendations(card: list[dict]) -> list[dict]:
    decisions = _decisions()
    out = []
    for row in card:
        if not row["enabled"] or decisions.get(f"remove:{row['name']}") == "kept":
            continue
        reason = None
        if row["health"] == "red" and row["last_error"]:
            reason = f"Fetching fails: {row['last_error'][:140]}"
        elif row["articles"] >= MIN_ARTICLES_TO_JUDGE and row["focus_share"] < OFF_FOCUS_SHARE:
            reason = (f"Mostly outside your focus: only {round(row['focus_share'] * 100)} % of its "
                      f"{row['articles']} articles in {WINDOW_DAYS} days are offshore wind or related.")
        elif row["articles"] == 0 and row["health"] != "red":
            reason = f"No articles in the last {WINDOW_DAYS} days."
        if reason:
            out.append({**row, "key": f"remove:{row['name']}", "reason": reason})
    return out


def addition_recommendations(card: list[dict]) -> list[dict]:
    known = {host_of(row["homepage"]) for row in card} | {host_of(s.get("url", "")) for s in _registry()}
    known.discard("")
    decisions = _decisions()
    since = _since()
    candidates: dict[str, dict] = {}

    def note(url: str, title: str, story_id, origin: str):
        host = host_of(url)
        if not host or host in known or host in IGNORED_HOSTS or any(host.endswith("." + k) for k in known):
            return
        if decisions.get(f"add:{host}") in {"dismissed", "added"}:
            return
        c = candidates.setdefault(host, {"host": host, "stories": set(), "examples": [], "origins": set()})
        c["stories"].add(story_id)
        c["origins"].add(origin)
        if len(c["examples"]) < 3 and url not in [e["url"] for e in c["examples"]]:
            c["examples"].append({"url": url, "title": title or url})

    with get_conn() as conn:
        for r in conn.execute('''SELECT raw_id, url, title FROM news_source_evidence
                WHERE basis = 'alternative_fulltext' AND checked_at >= ?''', (since,)):
            note(r["url"], r["title"], ("raw", r["raw_id"]), "Open version of a paywalled story")
        for r in conn.execute('''SELECT processed_id, result_json FROM news_story_research
                WHERE status = 'completed' AND completed_at >= ?''', (since,)):
            try:
                sources = (json.loads(r["result_json"] or "{}") or {}).get("sources") or []
            except ValueError:
                continue
            for s in sources:
                if s.get("relationship") in {"same_event", "update", "background"}:
                    note(s.get("url", ""), s.get("title", ""), ("research", r["processed_id"]), "Source in story research")

    out = []
    for c in candidates.values():
        count = len(c["stories"])
        if count < MIN_STORIES_TO_ADD:
            continue
        out.append({"key": f"add:{c['host']}", "host": c["host"], "name": _name_from_host(c["host"]),
                    "stories": count, "origins": sorted(c["origins"]), "examples": c["examples"],
                    "reason": f"Supplied relevant coverage for {count} of your stories in the last {WINDOW_DAYS} days."})
    return sorted(out, key=lambda x: -x["stories"])


def _name_from_host(host: str) -> str:
    base = host.split(".")[-2] if host.count(".") >= 1 else host
    return base.replace("-", " ").title()


def advice() -> dict:
    card = source_scorecard()
    refresh_learned_weights()
    return {"scorecard": sorted(card, key=lambda r: (-r["learned_weight"], r["name"])),
            "remove": removal_recommendations(card), "add": addition_recommendations(card),
            "window_days": WINDOW_DAYS, "generated_at": datetime.now(timezone.utc).isoformat()}
