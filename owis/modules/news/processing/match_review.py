import time
import os
from typing import Any
from fastapi import HTTPException
from owis.core.config.settings import MATCH_MAX_PAIRS
from owis.modules.news.matching.semantic import embed_articles, read_cache
from owis.core.llm.client import AIClient
from owis.core.storage.db import init_db, get_conn
from owis.modules.news.matching.service import auto_decision, build_candidate_pairs, judge_pair, judgement_cache_key, should_enqueue_review, window_start_iso
from owis.modules.news.processing.jobs import _update_job
from owis.modules.news.processing.collections import _synthesize_collection_master
from owis.modules.news.processing.item_view import _normalize_domain_bucket, _attach_domain_data, _filter_domain
from owis.modules.news.storage.repository import NewsRepository


repo = NewsRepository()


def _auto_merge_threshold() -> float:
    try:
        return min(max(float(os.getenv("OWI_MATCH_AUTO_MERGE_CONFIDENCE", "0.85")), 0.7), 1.0)
    except ValueError:
        return 0.85


def _run_match_review(payload: Any, job_id: str | None = None, deadline: float | None = None) -> dict[str, Any]:
    """deadline (time.monotonic) stops card making and pair review; the rest waits for the next run."""
    init_db()
    bucket = _normalize_domain_bucket(payload.domain_bucket)
    since_iso = window_start_iso(payload.days_window)
    if job_id:
        _update_job(job_id, status="running", percent=8, step="Loading recent processed articles...")

    items = repo.list_processed_since(since_iso=since_iso, limit=max(payload.lookback_items, 50))
    items = _filter_domain(_attach_domain_data(items), bucket)
    if job_id:
        _update_job(job_id, percent=14, step="Describing each story as an event card...")
    from owis.modules.news.processing.event_cards import attach_cards, ensure_cards
    from owis.modules.news.processing.threads import same_action_reported_twice
    cards_made = ensure_cards(items, deadline=deadline)
    attach_cards(items)
    if job_id:
        _update_job(job_id, percent=20, step=f"Building candidate pairs from {len(items)} articles...")

    learned_pairs = {
        (int(row["item_a_id"]), int(row["item_b_id"])): str(row["decision"])
        for row in repo.list_pair_learning()
    }
    ai = AIClient()
    if not ai.enabled:
        raise HTTPException(status_code=503, detail="OpenAI matching is not enabled. Configure OPENAI_API_KEY and OWI_AI_ENABLED=true on the server.")
    try:
        embeddings = embed_articles(items)
    except Exception:
        raise HTTPException(status_code=502, detail="OpenAI embeddings failed. Check model access, quota and server configuration.")
    candidates = build_candidate_pairs(
        items,
        days_window=payload.days_window,
        top_k=payload.top_k,
        learned_pairs=learned_pairs,
        embeddings=embeddings,
    )
    with get_conn() as conn:
        decided = {(r[0], r[1]): bool(r[2]) for r in conn.execute(
            """SELECT item_a_id, item_b_id, status = 'accepted' AND decided_by = 'auto' AND relationship = 'update'
               FROM news_match_review_pairs WHERE status != 'pending'""")}
    # Automatic update links stay open to re-judging, so a same-event pair once judged as a follow-up can still merge.
    auto_links = {pair for pair, is_auto_link in decided.items() if is_auto_link}
    candidates = [p for p in candidates
                  if decided.get(tuple(sorted((int(p[0]["id"]), int(p[1]["id"])))), True)]
    # Unjudged pairs first; coverage from different outlets before same-outlet pairs; then most similar.
    candidates.sort(key=lambda p: (read_cache(judgement_cache_key(p[0], p[1])) is not None,
                                   p[0].get("source_name") == p[1].get("source_name"), -p[2]))
    candidate_count = len(candidates)
    candidates = candidates[:max(1, MATCH_MAX_PAIRS)]

    enqueued = 0
    reviewed = 0
    fallback_count = 0
    auto_merged = 0
    auto_linked = 0
    threshold = _auto_merge_threshold()

    total = max(len(candidates), 1)
    for left, right, heuristic_score in candidates:
        if deadline and time.monotonic() > deadline:
            break
        if job_id:
            pct = 24 + min(62, int((reviewed / total) * 62))
            _update_job(job_id, percent=pct, step=f"Reviewing match pair {reviewed + 1}/{len(candidates)}...")
        judgement = judge_pair(ai=ai, item_a=left, item_b=right, heuristic_score=heuristic_score)
        if judgement.get("relationship") == "update" and same_action_reported_twice(left, right):
            judgement = {**judgement, "relationship": "same_event", "same_story": "yes",
                         "reason_short": "Same project, party and kind of event within two days. " + str(judgement.get("reason_short") or "")}
        reviewed += 1
        if judgement.get("fallback"):
            fallback_count += 1

        pair_ids = tuple(sorted((int(left["id"]), int(right["id"]))))
        if pair_ids in auto_links:
            if not (payload.auto_apply and auto_decision(judgement, threshold) == "accept"):
                continue
            repo.reopen_auto_update_link(*pair_ids)
        if not should_enqueue_review(judgement):
            continue

        repo.upsert_match_review_pair(
            item_a_id=int(left.get("id") or 0),
            item_b_id=int(right.get("id") or 0),
            ai_same_story=str(judgement.get("same_story") or "no"),
            ai_confidence=float(judgement.get("confidence") or 0.0),
            reason_short=str(judgement.get("reason_short") or ""),
            overlap_entities=[str(x) for x in (judgement.get("overlap_entities") or [])],
            overlap_timeframe=str(judgement.get("overlap_timeframe") or ""),
            relationship=judgement.get("relationship", "uncertain"),
        )
        enqueued += 1
        decision = auto_decision(judgement, threshold) if payload.auto_apply else None
        pair_id = repo.pending_pair_id(int(left.get("id") or 0), int(right.get("id") or 0)) if decision else None
        if pair_id:
            try:
                applied = repo.apply_match_decision(pair_id, decision, "auto")
            except (LookupError, ValueError):
                continue
            if applied["collection_key"]:
                found_items = repo.list_processed_by_ids(applied["item_ids"])
                repo.upsert_collection_master(_synthesize_collection_master(applied["collection_key"], found_items))
                auto_merged += 1
            else:
                auto_linked += 1

    if reviewed and fallback_count == reviewed:
        raise HTTPException(status_code=502, detail="OpenAI could not assess the candidate pairs. No negative matches were recorded. Check quota and model access.")
    result = {
        "candidate_pairs": candidate_count,
        "deferred_pairs": max(0, candidate_count - reviewed),
        "checked_pairs": reviewed,
        "enqueued_pairs": enqueued,
        "auto_merged_pairs": auto_merged,
        "event_cards_created": cards_made,
        "auto_linked_pairs": auto_linked,
        "fallback_pairs": fallback_count,
        "domain_bucket": bucket,
        "lookback_items": len(items),
    }
    if job_id:
        _update_job(job_id, percent=100, step="Match review completed.", status="completed", result=result)
    return result


def decide_match_review(payload: Any):
    decision = str(payload.decision or "").strip().lower()
    if decision not in {"accept", "reject", "link_update"}:
        raise HTTPException(status_code=400, detail="decision must be accept, reject or link_update")

    try:
        result = repo.apply_match_decision(payload.pair_id, decision, payload.actor)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result["collection_key"]:
        found_items = repo.list_processed_by_ids(result["item_ids"])
        repo.upsert_collection_master(_synthesize_collection_master(result["collection_key"], found_items))
    return {"updated_count": len(result["item_ids"]), "pair_id": payload.pair_id, "decision": decision}
