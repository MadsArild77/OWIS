from datetime import datetime, timezone
import re

from platform.core.llm.client import AIClient


def _clean_text(raw_text: str) -> str:
    text = re.sub(r"\s+", " ", raw_text or "").strip()
    return text


def _summary(text: str) -> str:
    if not text:
        return "No summary available."
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:3]).strip()[:700]


def _classify_theme(text: str) -> list[str]:
    lower = text.lower()
    tags = []
    if any(k in lower for k in ["auction", "cfd", "tender", "bid"]):
        tags.append("market_competition")
    if any(k in lower for k in ["policy", "regulation", "government", "ministry"]):
        tags.append("policy")
    if any(k in lower for k in ["floating", "fixed-bottom", "turbine", "substation"]):
        tags.append("technology")
    if not tags:
        tags.append("general_news")
    return tags


def _classify_geo(text: str) -> list[str]:
    lower = text.lower()
    mapping = {
        "norway": "Norway",
        "uk": "UK",
        "united kingdom": "UK",
        "eu": "EU",
        "europe": "Europe",
        "denmark": "Denmark",
        "germany": "Germany",
    }
    tags = [v for k, v in mapping.items() if k in lower]
    return sorted(set(tags)) or ["Global"]


def _extract_actors(text: str) -> list[str]:
    # Simple placeholder extraction for v1; replace with NER model later.
    candidates = ["Equinor", "RWE", "Vattenfall", "Orsted", "TotalEnergies"]
    lower = text.lower()
    return [c for c in candidates if c.lower() in lower]


def _why_it_matters(theme_tags: list[str], geo_tags: list[str]) -> str:
    return (
        f"This may influence offshore wind strategy in {', '.join(geo_tags)} "
        f"through themes: {', '.join(theme_tags)}."
    )


def _score(theme_tags: list[str], geo_tags: list[str], actors: list[str], text: str) -> int:
    score = 30
    score += min(len(theme_tags) * 10, 25)
    score += 10 if "Norway" in geo_tags or "Europe" in geo_tags else 5
    score += min(len(actors) * 8, 20)
    if len(text) > 500:
        score += 10
    return min(score, 100)


def _safe_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(x).strip() for x in value if str(x).strip()]
        return cleaned or fallback
    return fallback


def process_raw_item(raw: dict) -> dict:
    text = _clean_text(raw.get("content_raw") or raw.get("summary_raw") or raw.get("title_raw") or "")

    ai = AIClient()
    ai_data = ai.enrich_news(text)

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
    confidence = float(ai_data.get("confidence", 0.65)) if ai_data else 0.65

    score = _score(theme_tags, geo_tags, actors, text)
    linkedin_candidate = 1 if score >= 65 else 0

    return {
        "raw_item_id": raw["id"],
        "title": raw.get("title_raw") or "Untitled",
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
