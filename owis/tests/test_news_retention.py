import sqlite3
import pytest
from owis.core.storage import db
from owis.modules.news.storage.repository import NewsRepository
from owis.modules.news.processing.pipeline import process_raw_item

@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "retention.db"))
    monkeypatch.setattr("owis.modules.news.processing.pipeline.AIClient.enrich_news", lambda *args: None)
    db.init_db()
    return NewsRepository()

def add(repo, name, date):
    raw = dict(source_name="Test", article_url="https://example.com/"+name,
               title_raw="Offshore wind project", summary_raw="Norway floating wind project.",
               content_raw="Full article text.", content_hash=name,
               published_at=date, fetched_at="2026-09-23T10:00:00+00:00")
    raw_id = repo.upsert_raw_item_get_id(raw)
    processed = process_raw_item(dict(raw, id=raw_id))
    item_id = repo.save_processed_item(processed)
    repo.mark_raw_processed(raw_id)
    return raw, item_id

def test_archive_preserves_metadata_and_prevents_reingestion(repo):
    raw, item_id = add(repo, "old", "2026-05-01T00:00:00Z")
    repo.upsert_domain_classification(item_id, "offshore_wind", 0.9)
    result = repo.archive_old_unprotected_items("2026-08-24T00:00:00Z")
    assert result == dict(archived=1, deleted_processed=1, deleted_raw=1)
    assert repo.upsert_raw_item(raw) is False
    assert repo.archive_old_unprotected_items("2026-08-24T00:00:00Z")["archived"] == 0
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM news_article_archive").fetchone()
        assert row["article_url"] == raw["article_url"]
        assert row["title"] == raw["title_raw"]
        assert row["domain_bucket"] == "offshore_wind"
        assert conn.execute("SELECT COUNT(*) FROM news_domain_classification").fetchone()[0] == 0

@pytest.mark.parametrize("protection", ["relevance", "merge", "feedback", "pair", "review"])
def test_curated_articles_are_never_purged(repo, protection):
    _, item_id = add(repo, "protected", "2026-05-01T00:00:00Z")
    _, other_id = add(repo, "recent", "2026-09-22T00:00:00Z")
    if protection == "relevance": repo.set_relevance([item_id], relevance=1)
    elif protection == "merge": repo.set_collection_overrides([item_id], "manual:test")
    elif protection == "feedback": repo.log_learning_feedback("review", "keep", processed_id=item_id)
    elif protection == "pair": repo.upsert_pair_learning(item_id, other_id, "reject", "test")
    else:
        repo.upsert_match_review_pair(item_id, other_id, "no", 0.9, "different", [], "same day")
    assert repo.archive_old_unprotected_items("2026-08-24T00:00:00Z")["archived"] == 0
    assert repo.get_item(item_id)

def test_retention_compares_instants_and_keeps_unknown_dates(repo):
    add(repo, "offset", "2026-08-24T01:00:00+02:00")
    add(repo, "boundary", "2026-08-24T00:00:00Z")
    add(repo, "invalid", "not-a-date")
    assert repo.archive_old_unprotected_items("2026-08-24T00:00:00Z")["archived"] == 1
    assert repo.archive_summary() == dict(active_items=2, archived_items=1)

def test_archive_failure_rolls_back_deletions(repo):
    add(repo, "old", "2026-05-01T00:00:00Z")
    with db.get_conn() as conn:
        conn.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON news_raw_items BEGIN SELECT RAISE(ABORT, 'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        repo.archive_old_unprotected_items("2026-08-24T00:00:00Z")
    assert repo.archive_summary() == dict(active_items=1, archived_items=0)

def test_database_connection_closes_after_context(repo):
    with db.get_conn() as conn:
        conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError): conn.execute("SELECT 1")
