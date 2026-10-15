from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from owis.core.config.settings import (
    EINNSYN_NOTION_LOGG_DB_ID,
    EINNSYN_NOTION_SAKER_DB_ID,
    EINNSYN_NOTION_SOK_DB_ID,
    NOTION_API_KEY,
    NOTION_VERSION,
)
from owis.modules.einnsyn import case_accounts, case_chat, links
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
