from datetime import datetime, timezone
import hashlib
from typing import Any

import feedparser
import yaml

from platform.core.config.settings import NEWS_SOURCES_PATH


def load_sources() -> list[dict[str, Any]]:
    with open(NEWS_SOURCES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [s for s in data.get("sources", []) if s.get("enabled")]


def fetch_rss_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for source in load_sources():
        if source.get("type") != "rss":
            continue

        feed = feedparser.parse(source["url"])
        for entry in feed.entries:
            url = entry.get("link") or ""
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
