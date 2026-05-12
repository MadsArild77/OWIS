from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

from owis.modules.news.collectors.filters import is_probable_article_url, is_probable_news_item
from owis.modules.news.registry.source_discovery import load_source_registry


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
PAYWALL_MARKERS = ["subscribe", "subscriber", "subscription", "sign in", "log in", "paywall", "abonner", "abonnement"]
BOILERPLATE_MARKERS = [
    "vær varsom-plakaten",
    "vaer varsom-plakaten",
    "redaktørplakaten",
    "redaktorplakaten",
    "copyright ©",
    "copyright ",
    "alt materiale på denne siden er omfattet",
    "prøv energiwatch gratis",
    "få tilbud på et abonnement",
    "arbeider etter vær varsom-plakatens regler",
]
BOILERPLATE_MARKERS.extend(
    [
        "vær i forkant av utviklingen",
        "varsler er en tjeneste for våre abonnenter",
        "vennligst logg inn eller opprett bruker",
        "få informasjon om det siste fra bransjen med vårt nyhetsbrev",
        "med vårt nyhetsbrev",
        "jurist (rådgivar/seniorrådgivar)",
        "debattinnlegget er utelukkende et uttrykk for skribentens egen mening",
    ]
)


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
    paragraphs = _extract_paragraphs(soup)
    text = " ".join([p for p in paragraphs if p])

    return " ".join(text.split())[:5000]


def _extract_paragraphs(soup: BeautifulSoup) -> list[str]:
    # Prefer article/main area over full page to avoid nav/footer noise.
    container = soup.find("article") or soup.find("main") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if not _looks_like_boilerplate(p)]
    text = " ".join([p for p in paragraphs if p])
    if text.strip():
        return paragraphs

    return [
        p.get_text(" ", strip=True)
        for p in soup.find_all("p")
        if not _looks_like_boilerplate(p.get_text(" ", strip=True))
    ]


def _looks_like_boilerplate(text: str) -> bool:
    cleaned = _clean_text(text).lower()
    if not cleaned:
        return True
    if len(cleaned) < 40:
        return False
    if any(marker in cleaned for marker in BOILERPLATE_MARKERS):
        return True

    subscription_terms = ["abonnent", "abonnement", "logg inn", "opprett bruker", "nyhetsbrev"]
    if sum(1 for term in subscription_terms if term in cleaned) >= 2:
        return True

    if "debattinnlegget" in cleaned and "egen mening" in cleaned:
        return True

    return False


def _clean_text(value: Any) -> str:
    return " ".join(unescape(str(value or "")).split()).strip()


def _get_meta_content(soup: BeautifulSoup, key: str) -> str:
    if not key:
        return ""

    for attr in ("property", "name", "itemprop"):
        tag = soup.find("meta", attrs={attr: key})
        content = _clean_text(tag.get("content")) if tag else ""
        if content:
            return content
    return ""


def _find_json_ld_objects(soup: BeautifulSoup) -> list[Any]:
    objects: list[Any] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            objects.append(json.loads(raw))
        except Exception:
            continue
    return objects


