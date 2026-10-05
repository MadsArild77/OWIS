from datetime import datetime, timezone

import pytest

from owis.modules.news.processing import search_budget as budget

DAY = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)   # 10 days left in October


def use(purpose, n, when=DAY):
    for _ in range(n):
        budget.spend(purpose, when)


def test_automatic_searches_are_paced_over_the_month(monkeypatch):
    monkeypatch.setenv("OWI_SEARCH_MONTHLY_LIMIT", "1000")
    monkeypatch.setenv("OWI_SEARCH_RESEARCH_RESERVE", "100")
    use("policy", 600, datetime(2026, 10, 5, tzinfo=timezone.utc))
    status = budget.status(DAY)
    assert status["automatic_per_day"] == 30                     # (1000 - 100 - 600) / 10 days
    use("coverage", 30)
    assert not budget.allowed("coverage", DAY) and not budget.allowed("alternative", DAY)
    assert budget.allowed("policy", DAY) and budget.allowed("research", DAY)


def test_reserve_is_kept_for_own_research(monkeypatch):
    monkeypatch.setenv("OWI_SEARCH_MONTHLY_LIMIT", "10")
    monkeypatch.setenv("OWI_SEARCH_RESEARCH_RESERVE", "3")
    use("policy", 7)
    assert not budget.allowed("policy", DAY)
    with pytest.raises(budget.SearchBudgetExceeded):
        budget.spend("coverage", DAY)
    use("research", 3)
    assert not budget.allowed("research", DAY)
    assert budget.status(DAY)["by_purpose"] == {"alternative": 0, "coverage": 0, "policy": 7, "research": 3}


def test_new_month_resets(monkeypatch):
    monkeypatch.setenv("OWI_SEARCH_MONTHLY_LIMIT", "5")
    use("research", 5, datetime(2026, 10, 31, tzinfo=timezone.utc))
    assert budget.allowed("research", datetime(2026, 11, 1, 0, 5, tzinfo=timezone.utc))
    assert budget.status(DAY)["resets_on"] == "2026-11-01"
