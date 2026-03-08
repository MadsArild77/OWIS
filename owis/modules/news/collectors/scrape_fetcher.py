from datetime import datetime, timezone
import hashlib
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

from owis.modules.news.collectors.filters import is_probable_news_item
from owis.modules.news.registry.source_discovery import load_source_registry


USER_AGENT = "OWISBot/1.0 (+https://github.com/MadsArild77/OWIS)"


def fetch_scrape_items_with_report(limit_per_source: int = 20) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    report: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for source in load_source_registry():
        if not source.get("enabled") or source.get("type") != "scrape":
            continue

        src_name = source.get("name", "unknown")
        homepage = source.get("homepage") or source.get("url")
        if not homepage:
            report.append({"source": src_name, "type": "scrape", "url": "", "items": 0, "filtered": 0, "status": "error", "error": "missing_homepage"})
            continue

        source_count = 0
        filtered_count = 0
        error = None
        try:
            with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(homepage)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

            domain = urlparse(homepage).netloc
            for anchor in soup.select("a[href]"):
                href = (anchor.get("href") or "").strip()
                title = anchor.get_text(" ", strip=True)
                if not href or not title:
                    continue

                url = urljoin(homepage, href)
                if urlparse(url).netloc and urlparse(url).netloc != domain:
                    continue
                if not is_probable_news_item(url=url, title=title, summary=""):
                    filtered_count += 1
                    continue

                content_hash = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
                items.append(
                    {
                        "source_name": src_name,
                        "article_url": url,
                        "title_raw": title,
                        "summary_raw": "",
                        "content_raw": title,
                        "content_hash": content_hash,
                        "published_at": None,
                        "fetched_at": now,
                    }
                )
                source_count += 1
                if source_count >= limit_per_source:
                    break
        except Exception as ex:
            error = str(ex)

        report.append(
            {
                "source": src_name,
                "type": "scrape",
                "url": homepage,
                "items": source_count,
                "filtered": filtered_count,
                "status": "ok" if error is None else "error",
                "error": error,
            }
        )

    return items, report


def fetch_scrape_items(limit_per_source: int = 20) -> list[dict]:
    items, _ = fetch_scrape_items_with_report(limit_per_source=limit_per_source)
    return items
