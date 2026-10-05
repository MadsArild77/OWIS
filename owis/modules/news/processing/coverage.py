"""Find other outlets' coverage of important stories that only one of our sources carries.

After each fetch, a few high-scoring single-source stories get one web search
(Tavily or Brave). Results are kept only when the AI judges them the same event
as the story's event card. They appear as "Also covered by" and feed the source
advisor, which recommends websites that keep turning up. Bounded per run and per day.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone

from owis.core.llm.client import AIClient
from owis.core.storage.db import get_conn

logger = logging.getLogger(__name__)
MIN_SCORE = 70


def _limit(name: str, default: str) -> int:
    try:
        return max(0, int(os.getenv(name, default)))
    except ValueError:
        return int(default)


def _query(item: dict) -> str:
    card = item.get("event_card") or {}
    text = card.get("what_happened") or item.get("title") or ""
    return re.sub(r"^\[paywalled\]\s*|\s*\(\+\)\s*$", "", str(text), flags=re.I).strip()[:300]


def gap_candidates(days: int = 3) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute('''SELECT p.*, r.source_name, r.article_url, r.published_at FROM news_processed_items p
            JOIN news_raw_items r ON r.id = p.raw_item_id
            LEFT JOIN news_domain_classification d ON d.processed_id = p.id
            LEFT JOIN news_coverage_searches s ON s.raw_id = r.id
            WHERE COALESCE(r.published_at, r.fetched_at) >= ? AND p.signal_score >= ? AND s.raw_id IS NULL
              AND COALESCE(d.domain_bucket, 'other_energy') IN ('offshore_wind', 'adjacent_energy')
              AND p.id NOT IN (SELECT o.processed_id FROM news_collection_overrides o
                               WHERE (SELECT COUNT(*) FROM news_collection_overrides x WHERE x.collection_key = o.collection_key) > 1)
            ORDER BY p.signal_score DESC, r.published_at DESC''', (since, MIN_SCORE)).fetchall()
    return [dict(r) for r in rows]


def fill_coverage_gaps() -> dict:
    if not (os.getenv("TAVILY_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY")):
        return {"skipped": "no search provider configured"}
    ai = AIClient()
    if not ai.enabled:
        return {"skipped": "AI is not enabled"}
    from owis.modules.news.matching.service import judge_pair
    from owis.modules.news.processing.event_cards import attach_cards
    from owis.modules.news.processing.research import search
    from owis.modules.news.registry.source_advisor import host_of
    from owis.modules.news.storage.evidence import save

    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    with get_conn() as conn:
        used_today = conn.execute("SELECT COUNT(*) FROM news_coverage_searches WHERE searched_at >= ?", (start_of_day,)).fetchone()[0]
        collected = {r[0] for r in conn.execute("SELECT article_url FROM news_raw_items")}
    budget = min(_limit("OWI_GAP_SEARCHES_PER_RUN", "5"), _limit("OWI_GAP_SEARCHES_PER_DAY", "25") - used_today)
    searched = found = 0
    for item in attach_cards(gap_candidates())[:max(budget, 0)]:
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO news_coverage_searches(raw_id, searched_at, found) VALUES(?,?,0)",
                         (item["raw_item_id"], now))
        searched += 1
        try:
            results = search(_query(item))
        except Exception:
            logger.exception("Coverage search failed for article %s", item["id"])
            continue
        own_host = host_of(item.get("article_url", ""))
        hits = 0
        for i, row in enumerate(results[:5]):
            url = str(row.get("url") or "")
            if not url or url in collected or host_of(url) == own_host:
                continue
            other = {"id": 2147480000 + i, "title": row.get("title", ""), "cleaned_text": row.get("description", ""),
                     "published_at": None}
            judgement = judge_pair(ai, item, other, 0)
            if judgement.get("relationship") == "same_event" and float(judgement.get("confidence") or 0) >= 0.8:
                save(item["raw_item_id"], url, row.get("title") or url, host_of(url), "unknown", "additional_coverage",
                     row.get("description") or "", suggest=True)
                hits += 1
        with get_conn() as conn:
            conn.execute("UPDATE news_coverage_searches SET found=? WHERE raw_id=?", (hits, item["raw_item_id"]))
        found += hits
    return {"searched": searched, "found": found}
