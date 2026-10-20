from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from owis.core.config.settings import (
    EINNSYN_NOTION_LOGG_DB_ID,
    EINNSYN_NOTION_SAKER_DB_ID,
    EINNSYN_NOTION_SOK_DB_ID,
    NOTION_API_KEY,
    NOTION_VERSION,
)
from owis.modules.einnsyn import big_picture, case_accounts, case_chat, links
from owis.modules.einnsyn.case_source import CaseSource
from owis.modules.einnsyn.notion_reader import EinnsynNotionReader, OverviewCache

router = APIRouter(prefix="/api/einnsyn", tags=["einnsyn"])
reader = EinnsynNotionReader(NOTION_API_KEY, EINNSYN_NOTION_SAKER_DB_ID, EINNSYN_NOTION_LOGG_DB_ID,
                             EINNSYN_NOTION_SOK_DB_ID, NOTION_VERSION)
cache = OverviewCache(reader)
cases = CaseSource()
document_texts = case_chat.DocumentTexts()


@router.get("/overview")
def overview(refresh: bool = False, project: str = "", theme: str = ""):
    if not reader.configured():
        raise HTTPException(
            status_code=503,
            detail="eInnsyn is not configured. Set NOTION_API_KEY and OWI_EINNSYN_SAKER_DB_ID, "
                   "OWI_EINNSYN_LOGG_DB_ID and OWI_EINNSYN_SOK_DB_ID, and share the three Notion "
                   "databases with the integration.",
        )
    try:
        return cache.get(refresh=refresh, project=project.strip(), theme=theme.strip())
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
    ctx = big_picture.context(case, _saker())
    case["related_news"], case["project_cases"], case["projects"] = ctx["news"], ctx["cases"], ctx["projects"]
    case["big_picture"] = big_picture.stored(case, ctx)
    return case


def _saker() -> list[dict]:
    """Case rows from the Notion cache, or none when Notion is not set up or not reachable."""
    if not reader.configured():
        return []
    try:
        return cache.saker()
    except Exception:
        return []


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


@router.post("/case/big-picture")
def case_big_picture(payload: AccountRequest):
    """Write the big picture: the case together with its news and the other cases on the same project."""
    case = _load_case(payload.ref)
    ctx = big_picture.context(case, _saker())
    if not (ctx["news"] or ctx["cases"]):
        raise HTTPException(status_code=404, detail="No news or other cases on this project to put the case in context.")
    result = big_picture.write(case, ctx, case_accounts.stored(case))
    if not result:
        raise HTTPException(status_code=503, detail="The big picture could not be written now (is AI enabled?).")
    return result


class KeywordStatusRequest(BaseModel):
    id: str
    active: bool


@router.post("/keywords/status")
def keyword_status(payload: KeywordStatusRequest):
    """Turn a search term or a suggested search term on (Aktiv) or off (Pause) in Notion.
    The eInnsyn monitor uses the change from its next run."""
    if not reader.configured():
        raise HTTPException(status_code=503, detail="eInnsyn is not configured.")
    try:
        cache.get()
        status = cache.set_keyword_status(payload.id, payload.active)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such search term. Refresh the page and try again.")
    except Exception as exc:  # Notion down, or the integration may not edit the database
        raise HTTPException(status_code=502, detail=f"Notion did not accept the change: {exc}")
    return {"id": payload.id, "status": status}


@router.get("/related")
def related_cases(item_ids: list[int] = Query(default=[])):
    """eInnsyn cases naming the projects or companies of these news items (for the news page)."""
    saker = _saker() if item_ids else []
    return {"items": links.cases_for_news(item_ids, saker) if saker else []}


class ChatRequest(BaseModel):
    ref: str
    question: str


@router.get("/case/chat")
def case_chat_history(ref: str):
    """The stored conversation about a case."""
    from owis.modules.einnsyn.case_source import case_ref
    return {"messages": case_chat.conversation(case_ref(ref))}


@router.post("/case/chat")
def case_chat_answer(payload: ChatRequest):
    """Answer a question about the case from its journal posts, the most relevant open documents and the
    conversation so far; the question and answer are stored with the case."""
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Ask a question.")
    case = dict(_load_case(payload.ref))
    case["account"] = case_accounts.stored(case)
    case["related_news"] = links.news_for_case(case)
    result = case_chat.answer(case, payload.question, document_texts)
    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@router.delete("/case/chat")
def case_chat_clear(ref: str):
    from owis.modules.einnsyn.case_source import case_ref
    case_chat.forget(case_ref(ref))
    return {"ok": True}
