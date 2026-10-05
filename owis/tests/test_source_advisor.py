import json
from datetime import datetime, timezone

import pytest

from owis.core.storage import db
from owis.modules.news.processing import signal
from owis.modules.news.registry import source_advisor as advisor

NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "advisor.db"))
    db.init_db()
    registry = [
        {"name": "Trade Press", "homepage": "https://tradepress.example", "url": "https://tradepress.example/rss", "enabled": True, "type": "rss"},
        {"name": "Clean Technica", "homepage": "https://cleantechnica.com", "url": "https://cleantechnica.com/feed", "enabled": True, "type": "rss"},
        {"name": "Quiet", "homepage": "https://quiet.example", "url": "https://quiet.example/rss", "enabled": True, "type": "rss"},
    ]
    monkeypatch.setattr(advisor, "_registry", lambda: [{"index": i, **s} for i, s in enumerate(registry)])
    yield
    signal.set_learned_source_weights({})


def add_article(source, bucket, n, url_prefix=None, score=50):
    with db.get_conn() as c:
        for i in range(n):
            url = f"https://{url_prefix or source.replace(' ', '').lower()}.example/{bucket}/{i}"
            raw = c.execute('''INSERT INTO news_raw_items(source_name, article_url, title_raw, content_hash, published_at, fetched_at, status)
                VALUES(?,?,?,?,?,?,'processed')''', (source, url, f"t{i}", f"h{url}", NOW, NOW)).lastrowid
            pid = c.execute('''INSERT INTO news_processed_items(raw_item_id, title, cleaned_text, summary, theme_tags, geography_tags,
                actors, why_it_matters, signal_score, confidence, linkedin_angle, linkedin_candidate, processed_at)
                VALUES(?, 't', 'x', 's', '', '', '', 'w', ?, 0.7, 'a', 0, ?)''', (raw, score, NOW)).lastrowid
            c.execute("INSERT INTO news_domain_classification VALUES(?,?,0.9,?)", (pid, bucket, NOW))


def test_learned_weight_moves_from_prior_toward_observed_quality():
    assert advisor.learned_weight(10, 0, 0, 0) == 10
    assert advisor.learned_weight(4, 100, 0.9, 1.0) >= 8          # a weak prior earns trust
    assert advisor.learned_weight(10, 100, 0.05, 0.2) <= 4        # a strong prior loses it
    assert advisor.learned_weight(6, 40, 0.5, 0.8, positive=0, negative=10) < advisor.learned_weight(6, 40, 0.5, 0.8)


def test_scorecard_learns_weights_and_recommends_pause(setup):
    add_article("Trade Press", "offshore_wind", 30, score=80)
    add_article("Clean Technica", "other_energy", 40)
    add_article("Clean Technica", "adjacent_energy", 5)
    result = advisor.advice()
    card = {row["name"]: row for row in result["scorecard"]}
    assert card["Trade Press"]["offshore_share"] == 1.0 and card["Trade Press"]["strong_signals"] == 30
    assert card["Clean Technica"]["learned_weight"] < card["Clean Technica"]["prior_weight"] or card["Clean Technica"]["learned_weight"] <= 3
    removal = {r["name"]: r["reason"] for r in result["remove"]}
    assert "Mostly outside your focus" in removal["Clean Technica"]
    assert "No articles" in removal["Quiet"]
    assert "Trade Press" not in removal
    # The scorer now uses the learned weights for new articles.
    assert signal.source_weight("Clean Technica") == card["Clean Technica"]["learned_weight"]
    assert signal.source_weight("Clean Technica", learned=False) == 4


def test_kept_source_is_not_recommended_again(setup):
    add_article("Clean Technica", "other_energy", 30)
    advisor.record_decision("remove:Clean Technica", "kept")
    assert "Clean Technica" not in {r["name"] for r in advisor.advice()["remove"]}


def test_websites_supplying_verified_coverage_are_recommended(setup):
    with db.get_conn() as c:
        for raw_id in (1, 2, 3):
            c.execute('''INSERT INTO news_source_evidence(raw_id,url,title,publisher,access,basis,content_hash,text,checked_at)
                VALUES(?,?,?,?, 'open','alternative_fulltext',?, 'text', ?)''',
                      (raw_id, f"https://www.newoutlet.example/story-{raw_id}", f"Story {raw_id}", "newoutlet", f"h{raw_id}", NOW))
        c.execute('''INSERT INTO news_source_evidence(raw_id,url,title,publisher,access,basis,content_hash,text,checked_at)
            VALUES(9,'https://tradepress.example/a','Known','x','open','alternative_fulltext','hk','t',?)''', (NOW,))
        c.execute('''INSERT INTO news_source_evidence(raw_id,url,title,publisher,access,basis,content_hash,text,checked_at)
            VALUES(8,'https://onceonly.example/a','Once','x','open','alternative_fulltext','ho','t',?)''', (NOW,))
        c.execute("INSERT INTO news_story_research(processed_id,status,started_at,completed_at,result_json,run_id) VALUES(5,'completed',?,?,?,'r')",
                  (NOW, NOW, json.dumps({"sources": [{"url": "https://newoutlet.example/x", "title": "X", "relationship": "background"},
                                                     {"url": "https://linkedin.com/post", "title": "L", "relationship": "same_event"}]})))
    adds = advisor.advice()["add"]
    assert [a["host"] for a in adds] == ["newoutlet.example"]
    assert adds[0]["stories"] == 4 and len(adds[0]["examples"]) == 3
    advisor.record_decision("add:newoutlet.example", "dismissed")
    assert advisor.advice()["add"] == []
