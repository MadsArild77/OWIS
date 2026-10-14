"""Publication times for articles found by scraping a front page.

Scraping only sees a link and a headline, so those articles were stored without a
publication time. Without one they fall outside the morning report's 24-hour window
and sort badly. The article page itself states the time; it is read once, when the
article is first stored, and articles stored earlier without one are filled in a few
per run.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from owis.core.storage.db import get_conn

logger = logging.getLogger(__name__)
BACKFILL_PER_RUN = 20


def _known(urls: list[str]) -> set[str]:
    if not urls:
        return set()
    marks = ",".join("?" * len(urls))
    with get_conn() as conn:
        return {r[0] for r in conn.execute(f"SELECT article_url FROM news_raw_items WHERE article_url IN ({marks})", urls)} | \
               {r[0] for r in conn.execute(f"SELECT article_url FROM news_article_archive WHERE article_url IN ({marks})", urls)}


def fill_new(items: list[dict], preview) -> int:
    """Read the publication time (and lead and image, when missing) of new undated articles."""
    undated = [i for i in items if not i.get("published_at")]
    known = _known([i["article_url"] for i in undated])
    filled = 0
    for item in undated:
        if item["article_url"] in known:
            continue
        page = preview(item["article_url"], item.get("title_raw", ""), item.get("summary_raw", ""))
        if page.get("published_at"):
            item["published_at"] = page["published_at"]
            filled += 1
        if not item.get("summary_raw") and page.get("description"):
            item["summary_raw"] = page["description"][:500]
        if not item.get("image_url") and page.get("image_url"):
            item["image_url"] = page["image_url"]
    return filled


def backfill(preview, limit: int = BACKFILL_PER_RUN) -> int:
    """Fill the publication time of recently stored articles never checked for one."""
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    with get_conn() as conn:
        rows = conn.execute('''SELECT id, article_url, title_raw FROM news_raw_items
            WHERE published_at IS NULL AND fetched_at >= ?
            ORDER BY fetched_at DESC LIMIT ?''', (since, limit)).fetchall()
    filled = 0
    for row in rows:
        page = preview(row["article_url"], row["title_raw"], "")
        with get_conn() as conn:  # '' marks a page checked without a stated time, so it is not read again
            conn.execute("UPDATE news_raw_items SET published_at=? WHERE id=?", (page.get("published_at") or "", row["id"]))
        filled += bool(page.get("published_at"))
    return filled
