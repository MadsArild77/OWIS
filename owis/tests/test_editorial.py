import sqlite3
import pytest
from owis.core.storage import db
from owis.modules.news.processing import editorial,content
from owis.modules.news.storage.repository import NewsRepository
from owis.modules.news.processing.pipeline import process_raw_item

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',str(tmp_path/'test.db'));db.init_db()
    monkeypatch.setattr(content.AIClient,'_post_json_prompt',lambda *a,**k:None)
    monkeypatch.setattr(content,'fetch_public',lambda url:('unknown','',url))
    repo=NewsRepository()
    raw=dict(source_name='Test',article_url='https://example.com/story',title_raw='New offshore wind cable contract',summary_raw='Cable contract awarded.',content_raw='Cable contract awarded.',content_hash='1',fetched_at='2026-09-23')
    raw['id']=repo.upsert_raw_item_get_id(raw)
    item=repo.save_processed_item(process_raw_item(raw))
    return repo,raw,item

def test_feedback_restart_scope_undo_and_conflict(setup):
    repo,raw,item=setup
    first=editorial.record(item,'energy','relevant')
    second=editorial.record(item,'energy','non_relevant','promotion')
    editorial.record(item,'maritime','relevant')
    db.init_db()
    assert editorial.attach([repo.get_item(item)])[0]['editorial']['energy']['value']=='non_relevant'
    with pytest.raises(ValueError):editorial.undo(first['event_id'])
    editorial.undo(second['event_id'])
    state=editorial.attach([repo.get_item(item)])[0]['editorial']
    assert state['energy']['value']=='relevant' and state['maritime']['value']=='relevant'
    with pytest.raises(ValueError):editorial.undo(second['event_id'])
    with db.get_conn() as c:assert c.execute('SELECT count(*) FROM news_editorial_events').fetchone()[0]==3

def test_feedback_error_has_no_partial_state(setup):
    with pytest.raises(LookupError):editorial.record(999,'all','relevant')
    with db.get_conn() as c:assert c.execute('SELECT count(*) FROM news_editorial_events').fetchone()[0]==0

def test_exclusion_before_network_and_enrichment(setup,monkeypatch):
    _,raw,_=setup
    raw.update(title_raw='Football results',summary_raw='Football results')
    monkeypatch.setattr(content,'fetch_public',lambda *a:pytest.fail('Irrelevant story fetched'))
    prepared=content.prepare(raw)
    assert prepared['_content_basis']['relevance']=='excluded'
    monkeypatch.setattr(content.AIClient,'enrich_news',lambda *a:pytest.fail('Excluded story sent to AI'))
    process_raw_item(prepared)

def test_fulltext_cached_and_citations_saved(setup,monkeypatch):
    _,raw,_=setup
    calls=[]
    monkeypatch.setattr(content,'fetch_public',lambda url:(calls.append(url) or ('open','Verified text. '*100,url)))
    result=content.prepare(raw);again=content.prepare(raw)
    assert result['content_raw']==again['content_raw'] and len(calls)==1
    with db.get_conn() as c:
        assert c.execute('SELECT count(*) FROM news_source_evidence').fetchone()[0]==2

def test_closed_article_uses_attributed_alternative(setup,monkeypatch):
    _,raw,item=setup
    editorial.record(item,'all','relevant')
    monkeypatch.setattr(content,'fetch_public',lambda url:('restricted','',url))
    monkeypatch.setattr(content,'alternative_sources',lambda *a:[dict(url='https://open.example/story',title='Open report',access='open',text='Open evidence. '*100)])
    result=content.prepare(raw)
    assert result['_content_basis']['access']=='restricted'
    assert result['_content_basis']['basis']=='alternative_fulltext'
    assert result['_content_basis']['source_url']=='https://open.example/story'
    with db.get_conn() as c:
        assert c.execute('SELECT count(*) FROM news_source_suggestions').fetchone()[0]==1

def test_failure_preserves_excerpt(setup,monkeypatch):
    _,raw,_=setup
    def fail(url):raise TimeoutError()
    monkeypatch.setattr(content,'fetch_public',fail)
    result=content.prepare(raw)
    assert result['content_raw']==raw['content_raw'] and result['_content_basis']['access']=='unknown'

