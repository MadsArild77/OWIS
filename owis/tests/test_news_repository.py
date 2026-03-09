from owis.core.storage import db
from owis.modules.news.storage.repository import NewsRepository


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



def test_domain_and_match_review_lifecycle(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    db.init_db()
    repo = NewsRepository()

    item_a = {
        "source_name": "TestFeed",
        "article_url": "https://example.com/a2",
        "title_raw": "Offshore wind policy update",
        "summary_raw": "Policy update in Norway",
        "content_raw": "Long enough content for storage",
        "content_hash": "abc124",
        "published_at": "2026-03-08T10:00:00Z",
        "fetched_at": "2026-03-08T10:01:00Z",
    }
    item_b = {
        "source_name": "TestFeed",
        "article_url": "https://example.com/a3",
        "title_raw": "Norway offshore wind policy announced",
        "summary_raw": "Similar policy story",
        "content_raw": "Another long text",
        "content_hash": "abc125",
        "published_at": "2026-03-08T12:00:00Z",
        "fetched_at": "2026-03-08T12:01:00Z",
    }

    assert repo.upsert_raw_item(item_a) is True
    assert repo.upsert_raw_item(item_b) is True

    raws = repo.list_unprocessed_raw(limit=5)
    assert len(raws) == 2

    first = raws[0]
    second = raws[1]

    id_a = repo.save_processed_item(
        {
            "raw_item_id": first["id"],
            "title": "A",
            "cleaned_text": "A",
            "summary": "A",
            "theme_tags": "policy",
            "geography_tags": "Norway",
            "actors": "",
            "why_it_matters": "A",
            "signal_score": 80,
            "confidence": 0.8,
            "linkedin_angle": "A",
            "linkedin_candidate": 1,
            "processed_at": "2026-03-08T12:02:00Z",
        }
    )
    id_b = repo.save_processed_item(
        {
            "raw_item_id": second["id"],
            "title": "B",
            "cleaned_text": "B",
            "summary": "B",
            "theme_tags": "policy",
            "geography_tags": "Norway",
            "actors": "",
            "why_it_matters": "B",
            "signal_score": 81,
            "confidence": 0.81,
            "linkedin_angle": "B",
            "linkedin_candidate": 1,
            "processed_at": "2026-03-08T12:03:00Z",
        }
    )

    repo.upsert_domain_classification(id_a, "offshore_wind", 0.9)
    repo.upsert_domain_classification(id_b, "offshore_wind", 0.91)

    pair_id = repo.upsert_match_review_pair(
        item_a_id=id_a,
        item_b_id=id_b,
        ai_same_story="yes",
        ai_confidence=0.88,
        reason_short="same policy announcement",
        overlap_entities=["Norway"],
        overlap_timeframe="same day",
    )

    pairs = repo.list_match_review_pairs(status="pending", domain_bucket="offshore_wind", limit=10)
    assert pairs
    assert any(int(p["id"]) == int(pair_id) for p in pairs)

    updated = repo.decide_match_review_pair(pair_id=pair_id, decision="accept", actor="tester")
    assert updated == 1

    repo.log_learning_feedback(
        feedback_type="match_review_decision",
        feedback_value="accept",
        pair_id=pair_id,
        actor="tester",
    )
