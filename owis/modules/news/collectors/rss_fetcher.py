from datetime import datetime, timezone
import hashlib
from typing import Any

import feedparser

from owis.modules.news.collectors.filters import is_probable_news_item
from owis.modules.news.registry.source_discovery import load_source_registry


USER_AGENT = "OWISBot/1.0 (+https://github.com/MadsArild77/OWIS)"


def load_sources() -> list[dict[str, Any]]:
    return [s for s in load_source_registry() if s.get("enabled")]


def fetch_rss_items_with_report() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for source in load_sources():
        if source.get("type") != "rss":
            continue

        src_name = source.get("name", "unknown")
        src_url = source.get("url", "")
        source_count = 0
        filtered_count = 0
        error = None

        try:
            feed = feedparser.parse(src_url, request_headers={"User-Agent": USER_AGENT})
            for entry in getattr(feed, "entries", []):
                url = entry.get("link") or ""
                title = (entry.get("title") or "").strip()
                summary = (entry.get("summary") or "").strip()

                if not is_probable_news_item(url=url, title=title, summary=summary):
                    filtered_count += 1
                    continue

                content_hash = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()

                items.append(
                    {
                        "source_name": src_name,
                        "article_url": url,
                        "title_raw": title,
                        "summary_raw": summary,
                        "content_raw": summary,
                        "content_hash": content_hash,
                        "published_at": entry.get("published"),
                        "fetched_at": now,
                    }
                )
                source_count += 1
        except Exception as ex:
            error = str(ex)

        report.append(
            {
                "source": src_name,
                "type": "rss",
                "url": src_url,
                "items": source_count,
                "filtered": filtered_count,
                "status": "ok" if error is None else "error",
                "error": error,
            }
        )

    return items, report


def fetch_rss_items() -> list[dict[str, Any]]:
    items, _ = fetch_rss_items_with_report()
    return items
