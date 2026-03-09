from __future__ import annotations

import re

from owis.core.llm.client import AIClient

_BUCKETS = {"offshore_wind", "adjacent_energy", "other_energy"}

OFFSHORE_TERMS = {
    "offshore wind",
    "offshore",
    "wind farm",
    "floating wind",
    "fixed-bottom",
    "turbine installation",
    "cfd auction",
    "lease round",
    "subsea cable",
}

ADJACENT_TERMS = {
    "grid",
    "transmission",
    "interconnector",
    "hydrogen",
    "electrolyser",
    "port",
    "supply chain",
    "battery",
    "renewables",
    "power market",
}

OTHER_ENERGY_TERMS = {
    "oil",
    "gas",
    "lng",
    "upstream",
    "drilling",
    "refinery",
    "petroleum",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _hits(text: str, terms: set[str]) -> int:
    t = _norm(text)
    return sum(1 for term in terms if term in t)


def classify_domain_bucket(title: str, summary: str, themes: str) -> tuple[str, float]:
    blob = _norm(f"{title} {summary} {themes}")
    if not blob:
        return "other_energy", 0.4

    offshore_hits = _hits(blob, OFFSHORE_TERMS)
    adjacent_hits = _hits(blob, ADJACENT_TERMS)
    other_hits = _hits(blob, OTHER_ENERGY_TERMS)

    if offshore_hits >= 2:
        return "offshore_wind", 0.92
    if offshore_hits >= 1 and other_hits == 0:
        return "offshore_wind", 0.84
    if other_hits >= 2 and offshore_hits == 0:
        return "other_energy", 0.9
    if adjacent_hits >= 1 and offshore_hits == 0:
        return "adjacent_energy", 0.78

    if offshore_hits > 0:
        return "offshore_wind", 0.68
    if adjacent_hits > 0:
        return "adjacent_energy", 0.66
    if other_hits > 0:
        return "other_energy", 0.66
    return "other_energy", 0.52


def classify_domain_with_ai_fallback(title: str, summary: str, themes: str) -> tuple[str, float]:
    bucket, confidence = classify_domain_bucket(title=title, summary=summary, themes=themes)
    if confidence >= 0.85:
        return bucket, confidence

    ai = AIClient()
    ai_result = ai.classify_news_domain(title=title, summary=summary, themes=themes)
    if not ai_result:
        return bucket, confidence

    ai_bucket = str(ai_result.get("domain_bucket") or "").strip().lower()
    ai_conf = float(ai_result.get("confidence") or 0.0)
    if ai_bucket not in _BUCKETS:
        return bucket, confidence

    # Keep AI only for uncertain cases to protect precision.
    if ai_conf >= confidence:
        return ai_bucket, min(max(ai_conf, 0.0), 1.0)
    return bucket, confidence
