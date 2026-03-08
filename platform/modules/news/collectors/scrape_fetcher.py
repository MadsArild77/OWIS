from datetime import datetime, timezone
import hashlib
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

from platform.modules.news.registry.source_discovery import load_source_registry


def _looks_like_article(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in ["/news", "/article", "offshore", "wind", "202", "2026"])


def fetch_scrape_items(limit_per_source: int = 20) -> list[dict]:
    items: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for source in load_source_registry():
        if not source.get("enabled") or source.get("type") != "scrape":
            continue

        homepage = source.get("homepage") or source.get("url")
        if not homepage:
            continue

        try:
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                response = client.get(homepage)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            continue

        domain = urlparse(homepage).netloc
        collected = 0
        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            title = anchor.get_text(" ", strip=True)
            if not href or not title:
                continue

            url = urljoin(homepage, href)
            if urlparse(url).netloc and urlparse(url).netloc != domain:
                continue
            if not _looks_like_article(url):
                continue

            content_hash = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
            items.append(
                {
                    "source_name": source["name"],
                    "article_url": url,
                    "title_raw": title,
                    "summary_raw": "",
                    "content_raw": title,
                    "content_hash": content_hash,
                    "published_at": None,
                    "fetched_at": now,
                }
            )
            collected += 1
            if collected >= limit_per_source:
                break

    return items
