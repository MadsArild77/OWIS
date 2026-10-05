import pytest


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Tests never start background collection and never touch the real database."""
    from owis.core.storage import db
    monkeypatch.setenv("OWI_SCHEDULED_FETCH_ENABLED", "false")
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "isolated.db"))
    db.init_db()
