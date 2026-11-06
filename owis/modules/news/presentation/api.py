from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from owis.core.llm.client import AIClient
from owis.core.storage.db import init_db
from owis.modules.news.registry.source_discovery import dedupe_sources, delete_source, import_sources_from_text, load_source_registry, rediscover_rss_for_sources, set_source_enabled, source_health_report, update_source
from owis.modules.news.storage.repository import NewsRepository
from owis.modules.news.processing import jobs, collections, match_review, item_view, fetch_process, retention


router = APIRouter(prefix="/api/news", tags=["news"])


repo = NewsRepository()


class ImportSourcesRequest(BaseModel):
    text: str


class ToggleSourceRequest(BaseModel):
    index: int
    enabled: bool


class DeleteSourceRequest(BaseModel):
    index: int


class RediscoverRSSRequest(BaseModel):
    only_scrape: bool = True
    with_debug: bool = False


class SourceHealthRequest(BaseModel):
    only_enabled: bool = True


class RunFetchProcessRequest(BaseModel):
    days_back: int = 7
    # Ignored: articles already stored are always skipped (by URL). A global "newest
    # article" cut-off dropped date-only and late-listed stories from slower sources.
    since_last: bool = False


class UpdateSourceRequest(BaseModel):
    index: int
    name: str | None = None
    homepage: str | None = None
    type: str | None = None
    url: str | None = None
    enabled: bool | None = None
    priority: str | None = None
    interest_topic: str | None = None
    geography_tags: list[str] | None = None
    auth: dict[str, object] | None = None
    manual_override: bool | None = None


class MergeCollectionRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)
    collection_key: str | None = None
    note: str | None = None


class UnmergeCollectionRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)


class UpdateRelevanceRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)
    relevance: str | None = None
    qualified: bool | None = None


class MatchRunRequest(BaseModel):
    lookback_items: int = Field(default=350, ge=2, le=1000)
    days_window: int = Field(default=30, ge=1, le=365)
    top_k: int = Field(default=8, ge=1, le=20)
    domain_bucket: str = "core"
    auto_apply: bool = True


class MatchReviewDecisionRequest(BaseModel):
    pair_id: int
    decision: str
    actor: str | None = None


class StartJobRequest(BaseModel):
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RetentionRunRequest(BaseModel):
    days: int | None = None
    limit: int = 1000


@router.get("/latest")
def latest(limit: int = 20, source_name: str | None = None, domain_bucket: str = "offshore_wind"):
    return item_view.latest(limit=limit, source_name=source_name, domain_bucket=domain_bucket)


@router.get("/top-signals")
def top_signals(limit: int = 20, source_name: str | None = None, domain_bucket: str = "offshore_wind"):
    return item_view.top_signals(limit=limit, source_name=source_name, domain_bucket=domain_bucket)


@router.get("/linkedin-candidates")
def linkedin_candidates(limit: int = 20, source_name: str | None = None, domain_bucket: str = "offshore_wind"):
    return item_view.linkedin_candidates(limit=limit, source_name=source_name, domain_bucket=domain_bucket)


@router.post("/items/relevance")
def update_item_relevance(payload: UpdateRelevanceRequest):
    return item_view.update_item_relevance(payload=payload)


@router.post("/items/qualification")
def update_item_qualification(payload: UpdateRelevanceRequest):
    return item_view.update_item_relevance(payload)


@router.get("/item/{item_id}")
def item(item_id: int):
    return item_view.item(item_id=item_id)


class EditorialRequest(BaseModel):
    topic: str = 'all'
    value: str
    reason: str = ''


@router.post('/item/{item_id}/feedback')
def editorial_feedback(item_id: int, payload: EditorialRequest):
    from owis.modules.news.processing.editorial import record
    try:
        result=record(item_id,payload.topic,payload.value,payload.reason)
        if payload.value=='relevant':result['enrichment_job_id']=jobs._create_job('enrich_one',{'item_id':item_id})
        return result
    except LookupError as ex:raise HTTPException(404,str(ex))
    except ValueError as ex:raise HTTPException(400,str(ex))


