from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from owis.core.storage.db import init_db
from owis.modules.news.presentation.api import router as news_router
from owis.modules.opportunities.presentation.api import router as opportunities_router

app = FastAPI(title="Offshore Wind Intelligence API", version="0.1.0")
app.include_router(news_router)
app.include_router(opportunities_router)

web_dir = Path("owis/apps/web")
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.on_event("startup")
def on_startup() -> None:
    import os
    from datetime import datetime, timezone
    from owis.core.storage import db
    from owis.scripts.backup_database import backup
    database=Path(db.DB_PATH).resolve()
    if os.getenv('RAILWAY_ENVIRONMENT_ID'):
        mount=os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
        if not mount or not database.is_relative_to(Path(mount).resolve()):
            raise RuntimeError('Railway requires a persistent volume containing OWI_DB_PATH before starting OWIS.')
    if database.exists() and database.stat().st_size:
        destination=database.parent/'backups'/f"startup-{datetime.now(timezone.utc):%Y-%m-%d}.db"
        if not destination.exists():backup(destination)
    init_db()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/news")


@app.get("/news", include_in_schema=False)
def news_page():
    return FileResponse(web_dir / "news.html")


@app.get("/opportunities", include_in_schema=False)
def opportunities_page():
    return FileResponse(web_dir / "opportunities.html")


@app.get("/health")
def health():
    return {"ok": True}
