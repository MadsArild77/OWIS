from datetime import datetime, timezone
import hashlib
from typing import Any

import feedparser

from owis.modules.news.registry.source_discovery import load_source_registry


def load_sources() -> list[dict[str, Any]]:
    return [s for s in load_source_registry() if s.get("enabled")]


def fetch_rss_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for source in load_sources():
        if source.get("type") != "rss":
            continue

        feed = feedparser.parse(source["url"])
        for entry in getattr(feed, "entries", []):
            url = entry.get("link") or ""
            if not url:
                continue
            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or "").strip()
            content = summary
            content_hash = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()

            items.append(
                {
                    "source_name": source["name"],
                    "article_url": url,
                    "title_raw": title,
                    "summary_raw": summary,
                    "content_raw": content,
                    "content_hash": content_hash,
                    "published_at": entry.get("published"),
                    "fetched_at": now,
                }
            )

    return items

