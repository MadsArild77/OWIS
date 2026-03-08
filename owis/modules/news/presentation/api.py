from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from owis.modules.news.registry.source_discovery import import_sources_from_text, load_source_registry
from owis.modules.news.storage.repository import NewsRepository

router = APIRouter(prefix="/api/news", tags=["news"])
repo = NewsRepository()


class ImportSourcesRequest(BaseModel):
    text: str

@router.get("/latest")
def latest(limit: int = 20):
    return repo.latest(limit)


@router.get("/top-signals")
def top_signals(limit: int = 20):
    return repo.top_signals(limit)


@router.get("/linkedin-candidates")
def linkedin_candidates(limit: int = 20):
    return repo.linkedin_candidates(limit)


@router.get("/item/{item_id}")
def item(item_id: int):
    found = repo.get_item(item_id)
    if not found:
        raise HTTPException(status_code=404, detail="News item not found")
    return found

@router.get("/sources")
def list_sources():
    return load_source_registry()


@router.post("/sources/import-text")
def import_sources(payload: ImportSourcesRequest):
    added = import_sources_from_text(payload.text)
    return {"added_count": len(added), "added": added}

