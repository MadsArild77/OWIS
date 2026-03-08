from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import feedparser
import httpx
import yaml

from owis.core.config.settings import NEWS_SOURCES_PATH


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


def _source_key(source: dict[str, Any]) -> str:
    base = source.get("homepage") or source.get("url") or ""
    parsed = urlparse(_normalize_url(base))
    return parsed.netloc.replace("www.", "").lower().strip()


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
    seen = {_source_key(s) for s in existing}
    added: list[dict[str, Any]] = []

    for parsed_line in parse_source_input(text):
        candidate = _default_source(parsed_line.name, parsed_line.homepage, "scrape", parsed_line.homepage)
        key = _source_key(candidate)
        if key in seen:
            continue

        feed_url = discover_feed_url(parsed_line.homepage)
        if feed_url:
            source = _default_source(parsed_line.name, parsed_line.homepage, "rss", feed_url)
        else:
            source = candidate

        existing.append(source)
        added.append(source)
        seen.add(key)

    if added:
        save_source_registry(existing)

    return added


def set_source_enabled(index: int, enabled: bool) -> dict[str, Any] | None:
    sources = load_source_registry()
    if index < 0 or index >= len(sources):
        return None
    sources[index]["enabled"] = bool(enabled)
    save_source_registry(sources)
    return sources[index]


def update_source(index: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    sources = load_source_registry()
    if index < 0 or index >= len(sources):
        return None

    target = sources[index]
    allowed = {"name", "homepage", "type", "url", "enabled", "priority", "geography_tags"}
    for k, v in updates.items():
        if k in allowed and v is not None:
            if k in {"homepage", "url"}:
                target[k] = _normalize_url(str(v))
            else:
                target[k] = v

    save_source_registry(sources)
    return target


def _is_better_source(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a_score = 0
    b_score = 0
    if a.get("type") == "rss":
        a_score += 2
    if b.get("type") == "rss":
        b_score += 2
    if a.get("enabled"):
        a_score += 1
    if b.get("enabled"):
        b_score += 1
    return a_score >= b_score


def dedupe_sources() -> dict[str, Any]:
    sources = load_source_registry()
    kept_by_key: dict[str, dict[str, Any]] = {}

    for src in sources:
        key = _source_key(src)
        if not key:
            key = f"unknown-{id(src)}"
        if key not in kept_by_key:
            kept_by_key[key] = src
            continue
        current = kept_by_key[key]
        kept_by_key[key] = src if _is_better_source(src, current) else current

    deduped = list(kept_by_key.values())
    removed_count = len(sources) - len(deduped)
    if removed_count > 0:
        save_source_registry(deduped)

    return {
        "before": len(sources),
        "after": len(deduped),
        "removed_count": removed_count,
    }
