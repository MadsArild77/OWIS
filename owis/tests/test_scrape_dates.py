from datetime import datetime, timezone

import pytest

from owis.core.storage import db
from owis.modules.news.collectors import dates
from owis.modules.news.collectors.filters import is_probable_article_url
from owis.modules.news.storage.repository import NewsRepository

NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "dates.db"))
    db.init_db()


def raw(url, published=None):
    return dict(source_name="Europower", article_url=url, title_raw="Vindkraft", summary_raw="", content_raw="",
                content_hash=url, fetched_at=NOW, published_at=published)


def test_new_scraped_articles_get_their_time_from_the_page():
    pages = []
    def preview(url, title, summary):
        pages.append(url)
        return {"published_at": "2026-10-13T12:08:57+00:00", "description": "Ingress.", "image_url": "https://img"}
    NewsRepository().upsert_raw_item(raw("https://europower.com/known"))
    items = [raw("https://europower.com/new"), raw("https://europower.com/known"), raw("https://e.com/dated", "2026-10-12T08:00:00+00:00")]
    assert dates.fill_new(items, preview) == 1
    assert pages == ["https://europower.com/new"]          # stored and already dated articles are not read
    assert items[0]["published_at"] == "2026-10-13T12:08:57+00:00" and items[0]["summary_raw"] == "Ingress."


def test_stored_undated_articles_are_filled_once():
    repo = NewsRepository()
    repo.upsert_raw_item(raw("https://europower.com/a"))
    repo.upsert_raw_item(raw("https://windtech.com/blog-index"))
    answers = {"https://europower.com/a": "2026-10-13T09:27:48+00:00"}
    calls = []
    def preview(url, title, summary):
        calls.append(url)
        return {"published_at": answers.get(url, "")}
    assert dates.backfill(preview) == 1
    assert dates.backfill(preview) == 0 and len(calls) == 2  # a page without a time is not read again
    with db.get_conn() as c:
        assert c.execute("SELECT published_at FROM news_raw_items WHERE article_url='https://europower.com/a'").fetchone()[0].startswith("2026-10-13")


def test_blog_index_pages_are_not_articles():
    assert not is_probable_article_url("https://www.windtechinternational.com/editorial-features/articles/blog")
