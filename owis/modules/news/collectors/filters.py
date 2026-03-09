import re
from urllib.parse import parse_qs, urlparse


GENERIC_STATIC_TITLES = {
    "about",
    "about us",
    "about wind",
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
    "latest news",
    "position and statements",
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
    "/tag/",
    "/category/",
}

SECTION_SEGMENTS = {
    "news",
    "latest-news",
    "about",
    "about-us",
    "events",
    "careers",
    "membership",
    "policy",
    "data",
    "video",
    "videos",
    "photo",
    "photos",
    "category",
    "tag",
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
    "gw",
    "mw",
}

DATE_RE = re.compile(r"\b(20\d{2})\b|/20\d{2}/|\d{4}-\d{2}-\d{2}")


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _has_news_hints(text: str) -> bool:
    t = _norm(text)
    return any(hint in t for hint in NEWS_HINT_WORDS)


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", _norm(text)) if w])


def _is_probable_article_path(url: str) -> bool:
    parsed = urlparse(_norm(url))
    path = parsed.path or ""
    segments = [s for s in path.split("/") if s]
    if not segments:
        return False

    last = segments[-1].lower()
    depth = len(segments)

    has_date = bool(DATE_RE.search(path))
    has_slug = "-" in last and len(last) >= 12
    has_long_id = bool(re.search(r"\d{5,}", last))

    query = parse_qs(parsed.query)
    has_article_query = any(k in query for k in ["id", "article", "story", "post", "p"])

    if depth == 1 and last in SECTION_SEGMENTS and not (has_date or has_slug or has_long_id or has_article_query):
        return False

    if any(marker in path for marker in STATIC_PATH_MARKERS) and depth <= 2 and not (has_date or has_slug or has_long_id):
        return False

    if has_date or has_slug or has_long_id or has_article_query:
        return True

    return depth >= 3 and last not in SECTION_SEGMENTS


def is_probable_news_item(url: str, title: str, summary: str = "", full_text: str = "") -> bool:
    u = _norm(url)
    t = _norm(title)
    s = _norm(summary)
    f = _norm(full_text)

    if not u or not t:
        return False

    parsed = urlparse(u)
    path = parsed.path or ""

    if t in GENERIC_STATIC_TITLES:
        return False

    if _word_count(t) <= 2 and not (_has_news_hints(t) or DATE_RE.search(t)):
        return False

    if any(marker in path for marker in STATIC_PATH_MARKERS):
        if not (_has_news_hints(t) or _has_news_hints(s) or DATE_RE.search(u)):
            return False

    if not _is_probable_article_path(u):
        # Treat URL as section/index page unless strong evidence says otherwise.
        if not (DATE_RE.search(u) and (_has_news_hints(t) or _has_news_hints(s))):
            return False

    text_blob = f"{t} {s} {u}"

    # For scraped pages: require minimum body text quality.
    if f:
        if len(f) < 220:
            return False
        if _word_count(f) < 40:
            return False

    if _has_news_hints(text_blob) or _has_news_hints(f):
        return True

    if DATE_RE.search(text_blob) or DATE_RE.search(f):
        return True

    if len(t) >= 35 and len([p for p in path.split('/') if p]) >= 2:
        return True

    return False


def is_probable_article_url(url: str) -> bool:
    return _is_probable_article_path(_norm(url))

