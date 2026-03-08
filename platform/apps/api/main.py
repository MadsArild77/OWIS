from fastapi import FastAPI

from platform.core.storage.db import init_db
from platform.modules.news.presentation.api import router as news_router

app = FastAPI(title="Offshore Wind Intelligence API", version="0.1.0")
app.include_router(news_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"ok": True}
