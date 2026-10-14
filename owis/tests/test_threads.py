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
    assert threads.project_key("Floating") == "" and threads.project_key("solar hybrid") == ""


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


def event(key, day, ids, project="", topic="", title="t"):
    return {"collection_key": key, "latest_published_at": (NOW + timedelta(days=day)).isoformat(),
            "items": [{"id": i} for i in ids], "master": {"title": title, "summary": "s", "sources": ["X"]},
            "_card": {"project": project, "topic": topic, "companies": [], "event_type": "other"}}


def store_cards(events):
    with db.get_conn() as c:
        for e in events:
            for i in e["items"]:
                c.execute("INSERT OR REPLACE INTO news_event_cards VALUES(?,?,?)", (i["id"], json.dumps(e["_card"]), NOW.isoformat()))


def test_same_project_or_topic_within_a_week_is_one_case():
    events = [event("a", 0, [1, 2], project="Five Estuaries offshore wind farm", topic="Five Estuaries ownership"),
              event("b", 4, [3], project="Five Estuaries", topic="Five Estuaries stake sale"),
              event("c", 1, [4], topic="German offshore wind tender reform"),
              event("d", 6, [5], topic="German tender changes"),
              event("e", 20, [6], topic="German tender reform"),      # more than a week after the last development
              event("f", 2, [7], topic="Equinor"),                    # a company is not a topic
              event("g", 3, [8])]
    store_cards(events)
    by_key = {e["collection_key"]: e["case"] for e in threads.assign_cases(events)}
    assert by_key["a"]["key"] == by_key["b"]["key"] and by_key["a"]["name"] == "Five Estuaries"
    assert by_key["c"]["key"] == by_key["d"]["key"] != by_key["e"]["key"]
    assert by_key["a"]["signature"] == "1,2,3"
    assert by_key["f"]["size"] == by_key["g"]["size"] == 1


def test_case_account_is_written_once_and_kept_until_rewritten(monkeypatch):
    from owis.modules.news.processing import cases
    events = [event("a", 0, [1], project="Utsira Nord"), event("b", 2, [2], project="Utsira Nord")]
    store_cards(events)
    threads.assign_cases(events)
    calls = []
    monkeypatch.setattr(cases.AIClient, "__init__", lambda self: None)
    monkeypatch.setattr(cases.AIClient, "enabled", True, raising=False)
    monkeypatch.setattr(cases.AIClient, "_post_json_prompt",
                        lambda self, prompt, text, **k: calls.append(json.loads(text)) or
                        {"title": "Utsira Nord subsidy", "summary": "First this, then that.", "why_it_matters": "w", "next_steps": ""})
    assert cases.write_accounts(events)["written"] == 1
    assert [d["date"] for d in calls[0]["developments"]] == sorted(d["date"] for d in calls[0]["developments"])
    assert cases.write_accounts(events)["written"] == 0           # nothing new, nothing rewritten
    cases.attach(events)
    assert events[0]["case"]["account"]["title"] == "Utsira Nord subsidy" and events[0]["case"]["account"]["complete"]
    grown = events + [event("c", 3, [3], project="Utsira Nord")]
    store_cards(grown)
    threads.assign_cases(grown)
    cases.attach(grown)
    assert grown[0]["case"]["account"]["complete"] is False       # previous account shown until rewritten


def test_opening_a_story_writes_its_account(monkeypatch):
    from owis.modules.news.presentation import api
    from owis.modules.news.processing import cases
    events = [event("a", 0, [1], project="Utsira Nord"), event("b", 2, [2], project="Utsira Nord")]
    store_cards(events)
    threads.assign_cases(events)
    monkeypatch.setattr(api, "_cased_collections", lambda bucket="core": events)
    monkeypatch.setattr(cases.AIClient, "__init__", lambda self: None)
    monkeypatch.setattr(cases.AIClient, "enabled", True, raising=False)
    monkeypatch.setattr(cases.AIClient, "_post_json_prompt", lambda *a, **k: {"title": "Utsira Nord subsidy improved", "summary": "Story.", "why_it_matters": "w", "next_steps": ""})
    account = api.case_account(api.CaseAccountRequest(signature="1,2"))
    assert account["title"] == "Utsira Nord subsidy improved" and account["complete"]
    with pytest.raises(api.HTTPException):
        api.case_account(api.CaseAccountRequest(signature="9"))
