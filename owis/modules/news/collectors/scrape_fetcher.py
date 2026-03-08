from datetime import datetime, timezone
import hashlib
import os
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

from owis.modules.news.collectors.filters import is_probable_news_item
from owis.modules.news.registry.source_discovery import load_source_registry


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _resolve_auth_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        env_key = value.get("env")
        if env_key:
            return os.getenv(str(env_key), "").strip()
        raw = value.get("value")
        if raw is not None:
            return str(raw).strip()
    return ""


def _build_request_auth(source: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], bool]:
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    cookies: dict[str, str] = {}
    auth_cfg = source.get("auth") or {}
    configured = False

    if not isinstance(auth_cfg, dict):
        return headers, cookies, configured

    for header_name, raw_value in (auth_cfg.get("headers") or {}).items():
        resolved = _resolve_auth_value(raw_value)
        if header_name and resolved:
            headers[str(header_name)] = resolved
            configured = True

    for cookie_name, raw_value in (auth_cfg.get("cookies") or {}).items():
        resolved = _resolve_auth_value(raw_value)
        if cookie_name and resolved:
            cookies[str(cookie_name)] = resolved
            configured = True

    legacy_header_name = auth_cfg.get("header_name")
    legacy_header_env = auth_cfg.get("header_env")
    if legacy_header_name and legacy_header_env:
        resolved = os.getenv(str(legacy_header_env), "").strip()
        if resolved:
            headers[str(legacy_header_name)] = resolved
            configured = True

    legacy_cookie_name = auth_cfg.get("cookie_name")
    legacy_cookie_env = auth_cfg.get("cookie_env")
    if legacy_cookie_name and legacy_cookie_env:
        resolved = os.getenv(str(legacy_cookie_env), "").strip()
        if resolved:
            cookies[str(legacy_cookie_name)] = resolved
            configured = True

    return headers, cookies, configured


def _extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Prefer article/main area over full page to avoid nav/footer noise.
    container = soup.find("article") or soup.find("main") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = " ".join([p for p in paragraphs if p])

    return " ".join(text.split())[:5000]


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
        source_headers, source_cookies, auth_configured = _build_request_auth(source)
        try:
            with httpx.Client(
                timeout=20,
                follow_redirects=True,
                headers=source_headers,
                cookies=source_cookies or None,
            ) as client:
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

                    article_text = ""
                    try:
                        page_resp = client.get(url)
                        page_resp.raise_for_status()
                        article_text = _extract_article_text(page_resp.text)
                    except Exception:
                        filtered_count += 1
                        continue

                    if not is_probable_news_item(url=url, title=title, summary="", full_text=article_text):
                        filtered_count += 1
                        continue

                    content_hash = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
                    items.append(
                        {
                            "source_name": src_name,
                            "article_url": url,
                            "title_raw": title,
                            "summary_raw": article_text[:500],
                            "content_raw": article_text,
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
                "auth_configured": auth_configured,
                "status": "ok" if error is None else "error",
                "error": error,
            }
        )

    return items, report


def fetch_scrape_items(limit_per_source: int = 20) -> list[dict]:
    items, _ = fetch_scrape_items_with_report(limit_per_source=limit_per_source)
    return items
