import json
from datetime import datetime, timedelta, timezone

import pytest

from owis.core.storage import db
from owis.modules.news.processing import threads
from owis.modules.news.processing.pipeline import process_raw_item
from owis.modules.news.storage.repository import NewsRepository

NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "threads.db"))
    db.init_db()


def story(url, title, card, published=NOW, group=None):
    repo = NewsRepository()
    raw = dict(source_name="Test", article_url=url, title_raw=title, summary_raw=title, content_raw=title,
               content_hash=url, fetched_at=NOW.isoformat(), published_at=published.isoformat())
    raw["id"] = repo.upsert_raw_item_get_id(raw)
    item_id = repo.save_processed_item(process_raw_item(raw))
    with db.get_conn() as c:
        c.execute("INSERT INTO news_event_cards VALUES(?,?,?)", (item_id, json.dumps(card), NOW.isoformat()))
        if group:
            c.execute("INSERT INTO news_collection_overrides VALUES(?,?,?,?)", (item_id, group, "", NOW.isoformat()))
    return item_id


def card(project, companies, event_type="financing_or_deal"):
    return {"project": project, "companies": companies, "event_type": event_type}


def test_project_names_are_compared_without_generic_words():
    assert threads.project_key("Five Estuaries offshore wind farm") == threads.project_key("Five Estuaries")
    assert threads.project_key("Offshore wind project") == ""


def test_teaser_and_full_report_of_one_deal_are_the_same_event():
    teaser = {"published_at": NOW.isoformat(), "event_card": card("Five Estuaries", ["CIP"], "investment_decision")}
    full = {"published_at": (NOW + timedelta(minutes=30)).isoformat(),
            "event_card": card("Five Estuaries offshore wind farm", ["Copenhagen Infrastructure Partners", "Macquarie"], "investment_decision")}
    assert threads.same_action_reported_twice(teaser, full)
    later = {**full, "published_at": (NOW + timedelta(days=5)).isoformat()}
    assert not threads.same_action_reported_twice(teaser, later)
    other_party = {**full, "event_card": card("Five Estuaries", ["Equinor"], "investment_decision")}
    assert not threads.same_action_reported_twice(teaser, other_party)
    other_kind = {**full, "event_card": card("Five Estuaries", ["CIP"], "construction_start")}
    assert not threads.same_action_reported_twice(teaser, other_kind)


def test_thread_lists_other_stories_on_the_project_once_per_merged_story():
    sale = story("https://a/1", "RWE confirms Five Estuaries stake sale", card("Five Estuaries", ["RWE", "EDF"]), NOW - timedelta(days=4), "g1")
    story("https://b/1", "EDF buys RWE stake", card("Five Estuaries offshore wind farm", ["EDF"]), NOW - timedelta(days=1), "g1")
    cip = story("https://c/1", "CIP acquires Macquarie's Five Estuaries stake", card("Five Estuaries", ["CIP"]))
    story("https://d/1", "Hornsea 3 cable contract", card("Hornsea 3", ["Orsted"]))
    story("https://e/1", "Old Five Estuaries consent", card("Five Estuaries", ["RWE"]), NOW - timedelta(days=200))
    rows = threads.thread_for(cip)
    assert len(rows) == 1 and rows[0]["title"] in {"RWE confirms Five Estuaries stake sale", "EDF buys RWE stake"}
    assert [r["id"] for r in threads.thread_for(sale)] == [cip]
