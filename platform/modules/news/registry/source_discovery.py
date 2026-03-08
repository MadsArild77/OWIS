from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import feedparser
import httpx
import yaml

from platform.core.config.settings import NEWS_SOURCES_PATH


COMMON_FEED_PATHS = [
    "/feed",
    "/rss",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
]


@dataclass
class ParsedSourceLine:
    name: str
    homepage: str


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        return f"https://{url}"
    return url


def _guess_name_from_url(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "")
    return host.split(".")[0].capitalize() if host else "Source"


def parse_source_input(text: str) -> list[ParsedSourceLine]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    parsed: list[ParsedSourceLine] = []
    url_pattern = re.compile(r"https?://\S+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\S*")

    for line in lines:
        if " - " in line:
            name, raw_url = line.split(" - ", 1)
            homepage = _normalize_url(raw_url)
            if homepage:
                parsed.append(ParsedSourceLine(name=name.strip() or _guess_name_from_url(homepage), homepage=homepage))
            continue

        match = url_pattern.search(line)
        if not match:
            continue

        homepage = _normalize_url(match.group(0))
        name = line.replace(match.group(0), "").strip(" -:\t")
        parsed.append(ParsedSourceLine(name=name or _guess_name_from_url(homepage), homepage=homepage))

    return parsed


def _is_valid_feed(url: str) -> bool:
    parsed = feedparser.parse(url)
    return bool(getattr(parsed, "entries", []))


def discover_feed_url(homepage: str) -> str | None:
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(homepage)
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select('link[rel="alternate"]'):
        href = (link.get("href") or "").strip()
        typ = (link.get("type") or "").lower()
        if not href:
            continue
        if "rss" in typ or "atom" in typ or "xml" in typ:
            candidate = urljoin(homepage, href)
            if _is_valid_feed(candidate):
                return candidate

    for path in COMMON_FEED_PATHS:
        candidate = urljoin(homepage, path)
        if _is_valid_feed(candidate):
            return candidate

    return None


def _default_source(name: str, homepage: str, source_type: str, source_url: str) -> dict[str, Any]:
    return {
        "name": name,
        "homepage": homepage,
        "type": source_type,
        "url": source_url,
        "enabled": True,
        "geography_tags": ["global"],
        "priority": "medium",
    }


def load_source_registry() -> list[dict[str, Any]]:
    with open(NEWS_SOURCES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])


def save_source_registry(sources: list[dict[str, Any]]) -> None:
    payload = {"sources": sources}
    with open(NEWS_SOURCES_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)


def import_sources_from_text(text: str) -> list[dict[str, Any]]:
    existing = load_source_registry()
    seen_homepages = {s.get("homepage", "") for s in existing}
    added: list[dict[str, Any]] = []

    for parsed_line in parse_source_input(text):
        if parsed_line.homepage in seen_homepages:
            continue

        feed_url = discover_feed_url(parsed_line.homepage)
        if feed_url:
            source = _default_source(parsed_line.name, parsed_line.homepage, "rss", feed_url)
        else:
            source = _default_source(parsed_line.name, parsed_line.homepage, "scrape", parsed_line.homepage)

        existing.append(source)
        added.append(source)
        seen_homepages.add(parsed_line.homepage)

    if added:
        save_source_registry(existing)

    return added
