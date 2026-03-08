import re
from urllib.parse import urlparse


GENERIC_STATIC_TITLES = {
    "about",
    "about us",
    "videos",
    "video",
    "photos",
    "photo",
    "membership",
    "events",
    "event",
    "careers",
    "career",
    "data",
    "policy",
    "news",
    "contact",
    "login",
    "sign in",
    "register",
    "privacy",
    "cookie policy",
    "terms",
}

STATIC_PATH_MARKERS = {
    "/about",
    "/membership",
    "/careers",
    "/events",
    "/videos",
    "/photos",
    "/contact",
    "/privacy",
    "/cookies",
    "/terms",
    "/login",
    "/register",
}

NEWS_HINT_WORDS = {
    "offshore",
    "wind",
    "auction",
    "tender",
    "project",
    "farm",
    "developer",
    "capacity",
    "floating",
    "cfd",
    "market",
    "supply chain",
    "turbine",
    "regulation",
    "policy update",
}

DATE_RE = re.compile(r"\b(20\d{2})\b|/20\d{2}/|\d{4}-\d{2}-\d{2}")


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _has_news_hints(text: str) -> bool:
    t = _norm(text)
    return any(hint in t for hint in NEWS_HINT_WORDS)


def is_probable_news_item(url: str, title: str, summary: str = "") -> bool:
    u = _norm(url)
    t = _norm(title)
    s = _norm(summary)

    if not u or not t:
        return False

    parsed = urlparse(u)
    path = parsed.path or ""

    if t in GENERIC_STATIC_TITLES:
        return False

    if any(marker in path for marker in STATIC_PATH_MARKERS):
        # Allow if there are strong news indicators.
        if not (_has_news_hints(t) or _has_news_hints(s) or DATE_RE.search(u)):
            return False

    words = [w for w in re.split(r"\s+", t) if w]
    if len(words) <= 2 and not (_has_news_hints(t) or DATE_RE.search(t)):
        return False

    text_blob = f"{t} {s} {u}"
    if _has_news_hints(text_blob):
        return True

    if DATE_RE.search(text_blob):
        return True

    # Fallback: reasonably descriptive title and non-root path.
    if len(t) >= 25 and len([p for p in path.split('/') if p]) >= 2:
        return True

    return False
