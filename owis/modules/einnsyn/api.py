from fastapi import APIRouter, HTTPException

from owis.core.config.settings import (
    EINNSYN_NOTION_LOGG_DB_ID,
    EINNSYN_NOTION_SAKER_DB_ID,
    EINNSYN_NOTION_SOK_DB_ID,
    NOTION_API_KEY,
    NOTION_VERSION,
)
from owis.modules.einnsyn.notion_reader import EinnsynNotionReader, OverviewCache

router = APIRouter(prefix="/api/einnsyn", tags=["einnsyn"])
reader = EinnsynNotionReader(NOTION_API_KEY, EINNSYN_NOTION_SAKER_DB_ID, EINNSYN_NOTION_LOGG_DB_ID,
                             EINNSYN_NOTION_SOK_DB_ID, NOTION_VERSION)
cache = OverviewCache(reader)


@router.get("/overview")
def overview(refresh: bool = False):
    if not reader.configured():
        raise HTTPException(
            status_code=503,
            detail="eInnsyn is not configured. Set NOTION_API_KEY and OWI_EINNSYN_SAKER_DB_ID, "
                   "OWI_EINNSYN_LOGG_DB_ID and OWI_EINNSYN_SOK_DB_ID, and share the three Notion "
                   "databases with the integration.",
        )
    try:
        return cache.get(refresh=refresh)
    except Exception as exc:  # Notion down or not shared: show the reason on the page
        raise HTTPException(status_code=502, detail=f"Could not read eInnsyn data from Notion: {exc}")
