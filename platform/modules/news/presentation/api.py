from fastapi import APIRouter, HTTPException

from platform.modules.news.storage.repository import NewsRepository

router = APIRouter(prefix="/api/news", tags=["news"])
repo = NewsRepository()


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
