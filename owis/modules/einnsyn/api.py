from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from owis.core.config.settings import (
    EINNSYN_NOTION_LOGG_DB_ID,
    EINNSYN_NOTION_SAKER_DB_ID,
    EINNSYN_NOTION_SOK_DB_ID,
    NOTION_API_KEY,
    NOTION_VERSION,
)
from owis.modules.einnsyn import big_picture, case_accounts, case_chat, feedback, links, project_view, public_sources
from owis.modules.einnsyn.case_source import CaseSource
from owis.modules.einnsyn.notion_reader import PROJECT_FIELD, THEME_FIELD, EinnsynNotionReader, OverviewCache, _tags

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
    saker, sok = notion_rows()
    ctx = big_picture.context(case, saker, sok)
    case["related_news"], case["project_cases"], case["projects"] = ctx["news"], ctx["cases"], ctx["projects"]
    case["public_records"] = ctx["public"]
    case["feedback"] = feedback.public(ctx["feedback"])
    case["big_picture"] = big_picture.stored(case, ctx)
    return case


def _saker() -> list[dict]:
    return notion_rows()[0]


def notion_rows() -> tuple[list[dict], list[dict]]:
    """Case and search-term rows from the Notion cache, or none when Notion is not set up or not reachable."""
    if not reader.configured():
        return [], []
    try:
        return cache.saker(), cache.sok()
    except Exception:
        return [], []


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
    ctx = big_picture.context(case, *notion_rows())
    if not (ctx["news"] or ctx["cases"] or ctx["public"]):
        raise HTTPException(status_code=404, detail="No news, Storting records or other cases on this project to put the case in context.")
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


def _notion_data() -> dict:
    if not reader.configured():
        raise HTTPException(status_code=503, detail="eInnsyn is not configured.")
    try:
        return cache.data()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read eInnsyn data from Notion: {exc}")


@router.get("/project")
def project_overview(project: str = "", theme: str = ""):
    """The helicopter view for a project, theme or all projects: the stored overview (if any) and the timeline of
    journal posts, news, Storting records and the minister's calendar."""
    m = project_view.material(_notion_data(), project.strip(), theme.strip())
    return {"view": project_view.stored(m), "timeline": project_view.timeline(m),
            "counts": {"cases": len(m["cases"]), "journal_posts": len(m["posts"]), "news": len(m["news"]),
                       "public": len(m["public"])},
            "portfolio": not (project.strip() or theme.strip()),
            "scope": list(project_view.scope(project.strip(), theme.strip())), "feedback": feedback.public(m["feedback"])}


class ProjectRequest(BaseModel):
    project: str = ""
    theme: str = ""


@router.post("/project/view")
def project_view_write(payload: ProjectRequest):
    """Write the helicopter view now, when it is missing or older than its material."""
    m = project_view.material(_notion_data(), payload.project.strip(), payload.theme.strip())
    view = project_view.write(m)
    if not view:
        raise HTTPException(status_code=503, detail="The overview could not be written now (is AI enabled, and is there material?).")
    return view


# ---- The reader's corrections (see feedback.py) ----

class InterpretRequest(BaseModel):
    target_type: str
    label: str = ""
    context: str = ""
    text: str


@router.post("/feedback/interpret")
def feedback_interpret(payload: InterpretRequest):
    """What the AI understands the reader to mean. Nothing is stored until the reader confirms."""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Write what is wrong first.")
    try:
        return feedback.interpret(payload.model_dump(), payload.text.strip())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc) or "The correction could not be interpreted now.")


class FeedbackRequest(BaseModel):
    scope_type: str
    scope_id: str = ""
    target_type: str
    target_id: str = ""
    target_label: str = ""
    action: str
    text: str = ""
    correction: str = ""


@router.post("/feedback")
def feedback_save(payload: FeedbackRequest):
    """Store a confirmed correction or a «not relevant» mark."""
    try:
        saved = feedback.save(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return saved | {"items": feedback.public(feedback.for_scopes([(payload.scope_type, payload.scope_id)]))}


@router.get("/feedback")
def feedback_list(scope_type: str, scope_id: str = ""):
    return {"items": feedback.public(feedback.for_scopes([(scope_type, scope_id)]))}


@router.delete("/feedback/{feedback_id}")
def feedback_remove(feedback_id: int):
    feedback.remove(feedback_id)
    return {"ok": True}


class CaseStatusRequest(BaseModel):
    ref: str
    status: str


@router.post("/case/status")
def case_status(payload: CaseStatusRequest):
    """Mark a case «Ikke relevant» (or back to «Aktiv») in Notion; the eInnsyn monitor stops following it."""
    from owis.modules.einnsyn.case_source import case_ref
    if payload.status not in ("Ikke relevant", "Aktiv"):
        raise HTTPException(status_code=400, detail="Status must be «Ikke relevant» or «Aktiv».")
    ref = case_ref(payload.ref)
    row = next((r for r in _saker() if r.get("URL") and case_ref(r["URL"]) == ref), None)
    if not row:
        raise HTTPException(status_code=404, detail="This case is not in the Notion case list.")
    try:
        cache.set_case_status(row["_id"], payload.status)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Notion did not accept the change: {exc}")
    return {"status": payload.status}


@router.get("/public")
def public_records(project: str = "", theme: str = ""):
    """Storting records and the minister's calendar for the selection, with when each source last ran."""
    saker, sok = notion_rows()
    if project and public_sources._norm_project(project) not in public_sources.BROAD_PROJECTS:
        wanted = [project]
    elif theme:  # the projects of the theme's cases
        wanted = sorted({p for r in saker if theme in _tags(r, THEME_FIELD) for p in _tags(r, PROJECT_FIELD)})
    else:
        wanted = None
    # The reader's «not relevant» marks for this selection (and for everything)
    skip = feedback.excluded(feedback.for_scopes([project_view.scope(project.strip(), theme.strip())]))
    items = [i for i in public_sources.items(saker, sok, projects=wanted) if i["id"] not in skip]
    if project and wanted is None:  # «Generelt» or «Uklassifisert»: the records naming no project
        items = [i for i in items if not i["projects"]]
    return {"items": items[:300], "total": len(items), "runs": public_sources.runs()}


@router.post("/public/refresh")
def public_refresh():
    """Fetch the Storting and the minister's calendar now, in the background."""
    saker, sok = notion_rows()
    if not (saker or sok):
        raise HTTPException(status_code=503, detail="The Notion data is needed first (project areas and search terms).")
    import threading
    threading.Thread(target=public_sources.refresh, args=(saker, sok), daemon=True).start()
    return {"started": True, "runs": public_sources.runs()}


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
    case["corrections"] = feedback.corrections(feedback.for_scopes([("case", case["ref"])]))
    result = case_chat.answer(case, payload.question, document_texts)
    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@router.delete("/case/chat")
def case_chat_clear(ref: str):
    from owis.modules.einnsyn.case_source import case_ref
    case_chat.forget(case_ref(ref))
    return {"ok": True}