@router.post('/feedback/{event_id}/undo')
def undo_editorial_feedback(event_id: int):
    from owis.modules.news.processing.editorial import undo
    try:return undo(event_id)
    except LookupError as ex:raise HTTPException(404,str(ex))
    except ValueError as ex:raise HTTPException(409,str(ex))


@router.get('/feedback/history')
def editorial_history(limit: int = 100):
    return item_view.editorial_history(limit=limit)


class FeedbackReason(BaseModel):
    reason: str


@router.post('/feedback/{event_id}/reason')
def editorial_reason(event_id: int, payload: FeedbackReason):
    return item_view.editorial_reason(event_id=event_id, payload=payload)


@router.post('/item/{item_id}/enrich')
def enrich_article(item_id: int, refresh: bool = False):
    return item_view.enrich_article(item_id=item_id, refresh=refresh)


@router.get('/morning-report/history')
def morning_report_history():
    from owis.modules.news.processing import morning
    return morning.history()


@router.get('/ops-report')
def ops_report(days: int = Query(default=30, ge=1, le=366)):
    from owis.modules.news.processing.ops_report import read_report
    return read_report(days=days)


@router.get('/morning-report')
def morning_report(report_date: str | None = None):
    from owis.modules.news.processing import morning
    if report_date:
        from datetime import date
        try:
            report_date = date.fromisoformat(report_date).isoformat()
        except ValueError:
            raise HTTPException(400, 'Use YYYY-MM-DD for report_date')
    return morning.read(report_date)


@router.post('/morning-report')
def generate_morning_report(refresh: bool = False):
    from owis.modules.news.processing import morning
    try:
        return morning.start(refresh=refresh)
    except ValueError as ex:
        raise HTTPException(409, str(ex))


@router.get('/researched')
def researched_stories():
    """User's research history, independent of feed filters and retention windows."""
    return item_view.researched_stories()


@router.get('/item/{item_id}/research')
def read_story_research(item_id: int):
    from owis.modules.news.processing import research
    if not repo.get_item(item_id):
        raise HTTPException(404, 'Article not found')
    return research.read(item_id)


@router.post('/item/{item_id}/research')
def start_story_research(item_id: int, refresh: bool = False):
    from owis.modules.news.processing import research
    try:
        return research.start(item_id, refresh=refresh)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))


@router.post('/item/{item_id}/draft')
def editorial_draft(item_id: int):
    return item_view.editorial_draft(item_id=item_id)


@router.get('/item/{item_id}/thread')
def article_thread(item_id: int):
    """Other stories about the same project (from event cards), newest first."""
    from owis.modules.news.processing.threads import thread_for
    if not repo.get_item(item_id):raise HTTPException(404,'Article not found')
    return thread_for(item_id)


@router.get('/item/{item_id}/sources')
def article_sources(item_id: int):
    return item_view.article_sources(item_id=item_id)


class SourceAdviceDecision(BaseModel):
    key: str
    decision: str


@router.get('/search-budget')
def search_budget_status():
    from owis.modules.news.processing.search_budget import status
    init_db()
    return status()


@router.get('/source-advisor')
def source_advisor():
    from owis.modules.news.registry.source_advisor import advice
    from owis.modules.news.processing.fulltext import summary
    init_db()
    return {**advice(), 'fulltext': summary()}


