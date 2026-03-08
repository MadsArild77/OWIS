from platform.core.storage import db
from platform.modules.news.storage.repository import NewsRepository


def test_upsert_deduplicates_article_url(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    db.init_db()
    repo = NewsRepository()

    item = {
        "source_name": "TestFeed",
        "article_url": "https://example.com/a1",
        "title_raw": "Test title",
        "summary_raw": "Test summary",
        "content_raw": "Test content",
        "content_hash": "abc123",
        "published_at": "2026-03-08T10:00:00Z",
        "fetched_at": "2026-03-08T10:01:00Z",
    }

    assert repo.upsert_raw_item(item) is True
    assert repo.upsert_raw_item(item) is False
