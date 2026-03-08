from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from owis.core.storage.db import init_db
from owis.modules.news.presentation.api import router as news_router

app = FastAPI(title="Offshore Wind Intelligence API", version="0.1.0")
app.include_router(news_router)

web_dir = Path("owis/apps/web")
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/news")


@app.get("/news", include_in_schema=False)
def news_page():
    return FileResponse(web_dir / "news.html")


@app.get("/health")
def health():
    return {"ok": True}


