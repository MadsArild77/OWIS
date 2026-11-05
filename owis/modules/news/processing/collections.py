from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
import re
from uuid import uuid4
from typing import Any
from fastapi import HTTPException
from owis.core.llm.client import AIClient
from owis.core.storage.db import init_db
from owis.modules.news.processing.signal import score_signal
from owis.modules.news.processing.item_view import _parse_iso_datetime, _split_csv, _clean_source_filter, _normalize_domain_bucket, _attach_metadata, _filter_domain
from owis.modules.news.storage.repository import NewsRepository


repo = NewsRepository()


_CLUSTER_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "its", "new", "of", "on", "or", "the",
    "to", "with", "offshore", "wind", "project", "projects",
}


def _title_cluster_key(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").lower()
    tokens = re.findall(r"[a-z0-9]{3,}", title)
    significant = [token for token in tokens if token not in _CLUSTER_STOPWORDS]
    if not significant:
        return f"item{int(item.get('id') or 0)}"
    return "-".join(significant[:5])


def _default_collection_key(item: dict[str, Any]) -> str:
    themes = _split_csv(item.get("theme_tags"))
    geos = _split_csv(item.get("geography_tags"))
    theme = themes[0] if themes else "general_news"
    geo = geos[0] if geos else "Global"
    title_key = _title_cluster_key(item)
    return f"auto:{theme}|{geo}|{title_key}"


def _top_values(counter: defaultdict[str, int], limit: int = 5) -> list[str]:
    return [name for name, _ in sorted(counter.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _count_values(items: list[dict], field: str, limit: int = 6) -> list[str]:
    counts: defaultdict[str, int] = defaultdict(int)
    for item in items:
        for value in _split_csv(item.get(field)):
            counts[value] += 1
    return _top_values(counts, limit=limit)


def _fallback_master_summary(items: list[dict]) -> str:
    parts: list[str] = []
    for item in sorted(items, key=lambda x: int(x.get("signal_score") or 0), reverse=True):
        source = str(item.get("source_name") or "Unknown")
        title = str(item.get("title") or "Untitled")
        summary = str(item.get("summary") or item.get("cleaned_text") or "").strip()
        if not summary:
            continue
        parts.append(f"{source} reports {title}: {summary}")
    return " ".join(parts)[:1600] or "Merged story from selected source articles."


def _synthesize_collection_master(collection_key: str, items: list[dict]) -> dict[str, Any]:
    sorted_items = sorted(items, key=lambda x: int(x.get("signal_score") or 0), reverse=True)
    lead = sorted_items[0] if sorted_items else {}
    sources = sorted({str(item.get("source_name") or "Unknown") for item in sorted_items})
    themes = _count_values(sorted_items, "theme_tags")
    geos = _count_values(sorted_items, "geography_tags")
    actors = _count_values(sorted_items, "actors")
    image_url = next((str(item.get("image_url") or "") for item in sorted_items if item.get("image_url")), "")

    synthesis_input = "\n\n".join(
        (
            f"Source: {item.get('source_name') or 'Unknown'}\n"
            f"Title: {item.get('title') or 'Untitled'}\n"
            f"Summary: {item.get('summary') or ''}\n"
            f"Why it matters: {item.get('why_it_matters') or ''}\n"
            f"Tags: {item.get('theme_tags') or ''}; {item.get('geography_tags') or ''}; {item.get('actors') or ''}\n"
            f"Text: {str(item.get('cleaned_text') or '')[:1800]}"
        )
        for item in sorted_items[:8]
    )

    ai_data = None
    try:
        ai_data = AIClient().synthesize_news_master(synthesis_input)
    except Exception:
        ai_data = None

    title = str((ai_data or {}).get("title") or lead.get("title") or "Merged story")
    summary = str((ai_data or {}).get("summary") or _fallback_master_summary(sorted_items))
    why = str((ai_data or {}).get("why_it_matters") or lead.get("why_it_matters") or "")
    ai_themes = (ai_data or {}).get("theme_tags")
    ai_geos = (ai_data or {}).get("geography_tags")
    ai_actors = (ai_data or {}).get("actors")

    return {
        "collection_key": collection_key,
        "title": title,
        "summary": summary,
        "why_it_matters": why,
        "theme_tags": ",".join([str(x).strip() for x in ai_themes if str(x).strip()]) if isinstance(ai_themes, list) and ai_themes else ",".join(themes),
        "geography_tags": ",".join([str(x).strip() for x in ai_geos if str(x).strip()]) if isinstance(ai_geos, list) and ai_geos else ",".join(geos),
        "actors": ",".join([str(x).strip() for x in ai_actors if str(x).strip()]) if isinstance(ai_actors, list) and ai_actors else ",".join(actors),
        "sources": ",".join(sources),
        "image_url": image_url,
        "lead_item_id": int(lead.get("id") or 0),
        "article_count": len(sorted_items),
        "synthesized_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_collections(
    items: list[dict],
    overrides: dict[int, dict],
    limit: int,
    items_per_collection: int,
    masters: dict[str, dict] | None = None,
) -> list[dict]:
    groups: dict[str, dict] = {}
    masters = masters or {}

    for item in items:
        processed_id = int(item.get("id") or 0)
        override = overrides.get(processed_id)
        collection_key = (override or {}).get("collection_key") or _default_collection_key(item)

        group = groups.get(collection_key)
        if group is None:
            group = {
                "collection_key": collection_key,
                "is_manual": collection_key.startswith("manual:"),
                "article_count": 0,
                "top_signal_score": 0,
                "signal_score_sum": 0,
                "latest_published_at": None,
                "themes": defaultdict(int),
                "geographies": defaultdict(int),
                "actors": defaultdict(int),
                "sources": defaultdict(int),
                "image_url": "",
                "lead_item": None,
                "items": [],
            }
            groups[collection_key] = group

        score = int(item.get("signal_score") or 0)
        group["article_count"] += 1
        group["top_signal_score"] = max(group["top_signal_score"], score)
        group["signal_score_sum"] += score

        published = item.get("published_at") or item.get("processed_at")
        if not group["latest_published_at"] or str(published) > str(group["latest_published_at"]):
            group["latest_published_at"] = published

        themes = _split_csv(item.get("theme_tags"))
        geographies = _split_csv(item.get("geography_tags"))
        actors = _split_csv(item.get("actors"))

        for theme in themes:
            group["themes"][theme] += 1
        for geo in geographies:
            group["geographies"][geo] += 1
        for actor in actors:
            group["actors"][actor] += 1
        if item.get("source_name"):
            group["sources"][str(item.get("source_name"))] += 1
        if not group["image_url"] and item.get("image_url"):
            group["image_url"] = item.get("image_url")
        if group["lead_item"] is None or score > int(group["lead_item"].get("signal_score") or 0):
            group["lead_item"] = item

        group["items"].append(
            {
                "id": processed_id,
                "title": item.get("title") or "Untitled",
                "source_name": item.get("source_name") or "Unknown",
                "article_url": item.get("article_url") or "",
                "image_url": item.get("image_url") or "",
                "signal_score": score,
                "published_at": item.get("published_at"),
                "relevance_status": str(item.get("relevance_status") or "unrated"),
                "domain_bucket": str(item.get("domain_bucket") or "other_energy"),
                "is_manual_override": bool(override),
                "interest_topics": item.get("interest_topics", []),
                "editorial": item.get("editorial", {}),
                "content_basis": {key: (item.get("content_basis") or {}).get(key) for key in ("relevance", "access", "basis")},
            }
        )

    result: list[dict] = []
    for group in groups.values():
        item_rows = sorted(
            group["items"],
            key=lambda x: (int(x.get("signal_score") or 0), str(x.get("published_at") or "")),
            reverse=True,
        )

        top_themes = sorted(group["themes"].items(), key=lambda x: x[1], reverse=True)
        top_geos = sorted(group["geographies"].items(), key=lambda x: x[1], reverse=True)
        avg_score = round(group["signal_score_sum"] / max(group["article_count"], 1), 1)
        lead_item = group["lead_item"] or {}
        buckets = {str(row.get("domain_bucket") or "other_energy") for row in group["items"]}
        focus_bucket = next((b for b in ("offshore_wind", "adjacent_energy") if b in buckets), "other_energy")
        _, _, reasons = score_signal(str(lead_item.get("title") or ""), str(lead_item.get("cleaned_text") or ""),
                                     _split_csv(lead_item.get("geography_tags")), _split_csv(lead_item.get("actors")),
                                     str(lead_item.get("source_name") or ""), lead_item.get("content_basis"))
        stored_master = masters.get(str(group["collection_key"]) or "")
        master_theme_tags = _split_csv(stored_master.get("theme_tags")) if stored_master else []
        master_geo_tags = _split_csv(stored_master.get("geography_tags")) if stored_master else []
        master_actors = _split_csv(stored_master.get("actors")) if stored_master else []
        master_sources = _split_csv(stored_master.get("sources")) if stored_master else []

        result.append(
            {
                "collection_key": group["collection_key"],
                "is_manual": group["is_manual"],
                "article_count": group["article_count"],
                "top_signal_score": group["top_signal_score"],
                "avg_signal_score": avg_score,
                "domain_bucket": focus_bucket,
                "signal_reasons": reasons,
                "latest_published_at": group["latest_published_at"],
                "primary_theme": top_themes[0][0] if top_themes else "general_news",
                "primary_geography": top_geos[0][0] if top_geos else "Global",
                "master": {
                    "lead_item_id": int((stored_master or {}).get("lead_item_id") or lead_item.get("id") or 0),
                    "title": (stored_master or {}).get("title") or lead_item.get("title") or "Merged story",
                    "summary": (stored_master or {}).get("summary") or lead_item.get("summary") or "",
                    "why_it_matters": (stored_master or {}).get("why_it_matters") or lead_item.get("why_it_matters") or "",
                    "image_url": (stored_master or {}).get("image_url") or group["image_url"] or lead_item.get("image_url") or "",
                    "themes": master_theme_tags or _top_values(group["themes"]),
                    "geographies": master_geo_tags or _top_values(group["geographies"]),
                    "actors": master_actors or _top_values(group["actors"]),
                    "sources": master_sources or _top_values(group["sources"]),
                    "synthesized_at": (stored_master or {}).get("synthesized_at"),
                },
                "items": item_rows[: max(items_per_collection, 1)],
            }
        )

    result.sort(
        key=lambda x: ((_parse_iso_datetime(x.get("latest_published_at")) or datetime.min.replace(tzinfo=timezone.utc)), int(x.get("top_signal_score") or 0), int(x.get("article_count") or 0)),
        reverse=True,
    )
    return result[: max(limit, 1)]


def _cased_collections(domain_bucket: str = "core", limit: int = 120, items_per_collection: int = 400,
                       lookback_items: int = 400, source_name: str | None = None) -> list[dict]:
    """The feed's stories with their cases, built the same way wherever cases are needed."""
    from owis.modules.news.processing.threads import assign_cases
    items = repo.latest(limit=max(lookback_items, 1), source_name=_clean_source_filter(source_name))
    items = _filter_domain(_attach_metadata(items), _normalize_domain_bucket(domain_bucket))
    collections = _build_collections(items, repo.list_collection_overrides(), limit=limit,
                                     items_per_collection=items_per_collection, masters=repo.list_collection_masters())
    return assign_cases(collections)


def list_collections(
    limit: int = 20,
    items_per_collection: int = 5,
    lookback_items: int = 400,
    source_name: str | None = None,
    domain_bucket: str = "offshore_wind",
):
    init_db()
    from owis.modules.news.processing import cases
    collections = _cased_collections(domain_bucket, limit, items_per_collection, lookback_items, source_name)
    return {"items": cases.attach(collections)}


def case_account(payload: Any):
    """Write a case's account now, when it is opened without one (otherwise it waits for the next fetch)."""
    from owis.modules.news.processing import cases
    init_db()
    group = [c for c in _cased_collections(payload.domain_bucket) if c["case"]["signature"] == payload.signature]
    if not group:
        raise HTTPException(404, "This story has changed; reload the feed.")
    cases.write_accounts(group, limit=1)
    cases.attach(group)
    account = group[0]["case"].get("account")
    if not account or not account.get("complete"):
        raise HTTPException(503, "The story could not be written now; it will be written at the next fetch.")
    return account


def merge_collections(payload: Any):
    init_db()
    item_ids = [int(x) for x in payload.item_ids if int(x) > 0]
    if len(item_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 items to merge.")

    item_ids = repo.expand_collection_members(item_ids, payload.collection_key)
    found_items = repo.list_processed_by_ids(item_ids)
    if len(found_items) != len(item_ids):
        raise HTTPException(status_code=404, detail="One or more selected items were not found.")

    provided_key = (payload.collection_key or "").strip()
    collection_key = provided_key or f"manual:{uuid4().hex}"

    updated = repo.set_collection_overrides(item_ids, collection_key=collection_key, note=payload.note)
    for item_id in item_ids:
        repo.log_learning_feedback(
            feedback_type="merge",
            feedback_value=collection_key,
            processed_id=item_id,
        )
    for left_id, right_id in combinations(item_ids, 2):
        repo.upsert_pair_learning(left_id, right_id, decision="merge", source="manual_collection_merge")
    repo.upsert_collection_master(_synthesize_collection_master(collection_key, found_items))
    return {
        "updated_count": updated,
        "collection_key": collection_key,
    }


def unmerge_collections(payload: Any):
    init_db()
    item_ids = [int(x) for x in payload.item_ids if int(x) > 0]
    if not item_ids:
        raise HTTPException(status_code=400, detail="Provide at least 1 item to unmerge.")

    removed = repo.clear_collection_overrides(item_ids)
    for item_id in item_ids:
        repo.log_learning_feedback(
            feedback_type="unmerge",
            feedback_value="automatic_grouping",
            processed_id=item_id,
        )
    return {
        "updated_count": removed,
        "message": "Selected items reverted to automatic grouping.",
    }