def test_private_urls_rejected(monkeypatch):
    monkeypatch.setattr(content.socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',('127.0.0.1',80))])
    with pytest.raises(ValueError):content.public_url('http://internal.test')
    with pytest.raises(ValueError):content.public_url('file:///etc/passwd')

def test_backup_preserves_feedback_and_sources(setup,tmp_path,monkeypatch):
    from owis.scripts.backup_database import backup
    from owis.modules.news.registry import source_discovery as sources
    _,_,item=setup
    monkeypatch.setattr(sources,'_use_db_registry',lambda:True)
    sources.save_source_registry([dict(name='Port',url='https://example.com/feed',enabled=True,interest_topic='maritime')])
    editorial.record(item,'maritime','relevant')
    target=backup(tmp_path/'backup.db')
    with sqlite3.connect(target) as c:
        assert c.execute('SELECT count(*) FROM news_editorial_events').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM news_source_registry').fetchone()[0]==1
    sources.save_source_registry([]);db.init_db()
    assert sources.load_source_registry()==[]  # Never resurrect deleted sources from packaged YAML.

def test_negative_examples_do_not_veto_related_topic(setup):
    _,raw,item=setup
    editorial.record(item,'energy','non_relevant')
    class AI:
        def _post_json_prompt(self,*a,**kw):return dict(decision='excluded',reason='Past negative')
    assert editorial.prefilter(raw,AI())[0]=='uncertain'

def test_editorial_api_and_separate_draft_signal(setup,monkeypatch):
    from fastapi.testclient import TestClient
    from owis.apps.api.main import app
    _,raw,item=setup
    from owis.modules.news.presentation import api
    monkeypatch.setattr(api,'_create_job',lambda *a:'test-job')
    with TestClient(app) as client:
        result=client.post(f'/api/news/item/{item}/feedback',json={'topic':'grid','value':'relevant'})
        assert result.status_code==200
        assert client.post(f'/api/news/feedback/{result.json()["event_id"]}/reason',json={'reason':'not_now'}).status_code==200
        assert client.get('/api/news/feedback/history').json()[0]['reason']=='not_now'
        assert client.post(f'/api/news/feedback/{result.json()["event_id"]}/undo').status_code==200
        assert client.post(f'/api/news/item/{item}/draft').status_code==503
        with db.get_conn() as c:assert c.execute('SELECT count(*) FROM news_editorial_drafts').fetchone()[0]==0


@pytest.mark.parametrize('html,status,expected',[
    ('<article><p>'+('Wind contract details. '*80)+'</p></article>',200,'open'),
    ('<script type="application/ld+json">{"isAccessibleForFree":false}</script><article><p>'+('Details. '*200)+'</p></article>',200,'restricted'),
    ('<article><p>'+('Verify you are human. '*80)+'</p></article>',200,'blocked'),
    ('<p>'+('Menu links. '*200)+'</p>',200,'unknown'),
    ('Forbidden',403,'blocked'),
])
def test_access_classification(monkeypatch,html,status,expected):
    import httpx
    monkeypatch.setattr(content,'public_url',lambda url:None)
    original=httpx.Client
    transport=httpx.MockTransport(lambda req:httpx.Response(status,text=html,headers={'content-type':'text/html'},request=req))
    monkeypatch.setattr(content.httpx,'Client',lambda **kwargs:original(transport=transport,**kwargs))
    assert content.fetch_public('https://example.com/story')[0]==expected


def test_successful_draft_persists_without_relevance_vote(setup,monkeypatch):
    from fastapi.testclient import TestClient
    from owis.apps.api.main import app
    _,_,item=setup
    calls=[]
    def answer(self,*a,**kw):
        calls.append(1)
        return {'body':'Et nytt kabelprosjekt er annonsert. Hva betyr det for leverandørene?'}
    monkeypatch.setattr(content.AIClient,'_post_json_prompt',answer)
    with TestClient(app) as client:
        first=client.post(f'/api/news/item/{item}/draft')
        assert first.status_code==200 and 'Kilde:' in first.json()['body']
        count=len(calls)
        assert client.post(f'/api/news/item/{item}/draft').json()==first.json()
        assert len(calls)==count
    with db.get_conn() as c:
        assert c.execute('SELECT count(*) FROM news_editorial_events').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM news_draft_provenance').fetchone()[0]==1


def test_railway_startup_rejects_ephemeral_database(setup,monkeypatch):
    from owis.apps.api.main import on_startup
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_ID','test-environment')
    monkeypatch.delenv('RAILWAY_VOLUME_MOUNT_PATH',raising=False)
    with pytest.raises(RuntimeError,match='persistent volume'):on_startup()


def test_positive_vote_releases_cached_exclusion(setup,monkeypatch):
    _,raw,item=setup
    monkeypatch.setattr(content,'prefilter',lambda *a:('excluded','test',[]))
    content.prepare(raw)
    editorial.record(item,'energy','relevant')
    assert content.prepare(raw)['_content_basis']['relevance']=='relevant'


@pytest.mark.parametrize('access',['blocked','unknown','restricted'])
def test_alternative_threshold_cache_and_positive_override(setup,monkeypatch,access):
    _,raw,item=setup
    with db.get_conn() as c:c.execute('UPDATE news_processed_items SET signal_score=69 WHERE id=?',(item,))
    calls=[]
    monkeypatch.setattr(content,'fetch_public',lambda url:(access,'',url))
    monkeypatch.setattr(content,'alternative_sources',lambda *a:(calls.append(1) or []))
    content.prepare(raw)
    assert calls==[]
    editorial.record(item,'all','relevant')
    content.prepare(raw)
    content.prepare(raw,refresh=True)
    assert calls==[1]
    with db.get_conn() as c:assert c.execute('SELECT count(*) FROM news_open_search_attempts').fetchone()[0]==1


def test_score_boundary_and_sufficient_text(setup,monkeypatch):
    _,raw,item=setup
    with db.get_conn() as c:c.execute('UPDATE news_processed_items SET signal_score=70 WHERE id=?',(item,))
    calls=[]
    monkeypatch.setattr(content,'alternative_sources',lambda *a:(calls.append(1) or []))
    content.prepare(raw)
    assert calls==[1]
    raw['content_raw']='Wind project evidence. '*100
    calls.clear()
    content.prepare(raw,refresh=True)
    assert calls==[]


def test_alternative_candidates_bounded_and_deduplicated(setup,monkeypatch):
    from owis.modules.news.matching import service
    _,raw,_=setup
    def pairs(rows,**kwargs):
        target=rows[-1]
        return [(target,dict(id=i,title='Same event',article_url=f'https://example.com/{i//2}'),0) for i in range(10)]
    monkeypatch.setattr(service,'build_candidate_pairs',pairs)
    monkeypatch.setattr(service,'judge_pair',lambda *a:dict(fallback=False,relationship='unrelated',confidence=1))
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY',raising=False)
    calls=[]
    monkeypatch.setattr(content,'fetch_public',lambda url:(calls.append(url) or ('open','Evidence '*200,url)))
    assert content.alternative_sources(raw,object())==[]
    assert len(calls)<=3 and len(calls)==len(set(calls))
