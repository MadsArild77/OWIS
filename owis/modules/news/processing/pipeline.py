from datetime import datetime, timezone
import re

from owis.core.llm.client import AIClient

PAYWALL_MARKERS = ["paywalled", "paywall", "no full access", "partial/open text", "subscriber", "subscription"]


_THEME_KEYWORDS: list[tuple[str, list[str]]] = [
    ("market_competition", ["auction", "cfd", "bid", "leasing round", "prequalification", "license round"]),
    ("procurement", ["tender", "procurement", "rfp", "framework agreement", "contract notice"]),
    ("funding", ["grant", "funding", "support scheme", "horizon", "subsidy"]),
    ("policy", ["policy", "regulation", "government", "ministry", "directive", "consultation"]),
    ("projects", ["project", "fids", "final investment decision", "pipeline", "capacity expansion"]),
    ("supply_chain", ["supply chain", "supplier", "factory", "port", "installation vessel", "fabrication"]),
    ("technology", ["floating", "fixed-bottom", "turbine", "substation", "foundation", "electrolyser"]),
    ("finance", ["financing", "investment", "bank", "equity", "debt", "ppas"]),
]


def _clean_text(raw_text: str) -> str:
    text = re.sub(r"\s+", " ", raw_text or "").strip()
    return text


def _summary(text: str) -> str:
    if not text:
        return "No summary available."
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:3]).strip()[:700]


def _contains_token(text: str, token: str) -> bool:
    t = token.lower().strip()
    if not t:
        return False
    if len(t) <= 3 and t.isalpha():
        return re.search(rf"\b{re.escape(t)}\b", text) is not None
    return t in text


def _classify_theme(text: str) -> list[str]:
    lower = text.lower()
    tags: list[str] = []

    for tag, keywords in _THEME_KEYWORDS:
        if any(_contains_token(lower, keyword) for keyword in keywords):
            tags.append(tag)

    if not tags:
        tags.append("general_news")

    return tags


def _classify_geo(text: str) -> list[str]:
    lower = text.lower()
    mapping = {
        "norway": "Norway",
        "norwegian": "Norway",
        "uk": "UK",
        "united kingdom": "UK",
        "england": "UK",
        "scotland": "UK",
        "eu": "EU",
        "europe": "Europe",
        "denmark": "Denmark",
        "germany": "Germany",
        "netherlands": "Netherlands",
        "dutch": "Netherlands",
        "sweden": "Sweden",
        "france": "France",
        "spain": "Spain",
        "poland": "Poland",
        "italy": "Italy",
        "japan": "Japan",
        "korea": "South Korea",
        "south korea": "South Korea",
        "usa": "USA",
        "united states": "USA",
        "canada": "Canada",
        "australia": "Australia",
        "taiwan": "Taiwan",
    }

    tags = [label for token, label in mapping.items() if _contains_token(lower, token)]
    unique = sorted(set(tags))
    return unique or ["Global"]


def _extract_actors(text: str) -> list[str]:
    candidates = [
        "Equinor",
        "RWE",
        "Vattenfall",
        "Orsted",
        "TotalEnergies",
        "BP",
        "Shell",
        "Iberdrola",
        "Siemens Gamesa",
        "Vestas",
        "GE Vernova",
        "Statkraft",
    ]
    lower = text.lower()
    return [company for company in candidates if company.lower() in lower]


def _why_it_matters(theme_tags: list[str], geo_tags: list[str]) -> str:
    return (
        f"This may influence offshore wind strategy in {', '.join(geo_tags)} "
        f"through themes: {', '.join(theme_tags)}."
    )


def _score(theme_tags: list[str], geo_tags: list[str], actors: list[str], text: str) -> int:
    score = 28
    score += min(len(theme_tags) * 9, 30)
    score += 10 if any(geo in geo_tags for geo in ["Norway", "UK", "EU", "Europe"]) else 5
    score += min(len(actors) * 7, 21)
    if len(text) > 500:
        score += 10
    if any(tag in theme_tags for tag in ["market_competition", "procurement", "funding", "policy"]):
        score += 8
    return min(score, 100)


def _safe_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(x).strip() for x in value if str(x).strip()]
        return cleaned or fallback
    return fallback


def _safe_float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _is_paywalled(raw: dict, text: str) -> bool:
    title = (raw.get("title_raw") or "").lower()
    blob = f"{raw.get('summary_raw','')} {raw.get('content_raw','')} {text}".lower()
    return "[paywalled]" in title or any(marker in blob for marker in PAYWALL_MARKERS)


def process_raw_item(raw: dict) -> dict:
    text = _clean_text(raw.get("content_raw") or raw.get("summary_raw") or raw.get("title_raw") or "")

    ai = AIClient()
    try:
        ai_data = ai.enrich_news(text)
    except Exception:
        ai_data = None

    theme_tags = _safe_list(ai_data.get("theme_tags") if ai_data else None, _classify_theme(text))
    geo_tags = _safe_list(ai_data.get("geography_tags") if ai_data else None, _classify_geo(text))
    actors = _safe_list(ai_data.get("actors") if ai_data else None, _extract_actors(text))
    summary = ai_data.get("summary") if ai_data and ai_data.get("summary") else _summary(text)
    why_it_matters = (
        ai_data.get("why_it_matters")
        if ai_data and ai_data.get("why_it_matters")
        else _why_it_matters(theme_tags, geo_tags)
    )
    linkedin_angle = (
        ai_data.get("linkedin_angle")
        if ai_data and ai_data.get("linkedin_angle")
        else "Explain why this signal matters for offshore wind investors and supply chain players."
    )
    confidence = _safe_float(ai_data.get("confidence", 0.65), 0.65) if ai_data else 0.65

    score = _score(theme_tags, geo_tags, actors, text)
    paywalled = _is_paywalled(raw, text)
    title = raw.get("title_raw") or "Untitled"

    if paywalled and "[Paywalled]" not in title:
        title = f"[Paywalled] {title}"
    if paywalled and not summary.lower().startswith("paywalled"):
        summary = f"Paywalled: full article unavailable. {summary}"
    if paywalled:
        confidence = min(confidence, 0.45)

    linkedin_candidate = 1 if score >= 65 else 0

    return {
        "raw_item_id": raw["id"],
        "title": title,
        "cleaned_text": text,
        "summary": summary,
        "theme_tags": ",".join(theme_tags),
        "geography_tags": ",".join(geo_tags),
        "actors": ",".join(actors),
        "why_it_matters": why_it_matters,
        "signal_score": score,
        "confidence": max(0.0, min(confidence, 1.0)),
        "linkedin_angle": linkedin_angle,
        "linkedin_candidate": linkedin_candidate,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

