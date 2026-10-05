from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from owis.core.storage import db
from owis.modules.news.matching import service
from owis.modules.news.processing import coverage, research

NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "coverage.db"))
    db.init_db()
    monkeypatch.setenv("TAVILY_API_KEY", "test")
    monkeypatch.setattr(coverage, "AIClient", lambda: SimpleNamespace(enabled=True))
    with db.get_conn() as c:
        for i, score in ((1, 85), (2, 40)):
            raw = c.execute('''INSERT INTO news_raw_items(source_name, article_url, title_raw, content_hash, published_at, fetched_at, status)
                VALUES('Recharge', ?, ?, ?, ?, ?, 'processed')''', (f"https://rechargenews.com/a{i}", f"Story {i}", f"h{i}", NOW, NOW)).lastrowid
            pid = c.execute('''INSERT INTO news_processed_items(raw_item_id, title, cleaned_text, summary, theme_tags, geography_tags,
                actors, why_it_matters, signal_score, confidence, linkedin_angle, linkedin_candidate, processed_at)
                VALUES(?, ?, 'x', 's', '', '', '', 'w', ?, 0.7, 'a', 0, ?)''', (raw, f"Story {i}", score, NOW)).lastrowid
            c.execute("INSERT INTO news_domain_classification VALUES(?, 'offshore_wind', 0.9, ?)", (pid, NOW))
        c.execute('''INSERT INTO news_raw_items(source_name, article_url, title_raw, content_hash, fetched_at)
            VALUES('Offshorewind', 'https://offshorewind.biz/already', 'x', 'hx', ?)''', (NOW,))


def test_only_verified_coverage_of_important_stories_is_kept(setup, monkeypatch):
    queries = []
    monkeypatch.setattr(research, "search", lambda q: queries.append(q) or [
        {"url": "https://rechargenews.com/own", "title": "Own site"},
        {"url": "https://offshorewind.biz/already", "title": "Already collected"},
        {"url": "https://newoutlet.example/same", "title": "Same story", "description": "Same event"},
        {"url": "https://other.example/topic", "title": "Related", "description": "Only the topic"}])
    monkeypatch.setattr(service, "judge_pair", lambda ai, a, b, h: {
        "relationship": "same_event" if b["title"] == "Same story" else "related_topic", "confidence": 0.9})
    assert coverage.fill_coverage_gaps() == {"searched": 1, "found": 1}
    assert queries == ["Story 1"]          # low-scoring story 2 is not searched
    with db.get_conn() as c:
        rows = c.execute("SELECT url, basis FROM news_source_evidence").fetchall()
    assert [(r["url"], r["basis"]) for r in rows] == [("https://newoutlet.example/same", "additional_coverage")]
    assert coverage.fill_coverage_gaps() == {"searched": 0, "found": 0}   # each story is searched once


def test_daily_cap_and_missing_provider(setup, monkeypatch):
    monkeypatch.setenv("OWI_GAP_SEARCHES_PER_DAY", "0")
    monkeypatch.setattr(research, "search", lambda q: pytest.fail("must not search"))
    assert coverage.fill_coverage_gaps() == {"searched": 0, "found": 0}
    monkeypatch.delenv("TAVILY_API_KEY")
    assert coverage.fill_coverage_gaps()["skipped"] == "no search provider configured"
