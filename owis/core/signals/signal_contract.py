from typing import Any


def map_news_to_signal(processed: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": f"news_{processed['id']}",
        "module_type": "news",
        "module_item_id": str(processed["id"]),
        "title": processed["title"],
        "source_name": raw["source_name"],
        "source_url": raw["article_url"],
        "published_at": raw["published_at"],
        "country": "unknown",
        "geography_tags": [x for x in processed["geography_tags"].split(",") if x],
        "theme_tags": [x for x in processed["theme_tags"].split(",") if x],
        "actors": [x for x in processed["actors"].split(",") if x],
        "summary": processed["summary"],
        "why_it_matters": processed["why_it_matters"],
        "signal_score": processed["signal_score"],
        "confidence": processed["confidence"],
        "linkedin_angle": processed["linkedin_angle"],
        "linkedin_candidate": bool(processed["linkedin_candidate"]),
        "raw_reference": f"raw_{raw['id']}",
    }


def map_opportunity_to_signal(processed: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": f"opportunity_{processed['id']}",
        "module_type": "opportunities",
        "module_item_id": str(processed["id"]),
        "title": processed["title"],
        "source_name": processed["source_name"],
        "source_url": processed["source_url"],
        "published_at": raw.get("publication_date"),
        "country": processed.get("country") or "",
        "geography_tags": [processed.get("country") or ""],
        "theme_tags": [processed.get("opportunity_family") or ""],
        "actors": [processed.get("buyer") or ""],
        "summary": processed["summary"],
        "why_it_matters": processed["why_it_matters"],
        "signal_score": processed["signal_score"],
        "confidence": processed["confidence"],
        "deadline": processed.get("deadline"),
        "mechanism_type": processed.get("mechanism_type"),
        "opportunity_family": processed.get("opportunity_family"),
        "recommended_action": processed.get("recommended_action"),
        "raw_reference": f"raw_{raw['id']}",
    }