from __future__ import annotations

import re

from owis.core.llm.client import AIClient
from owis.modules.news.processing.signal import classify_focus

_BUCKETS = {"offshore_wind", "adjacent_energy", "other_energy"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("_", " ")).strip().lower()


def _safe_float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(fallback)

def classify_domain_bucket(title: str, summary: str, themes: str) -> tuple[str, float]:
    """Offshore wind first, then related areas (grid, power market, maritime...), then other energy."""
    focus = classify_focus(_norm(f"{title} {summary} {themes}"))
    return focus.bucket, focus.confidence


def classify_domain_with_ai_fallback(title: str, summary: str, themes: str) -> tuple[str, float]:
    bucket, confidence = classify_domain_bucket(title=title, summary=summary, themes=themes)
    if confidence >= 0.85:
        return bucket, confidence

    ai = AIClient()
    ai_result = ai.classify_news_domain(title=title, summary=summary, themes=themes)
    if not ai_result:
        return bucket, confidence

    ai_bucket = str(ai_result.get("domain_bucket") or "").strip().lower()
    ai_conf = _safe_float(ai_result.get("confidence") or 0.0, 0.0)
    if ai_bucket not in _BUCKETS:
        return bucket, confidence

    # Keep AI only for uncertain cases to protect precision.
    if ai_conf >= confidence:
        return ai_bucket, min(max(ai_conf, 0.0), 1.0)
    return bucket, confidence
