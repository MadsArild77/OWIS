from owis.core.storage import db
from owis.modules.opportunities.storage.repository import OpportunitiesRepository


def test_opportunity_upsert_deduplicates_notice_id(tmp_path, monkeypatch):
    db_path = tmp_path / "opportunities.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    db.init_db()
    repo = OpportunitiesRepository()

    item = {
        "id": "TED-2026-123",
        "source": "TED",
        "url": "https://ted.europa.eu/en/notice/-/detail/2026-123",
        "title": "Offshore cable route survey tender",
        "buyer": "Example Authority",
        "country": "NOR",
        "publication_date": "2026-03-08",
        "description": "Offshore survey tender for cable route.",
        "cpv_codes": ["71354500"],
        "fetched_at": "2026-03-08T10:00:00Z",
    }

    assert repo.upsert_raw_item(item) is True
    assert repo.upsert_raw_item(item) is False