from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import feedparser
import httpx
import yaml

from owis.core.config.settings import NEWS_SOURCES_PATH
from owis.core.storage.db import get_conn, init_db


_DEFAULT_NEWS_SOURCES_PATH = str(Path("owis/modules/news/registry/sources.yaml"))


def _is_default_sources_path(path_value: str) -> bool:
    configured = Path(path_value.strip())
    default = Path(_DEFAULT_NEWS_SOURCES_PATH)
    try:
        return configured.resolve() == default.resolve()
    except OSError:
        return configured.as_posix().strip() == default.as_posix().strip()


def _use_db_registry() -> bool:
    raw = os.getenv("OWI_NEWS_SOURCES_USE_DB", "true").strip().lower()
    use_db = raw in {"1", "true", "yes"}
    return use_db and _is_default_sources_path(str(NEWS_SOURCES_PATH))


def _load_source_registry_from_yaml() -> list[dict[str, Any]]:
    try:
        with open(NEWS_SOURCES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("sources", [])
    except FileNotFoundError:
        return []


def _save_source_registry_to_yaml(sources: list[dict[str, Any]], strict: bool) -> None:
    payload = {"sources": sources}
    try:
        with open(NEWS_SOURCES_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
    except Exception:
        if strict:
            raise


def _load_source_registry_from_db() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT source_json
            FROM news_source_registry
            ORDER BY position ASC, id ASC
            """
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            parsed = json.loads(str(row["source_json"]))
            if isinstance(parsed, dict):
                items.append(parsed)
        except Exception:
            continue
    return items


def _save_source_registry_to_db(sources: list[dict[str, Any]]) -> None:
    init_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM news_source_registry")
        for pos, source in enumerate(sources):
            conn.execute(
                """
                INSERT INTO news_source_registry (position, source_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (pos, json.dumps(source, ensure_ascii=False), now_iso),
            )

COMMON_FEED_PATHS = [
    "/feed",
    "/rss",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
    "/service/rss",
]

KNOWN_FEED_OVERRIDES = {
    "rechargenews.com": [
        "https://www.rechargenews.com/rss",
    ],
    "energiwatch.no": [
        "https://energiwatch.no/service/rss",
        "https://rss-feed-api.aws.jyllands-posten.dk/energiwatch.no/latest",
    ],
    "energywatch.com": [
        "https://energywatch.com/service/rss",
        "https://rss-feed-api.aws.jyllands-posten.dk/energywatch.com/latest",
    ],
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
PAYWALL_MARKERS = ["subscribe", "subscriber", "subscription", "sign in", "log in", "paywall", "abonner", "abonnement"]


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


def _host(homepage: str) -> str:
    return urlparse(_normalize_url(homepage)).netloc.replace("www.", "").lower().strip()


def _looks_like_feed_url(url: str) -> bool:
    u = url.lower()
    return any(token in u for token in ["rss", "feed", "atom", ".xml"])


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


def _build_source_auth(source: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], bool]:
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


def _validate_feed_url(url: str) -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = (resp.headers.get("content-type") or "").lower()
            snippet = resp.text[:6000].lower()
            parsed = feedparser.parse(resp.content)

        if getattr(parsed, "entries", None):
            if len(parsed.entries) > 0:
                return True, "feed has entries"

        feed_meta = getattr(parsed, "feed", None) or {}
        if feed_meta.get("title") or feed_meta.get("link"):
            return True, "feed metadata present"

        if any(token in content_type for token in ["rss", "atom", "xml"]):
            return True, f"content-type={content_type}"

        if "<rss" in snippet or "<feed" in snippet:
            return True, "rss/atom tags in content"
    except Exception as exc:
        return False, f"request/parse error: {exc.__class__.__name__}"

    return False, "not recognized as RSS/Atom feed"


def _is_valid_feed_url(url: str) -> bool:
    ok, _ = _validate_feed_url(url)
    return ok


def _candidate_feed_urls(homepage: str, soup: BeautifulSoup | None, html: str = "") -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        normalized = _normalize_url(url)
        if not normalized:
            return
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    host = _host(homepage)
    for known_url in KNOWN_FEED_OVERRIDES.get(host, []):
        add(known_url)

    if html:
        for match in re.findall(r"https?://[^\"'\s>]*(?:rss|feed|atom)[^\"'\s>]*", html, flags=re.IGNORECASE):
            add(match)
        for match in re.findall(r"(?:href|src)=['\"]([^'\"]*(?:rss|feed|atom)[^'\"]*)['\"]", html, flags=re.IGNORECASE):
            add(urljoin(homepage, match))

    if soup is not None:
        for link in soup.select('link[rel="alternate"]'):
            href = (link.get("href") or "").strip()
            typ = (link.get("type") or "").lower()
            if not href:
                continue
            if "rss" in typ or "atom" in typ or "xml" in typ or _looks_like_feed_url(href):
                add(urljoin(homepage, href))

        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            label = anchor.get_text(" ", strip=True).lower()
            if not href:
                continue
            if _looks_like_feed_url(href) or any(token in label for token in ["rss", "feed", "atom", "xml"]):
                add(urljoin(homepage, href))

    for path in COMMON_FEED_PATHS:
        add(urljoin(homepage, path))

    return candidates



def _forced_feed_for_host(homepage: str) -> str | None:
    host = _host(homepage)
    forced = KNOWN_FEED_OVERRIDES.get(host, [])
    if not forced:
        return None
    # Known watch media feeds can be temporarily empty/strict; prefer explicit endpoint.
    for u in forced:
        if "rss-feed-api.aws.jyllands-posten.dk" in u:
            return u
    return forced[0]

def discover_feed_url(homepage: str) -> str | None:
    forced = _forced_feed_for_host(homepage)
    if forced:
        return forced

    soup: BeautifulSoup | None = None
    html = ""

    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(homepage)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        soup = None

    for candidate in _candidate_feed_urls(homepage, soup, html=html):
        if _is_valid_feed_url(candidate):
            return candidate

        if "service/rss" in candidate or candidate.rstrip("/").endswith("/rss"):
            try:
                with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
                    resp2 = client.get(candidate)
                    resp2.raise_for_status()
                    soup2 = BeautifulSoup(resp2.text, "html.parser")
                    html2 = resp2.text
                for nested in _candidate_feed_urls(candidate, soup2, html=html2):
                    if _is_valid_feed_url(nested):
                        return nested
            except Exception:
                pass

    return None


def discover_feed_url_with_debug(homepage: str) -> dict[str, Any]:
    forced = _forced_feed_for_host(homepage)
    if forced:
        return {
            "homepage": homepage,
            "homepage_ok": True,
            "homepage_error": "",
            "candidate_count": len(KNOWN_FEED_OVERRIDES.get(_host(homepage), [])),
            "candidates_checked": [
                {
                    "candidate": forced,
                    "valid": True,
                    "reason": "known_feed_override",
                }
            ],
            "discovered_feed_url": forced,
        }

    soup: BeautifulSoup | None = None
    html = ""
    homepage_ok = True
    homepage_error = ""

    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(homepage)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        soup = None
        homepage_ok = False
        homepage_error = f"{exc.__class__.__name__}: {exc}"

    candidates = _candidate_feed_urls(homepage, soup, html=html)
    checked: list[dict[str, Any]] = []
    found_url: str | None = None

    for candidate in candidates:
        valid, reason = _validate_feed_url(candidate)
        checked.append({"candidate": candidate, "valid": valid, "reason": reason})
        if valid and found_url is None:
            found_url = candidate
            continue

        if "service/rss" in candidate or candidate.rstrip("/").endswith("/rss"):
            try:
                with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
                    resp2 = client.get(candidate)
                    resp2.raise_for_status()
                    soup2 = BeautifulSoup(resp2.text, "html.parser")
                    html2 = resp2.text
                for nested in _candidate_feed_urls(candidate, soup2, html=html2):
                    n_valid, n_reason = _validate_feed_url(nested)
                    checked.append({"candidate": nested, "valid": n_valid, "reason": f"nested:{n_reason}"})
                    if n_valid and found_url is None:
                        found_url = nested
            except Exception as exc:
                checked.append({"candidate": candidate, "valid": False, "reason": f"nested_error:{exc.__class__.__name__}"})

    return {
        "homepage": homepage,
        "homepage_ok": homepage_ok,
        "homepage_error": homepage_error,
        "candidate_count": len(candidates),
        "candidates_checked": checked,
        "discovered_feed_url": found_url,
    }


def source_health_report(only_enabled: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = load_source_registry()

    for source in sources:
        if only_enabled and not source.get("enabled"):
            continue

        src_name = source.get("name", "unknown")
        src_type = source.get("type", "unknown")
        homepage = source.get("homepage") or source.get("url") or ""
        host = _host(homepage) if homepage else ""
        auth_headers, auth_cookies, auth_configured = _build_source_auth(source)

        row: dict[str, Any] = {
            "source": src_name,
            "type": src_type,
            "homepage": homepage,
            "host": host,
            "enabled": bool(source.get("enabled")),
            "manual_override": bool(source.get("manual_override")),
            "auth_configured": auth_configured,
            "status": "unknown",
            "detail": "",
            "suggested_open_search": [
                f"offshore wind {src_name} project",
                f"offshore wind {host} open source",
            ],
        }

        if not homepage:
            row["status"] = "error"
            row["detail"] = "missing_homepage"
            rows.append(row)
            continue

        if src_type == "rss":
            feed_url = source.get("url") or homepage
            ok, reason = _validate_feed_url(feed_url)
            row["status"] = "healthy" if ok else "rss_invalid"
            row["detail"] = reason
            rows.append(row)
            continue

        try:
            with httpx.Client(timeout=15, follow_redirects=True, headers=auth_headers, cookies=auth_cookies or None) as client:
                resp = client.get(homepage)
            body = (resp.text or "")[:8000].lower()
            has_paywall_signals = any(m in body for m in PAYWALL_MARKERS)

            if resp.status_code in {401, 403}:
                row["status"] = "auth_forbidden" if auth_configured else "paywall_no_auth"
                row["detail"] = f"http_{resp.status_code}"
            elif has_paywall_signals:
                row["status"] = "paywall_detected_with_auth" if auth_configured else "paywall_no_auth"
                row["detail"] = "paywall_markers_detected"
            else:
                row["status"] = "healthy"
                row["detail"] = f"http_{resp.status_code}"
        except Exception as exc:
            row["status"] = "error"
            row["detail"] = f"{exc.__class__.__name__}: {exc}"

        rows.append(row)

    return rows


def _default_source(name: str, homepage: str, source_type: str, source_url: str) -> dict[str, Any]:
    return {
        "name": name,
        "homepage": homepage,
        "type": source_type,
        "url": source_url,
        "enabled": True,
        "manual_override": False,
        "geography_tags": ["global"],
        "priority": "medium",
    }


def load_source_registry() -> list[dict[str, Any]]:
    if _use_db_registry():
        init_db()
        db_sources = _load_source_registry_from_db()
        if db_sources:
            return db_sources

    yaml_sources = _load_source_registry_from_yaml()

    if _use_db_registry() and yaml_sources:
        _save_source_registry_to_db(yaml_sources)

    return yaml_sources


def save_source_registry(sources: list[dict[str, Any]]) -> None:
    if _use_db_registry():
        _save_source_registry_to_db(sources)
        # Keep YAML in sync as a best-effort local/dev fallback.
        _save_source_registry_to_yaml(sources, strict=False)
        return

    _save_source_registry_to_yaml(sources, strict=True)


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


def delete_source(index: int) -> dict[str, Any] | None:
    sources = load_source_registry()
    if index < 0 or index >= len(sources):
        return None

    removed = sources.pop(index)
    save_source_registry(sources)
    return removed


def update_source(index: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    sources = load_source_registry()
    if index < 0 or index >= len(sources):
        return None

    target = sources[index]
    allowed = {
        "name",
        "homepage",
        "type",
        "url",
        "enabled",
        "priority",
        "geography_tags",
        "auth",
        "manual_override",
    }
    for k, v in updates.items():
        if k in allowed and v is not None:
            if k in {"homepage", "url"}:
                target[k] = _normalize_url(str(v))
            else:
                target[k] = v

    if any(key in updates for key in {"homepage", "type", "url"}) and "manual_override" not in updates:
        target["manual_override"] = True

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


def rediscover_rss_for_sources(only_scrape: bool = True, with_debug: bool = False) -> dict[str, Any]:
    sources = load_source_registry()
    updated_count = 0
    checked_count = 0
    details: list[dict[str, Any]] = []

    for source in sources:
        if only_scrape and source.get("type") != "scrape":
            continue
        if source.get("manual_override"):
            if with_debug:
                details.append(
                    {
                        "source_name": source.get("name"),
                        "source_type": source.get("type"),
                        "status": "skipped_manual_override",
                        "homepage": source.get("homepage") or source.get("url"),
                    }
                )
            continue

        homepage = source.get("homepage") or source.get("url")
        if not homepage:
            continue

        checked_count += 1
        debug_payload = discover_feed_url_with_debug(homepage) if with_debug else None
        feed_url = (debug_payload or {}).get("discovered_feed_url") if debug_payload else discover_feed_url(homepage)

        if not feed_url:
            if debug_payload is not None:
                details.append(
                    {
                        "source_name": source.get("name"),
                        "source_type": source.get("type"),
                        "status": "no_feed_found",
                        **debug_payload,
                    }
                )
            continue

        changed = source.get("type") != "rss" or source.get("url") != feed_url
        status = "updated" if changed else "unchanged"
        if changed:
            source["type"] = "rss"
            source["url"] = feed_url
            updated_count += 1

        if debug_payload is not None:
            details.append(
                {
                    "source_name": source.get("name"),
                    "source_type": source.get("type"),
                    "status": status,
                    **debug_payload,
                }
            )

    if updated_count > 0:
        save_source_registry(sources)

    result: dict[str, Any] = {
        "updated_count": updated_count,
        "checked_count": checked_count,
        "only_scrape": only_scrape,
        "total_sources": len(sources),
    }
    if with_debug:
        result["details"] = details

    return result
