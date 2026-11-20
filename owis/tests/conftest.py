import pytest


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Tests never start background collection and never touch the real database."""
    from owis.core.storage import db
    monkeypatch.setenv("OWI_SCHEDULED_FETCH_ENABLED", "false")
    monkeypatch.setenv("OWI_OPP_SCHEDULED_FETCH_ENABLED", "false")
    # Policy-search tests use fixed dates on any weekday; the weekly default has its own test.
    monkeypatch.setenv("OWI_POLICY_SEARCH_WEEKDAYS", "0,1,2,3,4,5,6")
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "isolated.db"))
    db.init_db()
