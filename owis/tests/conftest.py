import pytest


@pytest.fixture(autouse=True)
def no_scheduled_fetch(monkeypatch):
    """Tests must never start real background collection."""
    monkeypatch.setenv("OWI_SCHEDULED_FETCH_ENABLED", "false")