@router.post('/source-advisor/decision')
def source_advisor_decision(payload: SourceAdviceDecision):
    from owis.modules.news.registry.source_advisor import record_decision
    try:
        if payload.decision == "undo":
            from owis.modules.news.registry.source_advisor import undo_decision
            undo_decision(payload.key[:300])
        else:
            record_decision(payload.key[:300], payload.decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved": True}


@router.get('/sources/saved')
def saved_source_evidence():
    return item_view.saved_source_evidence()


@router.get("/item/{item_id}/preview")
def item_preview(item_id: int):
    return item_view.item_preview(item_id=item_id)


@router.get("/collections")
def list_collections(
    limit: int = 20,
    items_per_collection: int = 5,
    lookback_items: int = 400,
    source_name: str | None = None,
    domain_bucket: str = "offshore_wind",
):
    return collections.list_collections(limit=limit, items_per_collection=items_per_collection, lookback_items=lookback_items, source_name=source_name, domain_bucket=domain_bucket)


class CaseAccountRequest(BaseModel):
    signature: str
    domain_bucket: str = "core"


@router.post("/cases/account")
def case_account(payload: CaseAccountRequest):
    """Write a case's account now, when it is opened without one (otherwise it waits for the next fetch)."""
    return collections.case_account(payload=payload)


@router.post("/collections/merge")
def merge_collections(payload: MergeCollectionRequest):
    return collections.merge_collections(payload=payload)


@router.post("/collections/unmerge")
def unmerge_collections(payload: UnmergeCollectionRequest):
    return collections.unmerge_collections(payload=payload)


@router.post("/match/run")
def run_match_review(payload: MatchRunRequest):
    return match_review._run_match_review(payload)


@router.get("/story-links")
def story_links():
    return {"items": repo.list_story_links()}


@router.get("/match-review")
def list_match_review(status: str = "pending", domain_bucket: str = "offshore_wind", limit: int = 30):
    if status not in {"pending", "accepted", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    bucket = item_view._normalize_domain_bucket(domain_bucket)
    items = repo.list_match_review_pairs(status=status, domain_bucket=bucket, limit=limit)
    return {"items": items}


@router.post("/match-review/decide")
def decide_match_review(payload: MatchReviewDecisionRequest):
    return match_review.decide_match_review(payload=payload)


@router.get("/sources")
def list_sources():
    return [{"index": i, **s} for i, s in enumerate(load_source_registry())]


@router.post("/sources/import-text")
def import_sources(payload: ImportSourcesRequest):
    added = import_sources_from_text(payload.text)
    return {"added_count": len(added), "added": added}


@router.post("/sources/toggle")
def toggle_source(payload: ToggleSourceRequest):
    updated = set_source_enabled(payload.index, payload.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated


@router.post("/sources/delete")
def remove_source(payload: DeleteSourceRequest):
    removed = delete_source(payload.index)
    if not removed:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"removed": removed}


@router.post("/sources/update")
def edit_source(payload: UpdateSourceRequest):
    updates = payload.model_dump(exclude_none=True)
    index = updates.pop("index")
    updated = update_source(index=index, updates=updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated


@router.post("/sources/dedupe")
def run_dedupe():
    return dedupe_sources()


@router.post("/sources/rediscover-rss")
def rediscover_rss(payload: RediscoverRSSRequest):
    return rediscover_rss_for_sources(only_scrape=payload.only_scrape, with_debug=payload.with_debug)


@router.post("/sources/health")
def source_health(payload: SourceHealthRequest):
    return {"items": source_health_report(only_enabled=payload.only_enabled)}


@router.get("/sources/history")
def source_history(source_url: str | None = None, limit: int = 100):
    from owis.modules.news.storage.source_events import list_events
    return {"items": list_events(source_url, limit)}


@router.get("/sources/health-state")
def source_health_state():
    return {"items": repo.list_source_health_states()}


@router.post("/jobs/start")
def start_news_job(payload: StartJobRequest):
    operation = str(payload.operation or "").strip()
    allowed = {"enrich_backfill", "fetch_process", "rediscover_rss", "source_health", "match_review", "retention_archive"}
    if operation not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported operation: {operation}")
    request_factory = {"fetch_process": RunFetchProcessRequest, "match_review": MatchRunRequest,
                       "retention_archive": RetentionRunRequest}.get(operation)
    job_id = jobs._create_job(operation, payload.payload or {}, request_factory=request_factory)
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_news_job(job_id: str):
    return jobs._job_snapshot(job_id)


@router.get("/ai/status")
def ai_status(probe: bool = False):
    ai = AIClient()
    return ai.status(with_probe=bool(probe))


@router.post("/retention/archive")
def retention_archive(payload: RetentionRunRequest):
    return retention._run_retention_archive(payload)


@router.get("/retention/summary")
def retention_summary():
    days, cutoff = retention._retention_cutoff()
    return {**repo.archive_summary(), "retention_days": days, "cutoff": cutoff}


@router.post("/run/fetch-process")
def run_fetch_process(payload: RunFetchProcessRequest):
    return fetch_process._run_fetch_process(payload)