def _flatten_json_ld(value: Any, bucket: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    out = bucket if bucket is not None else []
    if isinstance(value, list):
        for item in value:
            _flatten_json_ld(item, out)
        return out
    if isinstance(value, dict):
        out.append(value)
        graph = value.get("@graph")
        if graph:
            _flatten_json_ld(graph, out)
    return out


def _get_from_json_ld(soup: BeautifulSoup, field_names: list[str]) -> str:
    for root in _find_json_ld_objects(soup):
        for obj in _flatten_json_ld(root):
            for field_name in field_names:
                value = obj.get(field_name)
                if isinstance(value, str):
                    cleaned = _clean_text(value)
                    if cleaned:
                        return cleaned
                if field_name == "author" and isinstance(value, dict):
                    cleaned = _clean_text(value.get("name"))
                    if cleaned:
                        return cleaned
    return ""


def _strip_title_suffix(value: str) -> str:
    return re.sub(r"\s+\|\s+[^|]+$", "", value).strip()


def _extract_custom_published(html: str, url: str) -> str:
    if "kommunikasjon.ntb.no" in url:
        match = re.search(r">\s*(\d{1,2}\.\d{1,2}\.\d{4})\s+\d{2}:\d{2}:\d{2}\s+[A-Z]+(?:\s*<|[|])", html, re.IGNORECASE)
        if match:
            day, month, year = match.group(1).split(".")
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    if "uib.no" in url:
        match = re.search(r"Først publisert:\s*(\d{2}\.\d{2}\.\d{4})", html, re.IGNORECASE)
        if match:
            day, month, year = match.group(1).split(".")
            return f"{year}-{month}-{day}"

    return ""


def _normalize_published_at(value: str) -> str | None:
    raw = _clean_text(value)
    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.date().isoformat()
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            return dt.date().isoformat()
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass

    date_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", raw)
    if date_match:
        return date_match.group(0)

    return raw


def _extract_article_metadata(html: str, url: str, anchor_title: str = "") -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")

    title = (
        _get_meta_content(soup, "og:title")
        or _get_meta_content(soup, "twitter:title")
        or _strip_title_suffix(_clean_text(soup.title.get_text(" ", strip=True) if soup.title else ""))
        or _get_from_json_ld(soup, ["headline", "name"])
        or _clean_text(anchor_title)
    )
    title = _strip_title_suffix(title)

    description = (
        _get_meta_content(soup, "og:description")
        or _get_meta_content(soup, "description")
        or _get_meta_content(soup, "twitter:description")
        or _get_from_json_ld(soup, ["description"])
    )
    if not description:
        paragraphs = [p for p in _extract_paragraphs(soup) if len(p) >= 80]
        description = _clean_text(" ".join(paragraphs[:2]))[:500]

    published_raw = (
        _get_meta_content(soup, "article:published_time")
        or _get_meta_content(soup, "og:published_time")
        or _get_meta_content(soup, "publish_date")
        or _get_meta_content(soup, "pubdate")
        or _get_meta_content(soup, "datePublished")
        or _get_from_json_ld(soup, ["datePublished", "dateCreated"])
        or _extract_custom_published(html, url)
    )

    author = (
        _get_meta_content(soup, "author")
        or _get_meta_content(soup, "article:author")
        or _get_from_json_ld(soup, ["author", "creator"])
    )
    image_url = (
        _get_meta_content(soup, "og:image")
        or _get_meta_content(soup, "twitter:image")
        or _get_from_json_ld(soup, ["image", "thumbnailUrl"])
    )
    site_name = _get_meta_content(soup, "og:site_name")

    paragraphs = [_clean_text(p) for p in _extract_paragraphs(soup) if len(_clean_text(p)) >= 60]
    preview_excerpt = _clean_text(" ".join(paragraphs[:3]))[:1600]
    source_context = "\n\n".join(paragraphs[:6])[:3600]

    return {
        "title": title or _clean_text(anchor_title),
        "description": description,
        "published_at": _normalize_published_at(published_raw),
        "author": author,
        "image_url": image_url,
        "site_name": site_name,
        "preview_excerpt": preview_excerpt,
        "source_context": source_context,
    }


def fetch_article_preview(url: str, fallback_title: str = "", fallback_summary: str = "") -> dict[str, str]:
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url)
            response.raise_for_status()
        metadata = _extract_article_metadata(response.text, str(response.url), anchor_title=fallback_title)
        return {
            "title": str(metadata.get("title") or fallback_title or ""),
            "description": str(metadata.get("description") or fallback_summary or ""),
            "image_url": str(metadata.get("image_url") or ""),
            "site_name": str(metadata.get("site_name") or ""),
            "author": str(metadata.get("author") or ""),
            "published_at": str(metadata.get("published_at") or ""),
            "preview_excerpt": str(metadata.get("preview_excerpt") or ""),
            "source_context": str(metadata.get("source_context") or ""),
        }
    except Exception:
        return {
            "title": str(fallback_title or ""),
            "description": str(fallback_summary or ""),
            "image_url": "",
            "site_name": "",
            "author": "",
            "published_at": "",
            "preview_excerpt": "",
            "source_context": "",
        }


def _has_paywall_marker(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in PAYWALL_MARKERS)


def _make_raw_item(
    source_name: str,
    url: str,
    title: str,
    summary: str,
    content: str,
    now: str,
    published_at: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    content_hash = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
    return {
        "source_name": source_name,
        "article_url": url,
        "title_raw": title,
        "summary_raw": summary[:500],
        "content_raw": content,
        "content_hash": content_hash,
        "image_url": image_url or "",
        "published_at": published_at,
        "fetched_at": now,
    }


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
        paywall_count = 0
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

                    # Skip likely section/index/static pages before costly page fetch.
                    if not is_probable_article_url(url):
                        filtered_count += 1
                        continue

                    article_text = ""
                    try:
                        page_resp = client.get(url)
                        if page_resp.status_code in {401, 403}:
                            paywall_count += 1
                            note = "Paywalled content; no full access available."
                            items.append(_make_raw_item(src_name, url, title, note, f"{title}. {note}", now))
                            source_count += 1
                            if source_count >= limit_per_source:
                                break
                            continue

                        page_resp.raise_for_status()
                        metadata = _extract_article_metadata(page_resp.text, url, anchor_title=title)
                        final_title = metadata.get("title") or title
                        final_summary = metadata.get("description") or ""
                        published_at = metadata.get("published_at")
                        article_text = _extract_article_text(page_resp.text)
                        if _has_paywall_marker(page_resp.text) and not auth_configured:
                            paywall_count += 1
                            note = "Likely paywalled; only partial/open text available."
                            summary = final_summary or article_text[:500] or note
                            content = f"{final_title}. {summary}"
                            items.append(
                                _make_raw_item(
                                    src_name,
                                    url,
                                    final_title,
                                    summary,
                                    content,
                                    now,
                                    published_at=published_at,
                                    image_url=str(metadata.get("image_url") or ""),
                                )
                            )
                            source_count += 1
                            if source_count >= limit_per_source:
                                break
                            continue
                    except Exception:
                        filtered_count += 1
                        continue

                    if not is_probable_news_item(url=url, title=title, summary="", full_text=article_text):
                        filtered_count += 1
                        continue

                    summary = final_summary or article_text[:500]
                    items.append(
                        _make_raw_item(
                            src_name,
                            url,
                            final_title,
                            summary,
                            article_text,
                            now,
                            published_at=published_at,
                            image_url=str(metadata.get("image_url") or ""),
                        )
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
                "paywalled": paywall_count,
                "auth_configured": auth_configured,
                "status": "ok" if error is None else "error",
                "error": error,
            }
        )

    return items, report


def fetch_scrape_items(limit_per_source: int = 20) -> list[dict]:
    items, _ = fetch_scrape_items_with_report(limit_per_source=limit_per_source)
    return items

