import json
import sqlite3
from types import SimpleNamespace
import httpx
import pytest
from owis.core.storage import db
from owis.core.config import settings
from owis.core.llm.client import AIClient
from owis.modules.news.matching import semantic, service
from owis.modules.news.storage.repository import NewsRepository

@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "matching.db"))
    db.init_db()
    return NewsRepository()

def article(i, title="Norwegian story", **kw):
    return dict(id=i,title=title,summary="",actors="",domain_bucket="offshore_wind",
                published_at="2026-09-23T10:00:00Z", **kw)

def seed(repo, i):
    raw = dict(source_name="Fixture",article_url=f"https://example.com/{i}",title_raw=str(i),
               content_hash=str(i),fetched_at="2026-09-23T10:00:00Z")
    raw_id=repo.upsert_raw_item_get_id(raw)
    return repo.save_processed_item(dict(raw_item_id=raw_id,title=str(i),cleaned_text="text",summary="text",
        theme_tags="",geography_tags="",actors="",why_it_matters="",signal_score=50,confidence=0.5,
        linkedin_angle="",linkedin_candidate=0,processed_at="2026-09-23T10:00:00Z"))

def pair(repo, a,b, relation="same_event"):
    return repo.upsert_match_review_pair(a,b,"yes" if relation=="same_event" else "no",0.9,"evidence",[],"same day",relation)

def test_cross_language_candidate_does_not_need_common_words():
    items=[article(1,"Regjeringen godkjenner havvindpark"),article(2,"Government approves floating turbines")]
    assert not service.build_candidate_pairs(items)
    # Stub vectors test routing, not real model accuracy.
    result=service.build_candidate_pairs(items,embeddings={1:[1,0],2:[0.99,0.01]})
    assert len(result)==1

def test_rejected_pairs_and_time_limits_override_similarity():
    items=[article(1),article(2)]
    vectors={1:[1,0],2:[1,0]}
    assert not service.build_candidate_pairs(items,embeddings=vectors,learned_pairs={(1,2):"reject"})
    items[1]["published_at"]="2026-08-01T10:00:00Z"
    assert not service.build_candidate_pairs(items,days_window=30,embeddings=vectors)

def test_input_order_does_not_change_candidates():
    items=[article(i) for i in range(1,5)]
    def keys(rows):return [(a["id"],b["id"]) for a,b,_ in service.build_candidate_pairs(rows,top_k=1)]
    assert keys(items)==keys(list(reversed(items)))

def test_embedding_cache_and_changed_content(repo, monkeypatch):
    monkeypatch.setattr(settings,"AI_ENABLED",True)
    monkeypatch.setattr(settings,"AI_API_KEY","test-only")
    calls=[]
    def post(self,url,**kw):
        calls.append(kw["json"])
        return httpx.Response(200,json={"data":[{"index":i,"embedding":[1.0,float(i)]} for i,_ in enumerate(kw["json"]["input"])]},request=httpx.Request("POST",url))
    monkeypatch.setattr(httpx.Client,"post",post)
    items=[article(1),article(2)]
    assert len(semantic.embed_articles(items))==2
    semantic.embed_articles(items)
    assert len(calls)==1
    items[1]["summary"]="changed"
    semantic.embed_articles(items)
    assert len(calls)==2 and len(calls[-1]["input"])==1

@pytest.mark.parametrize("data", [{"data":[]},{"data":[{"index":0,"embedding":[]}]}])
def test_incomplete_embeddings_are_rejected(repo,monkeypatch,data):
    monkeypatch.setattr(settings,"AI_ENABLED",True)
    monkeypatch.setattr(settings,"AI_API_KEY","test-only")
    monkeypatch.setattr(httpx.Client,"post",lambda self,url,**kw:httpx.Response(200,json=data,request=httpx.Request("POST",url)))
    with pytest.raises(ValueError):semantic.embed_articles([article(1)])

def test_judgement_is_cached_and_invalidated(repo):
    calls=[]
    def judge(**kw):
        calls.append(kw)
        return dict(relationship="same_event",same_story="yes",confidence=0.9)
    ai=SimpleNamespace(judge_news_match=judge)
    a,b=article(1),article(2)
    service.judge_pair(ai,a,b,0.8)
    service.judge_pair(ai,b,a,0.8)
    assert len(calls)==1
    b["summary"]="new facts"
    service.judge_pair(ai,a,b,0.8)
    assert len(calls)==2

