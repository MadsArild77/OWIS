"""How each source's full text can be had, learned from what worked.

Two methods are tried in order: OWIS's own request ("direct") and, when that is
blocked or comes back thin, Tavily Extract ("extract"), which reads the page on
Tavily's side. Both respect paywalls: a paywalled page gives only its teaser,
and the story then goes on to the search for an open version elsewhere.

Every attempt is counted per source and method. A method that has failed
repeatedly for a source is skipped, except for one attempt in ten, so a source
that opens up (or starts blocking) is noticed. Counts are halved once they
reach 20, so recent results weigh more than old ones.
"""
from __future__ import annotations

import os
import random
import re
from datetime import datetime, timezone

import httpx

from owis.core.storage.db import get_conn

METHODS = ("direct", "extract")
MIN_ATTEMPTS = 3
MIN_SUCCESS_RATE = 0.2
EXPLORE_SHARE = 0.1
HALVE_AT = 20
MIN_TEXT = 500  # short trade-press news is often 100-150 words


def _rows(source: str | None = None) -> dict[tuple[str, str], dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM news_fulltext_methods" + (" WHERE source_name=?" if source else ""),
                            (source,) if source else ()).fetchall()
    return {(r["source_name"], r["method"]): dict(r) for r in rows}


def record(source: str, method: str, result: str, ok: bool) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute('''INSERT INTO news_fulltext_methods(source_name, method, attempts, successes, last_result, last_at)
            VALUES(?, ?, 1, ?, ?, ?)
            ON CONFLICT(source_name, method) DO UPDATE SET attempts = attempts + 1, successes = successes + excluded.successes,
                last_result = excluded.last_result, last_at = excluded.last_at''',
                     (source, method, int(ok), result, now))
        conn.execute('''UPDATE news_fulltext_methods SET attempts = attempts / 2, successes = successes / 2
            WHERE source_name=? AND method=? AND attempts >= ?''', (source, method, HALVE_AT))


def should_try(source: str, method: str) -> bool:
    row = _rows(source).get((source, method))
    if not row or row["attempts"] < MIN_ATTEMPTS or row["successes"] / row["attempts"] >= MIN_SUCCESS_RATE:
        return True
    return random.random() < EXPLORE_SHARE


def strategy(direct: dict | None, extract: dict | None) -> str:
    """A label for the Source advisor: how this source's full text is usually had."""
    def works(row):
        return bool(row) and row["attempts"] >= MIN_ATTEMPTS and row["successes"] / row["attempts"] >= MIN_SUCCESS_RATE

    def tried(row):
        return bool(row) and row["attempts"] >= MIN_ATTEMPTS
    if works(direct):
        return "direct"
    if works(extract):
        return "extract"
    if tried(direct) and (tried(extract) or not os.getenv("TAVILY_API_KEY")):
        return "closed"
    return "learning"


def summary() -> list[dict]:
    rows = _rows()
    out = []
    for source in sorted({s for s, _ in rows}):
        direct, extract = rows.get((source, "direct")), rows.get((source, "extract"))
        out.append({"source": source, "strategy": strategy(direct, extract),
                    **{f"{m}_{k}": (rows.get((source, m)) or {}).get(k) for m in METHODS
                       for k in ("attempts", "successes", "last_result", "last_at")}})
    return out


_NOT_ARTICLE = re.compile(r"subscri|newsletter|cookie|sign up|log in|abonn|nyhetsbrev", re.I)


def _article_body(markdown: str) -> str:
    """Article sentences from Tavily's page markdown, without menus, links, images and sales text."""
    paragraphs = []
    for line in (markdown or "").splitlines():
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line).strip()
        if line.startswith(("#", "|", "*", "-", ">", "!")) or _NOT_ARTICLE.search(line):
            continue
        if len(line) >= 40 and len(line.split()) >= 6 and line[-1] in ".!?\"\u201d\u2019)":
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def extract(url: str) -> tuple[str, str]:
    """Tavily Extract for one page; counted against the shared search budget."""
    from owis.modules.news.processing.search_budget import spend
    spend("extract")
    response = httpx.post("https://api.tavily.com/extract",
                          headers={"Authorization": "Bearer " + os.environ["TAVILY_API_KEY"]},
                          json={"urls": [url], "extract_depth": "basic"}, timeout=30)
    response.raise_for_status()
    results = response.json().get("results") or []
    body = _article_body(results[0].get("raw_content", "")) if results else ""
    return ("open" if len(body) >= MIN_TEXT else "thin"), body


def fetch_fulltext(source: str, url: str, fetch_public) -> tuple[str, str, str]:
    """(access, text, url): direct first, then Tavily Extract, each only where it has worked for this source."""
    access, text = "unknown", ""
    if should_try(source, "direct"):
        try:
            access, text, url = fetch_public(url)
        except Exception as exc:
            access = "error"
            record(source, "direct", type(exc).__name__, False)
        else:
            record(source, "direct", access, access == "open")
        if access == "open":
            return access, text, url
    if access == "restricted" or not os.getenv("TAVILY_API_KEY") or not should_try(source, "extract"):
        return access, "", url
    from owis.modules.news.processing.search_budget import SearchBudgetExceeded
    try:
        result, body = extract(url)
    except SearchBudgetExceeded:
        return access, "", url  # not the source's fault
    except Exception as exc:
        record(source, "extract", type(exc).__name__, False)
        return access, "", url
    record(source, "extract", result, result == "open")
    return ("open", body, url) if result == "open" else (access, "", url)
