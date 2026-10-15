from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from owis.core.config.settings import (
    EINNSYN_NOTION_LOGG_DB_ID,
    EINNSYN_NOTION_SAKER_DB_ID,
    EINNSYN_NOTION_SOK_DB_ID,
    NOTION_API_KEY,
    NOTION_VERSION,
)
from owis.modules.einnsyn import case_accounts, links
from owis.modules.einnsyn.case_source import CaseSource
from owis.modules.einnsyn.notion_reader import EinnsynNotionReader, OverviewCache

router = APIRouter(prefix="/api/einnsyn", tags=["einnsyn"])
reader = EinnsynNotionReader(NOTION_API_KEY, EINNSYN_NOTION_SAKER_DB_ID, EINNSYN_NOTION_LOGG_DB_ID,
                             EINNSYN_NOTION_SOK_DB_ID, NOTION_VERSION)
cache = OverviewCache(reader)
cases = CaseSource()


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


def _load_case(ref: str) -> dict:
    try:
        case = cases.case(ref)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read the case from eInnsyn: {exc}")
    if not case:
        raise HTTPException(status_code=404, detail="eInnsyn has no case with this id; it may have been removed.")
    return case


@router.get("/case")
def case_detail(ref: str):
    """One case from eInnsyn: journal posts, open documents, the written account if any, related news."""
    case = dict(_load_case(ref))
    case["account"] = case_accounts.stored(case)
    case["related_news"] = links.news_for_case(case)
    return case


class AccountRequest(BaseModel):
    ref: str


@router.post("/case/account")
def case_account(payload: AccountRequest):
    """Write the case's account now, when it is opened without an up-to-date one."""
    case = _load_case(payload.ref)
    account = case_accounts.write(case)
    if not account:
        raise HTTPException(status_code=503, detail="The account could not be written now (is AI enabled?).")
    return account


@router.get("/related")
def related_cases(item_ids: list[int] = Query(default=[])):
    """eInnsyn cases naming the projects or companies of these news items (for the news page)."""
    if not item_ids or not reader.configured():
        return {"items": []}
    try:
        saker = cache.saker()
    except Exception:
        return {"items": []}
    return {"items": links.cases_for_news(item_ids, saker)}