@pytest.mark.parametrize("relation,expected", [("same_event",True),("update",True),("uncertain",True),("related_topic",False),("unrelated",False)])
def test_review_queue_relationships(relation,expected):
    assert service.should_enqueue_review(dict(relationship=relation,confidence=0.9)) is expected
    assert not service.should_enqueue_review(dict(relationship=relation,confidence=0.9,fallback=True))

def test_judge_balances_articles_and_includes_relationship(monkeypatch):
    captured={}
    def prompt(self,**kw):
        captured.update(kw)
        return dict(relationship="update",confidence=0.9,reason_short="Later development")
    monkeypatch.setattr(AIClient,"_post_json_prompt",prompt)
    result=AIClient().judge_news_match(article(1,cleaned_text="A"*10000),article(2,"UNIQUE_B",cleaned_text="B"*10000))
    assert "UNIQUE_B" in captured["user_text"]
    assert len(captured["user_text"])<=settings.AI_INPUT_MAX_CHARS
    assert result["relationship"]=="update" and result["same_story"]=="no"

def test_accept_merges_whole_groups_and_prevents_replay(repo):
    ids=[seed(repo,i) for i in range(4)]
    repo.set_collection_overrides(ids[:2],"first")
    repo.set_collection_overrides(ids[2:],"second")
    p=pair(repo,ids[1],ids[2])
    result=repo.apply_match_decision(p,"accept")
    assert result["item_ids"]==ids
    assert len({x["collection_key"] for x in repo.list_collection_overrides().values()})==1
    assert len(repo.list_pair_learning())==6
    with pytest.raises(ValueError):repo.apply_match_decision(p,"accept")

def test_update_links_events_without_merging(repo):
    ids=[seed(repo,i) for i in range(2)]
    p=pair(repo,*ids,relation="update")
    with pytest.raises(ValueError):repo.apply_match_decision(p,"accept")
    repo.apply_match_decision(p,"link_update")
    assert repo.list_collection_overrides()=={}
    assert repo.list_story_links()[0]["relationship"]=="update"
    assert repo.get_match_review_pair(p)["status"]=="accepted"

def test_decision_rolls_back_when_merge_fails(repo):
    ids=[seed(repo,i) for i in range(2)]
    p=pair(repo,*ids)
    with db.get_conn() as conn:
        conn.execute("CREATE TRIGGER fail_merge BEFORE INSERT ON news_collection_overrides BEGIN SELECT RAISE(ABORT, 'test'); END")
    with pytest.raises(sqlite3.IntegrityError):repo.apply_match_decision(p,"accept")
    assert repo.get_match_review_pair(p)["status"]=="pending"
    assert repo.list_collection_overrides()=={}

def test_disabled_ai_is_explicit(repo,monkeypatch):
    from owis.modules.news.presentation import api
    from fastapi import HTTPException
    monkeypatch.setattr(api,"AIClient",lambda:SimpleNamespace(enabled=False))
    with pytest.raises(HTTPException) as exc:api._run_match_review(api.MatchRunRequest())
    assert exc.value.status_code==503


def test_api_review_roundtrip_and_duplicate_decision(repo, monkeypatch):
    from fastapi.testclient import TestClient
    from owis.apps.api.main import app
    from owis.modules.news.presentation import api
    ids=[seed(repo,i) for i in range(2)]
    p=pair(repo,*ids,relation="update")
    with TestClient(app) as client:
        response=client.get("/api/news/match-review?domain_bucket=all")
        assert response.json()["items"][0]["relationship"]=="update"
        assert client.post("/api/news/match-review/decide",json={"pair_id":p,"decision":"link_update"}).status_code==200
        assert client.get("/api/news/story-links").json()["items"][0]["title_a"]=="0"
        assert client.post("/api/news/match-review/decide",json={"pair_id":p,"decision":"link_update"}).status_code==409


def test_semantic_match_api_with_mocked_openai(repo, monkeypatch):
    from owis.modules.news.presentation import api
    ids=[seed(repo,i) for i in range(2)]
    monkeypatch.setattr(api,"AIClient",lambda:SimpleNamespace(enabled=True,judge_news_match=lambda **kw:dict(relationship="same_event",same_story="yes",confidence=0.95,reason_short="Same decision")))
    monkeypatch.setattr(api,"embed_articles",lambda rows:{int(r["id"]):[1,0] for r in rows})
    # Avoid tying this test to wall-clock date or classification quality.
    monkeypatch.setattr(api,"window_start_iso",lambda days:"2020-01-01T00:00:00Z")
    result=api._run_match_review(api.MatchRunRequest(domain_bucket="all"))
    assert result["checked_pairs"]==1 and result["enqueued_pairs"]==1
    assert repo.list_match_review_pairs()[0]["relationship"]=="same_event"
