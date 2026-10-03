import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from owis.core.storage import db
from owis.modules.news.processing import research
from owis.modules.news.storage.repository import NewsRepository
from owis.modules.news.processing.pipeline import process_raw_item

@pytest.fixture
def story(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path/'research.db'))
    db.init_db()
    repo = NewsRepository()
    raw = dict(source_name='Test', article_url='https://example.com/story', title_raw='New offshore wind contract',
               summary_raw='A contract was awarded.', content_raw='A contract was awarded.', content_hash='r1', fetched_at='2026-09-27')
    raw['id'] = repo.upsert_raw_item_get_id(raw)
    monkeypatch.setattr(research.AIClient, 'enrich_news', lambda *a: None)
    item_id = repo.save_processed_item(process_raw_item(raw))
    monkeypatch.setattr(research, 'capabilities', lambda: {'available': True, 'setup_required': ''})
    return item_id

@pytest.fixture
def analysis():
    claim = {'text':'A contract was awarded.', 'source_ids':[1]}
    return dict(what_happened=[claim], key_developments=[], why_it_matters=[claim], whats_new=[],
                sources=[{'source_id':1, 'relationship':'original'}, {'source_id':2, 'relationship':'background'}],
                brand_fit={'level':'High','reason':'Energy supply-chain implications.'},
                conversation_potential={'level':'Medium','reason':'A useful but narrow development.'},
                why_this_fits_you='Room for a measured industry perspective.',
                suggested_angles=['What this changes for suppliers.'], what_would_strengthen_it='Your own observation, if relevant.',
                limitations='Additional coverage is a search excerpt.')


def mock_analysis(monkeypatch, output):
    monkeypatch.setattr(research, 'search', lambda query:[{'url':'https://example.org/report','title':'Background','description':'Context.'}])
    monkeypatch.setattr(research, 'fetch_public', lambda url: ('blocked','',url))
    def respond(self, prompt, evidence, **kw):
        assert 'not a finished LinkedIn post' in prompt
        assert 'personal experience' in prompt
        assert 'virality' in prompt
        assert json.loads(evidence)['sources'][1]['basis'] == 'search_excerpt'
        assert kw['input_max_chars'] == 24000
        return output
    monkeypatch.setattr(research.AIClient, '_post_json_prompt', respond)


def test_saved_research_survives_reopen_without_new_search(story, analysis, monkeypatch):
    mock_analysis(monkeypatch, analysis)
    monkeypatch.setattr(research._EXECUTOR, 'submit', lambda fn,*args:fn(*args))
    first = research.start(story)
    assert first['status'] == 'completed'
    assert first['result']['brand_fit']['level'] == 'High'
    assert first['result']['conversation_potential']['level'] == 'Medium'
    assert first['result']['sources'][1]['url'] == 'https://example.org/report'
    db.init_db()
    monkeypatch.setattr(research, 'search', lambda q:pytest.fail('Cached result must not search again'))
    assert research.start(story)['result'] == first['result']


def test_duplicate_click_and_refresh_cooldown(story, monkeypatch):
    calls=[]
    monkeypatch.setattr(research._EXECUTOR, 'submit', lambda *args:calls.append(args))
    assert research.start(story)['status']=='running'
    assert research.start(story, refresh=True)['status']=='running'
    assert len(calls)==1
    with db.get_conn() as conn:
        conn.execute("UPDATE news_story_research SET status='failed' WHERE processed_id=?", (story,))
    with pytest.raises(ValueError, match='two minutes'):
        research.start(story, refresh=True)


@pytest.mark.parametrize('invalid', ['unknown_reference','unrelated_reference','unsupported_new','invalid_rating'])
def test_invalid_ai_results_are_not_saved(story, analysis, monkeypatch, invalid):
    if invalid=='unknown_reference': analysis['what_happened'][0]['source_ids']=[99]
    if invalid=='unrelated_reference':
        analysis['sources'][1]['relationship']='unrelated'
        analysis['what_happened'][0]['source_ids']=[2]
    if invalid=='unsupported_new': analysis['whats_new']=[{'text':'New claim','source_ids':[1]}]
    if invalid=='invalid_rating': analysis['brand_fit']['level']='95'
    mock_analysis(monkeypatch, analysis)
    monkeypatch.setattr(research._EXECUTOR,'submit',lambda fn,*args:fn(*args))
    result=research.start(story)
    assert result['status']=='failed' and result['result'] is None


def test_failed_refresh_preserves_previous_result(story, analysis, monkeypatch):
    mock_analysis(monkeypatch, analysis)
    monkeypatch.setattr(research._EXECUTOR,'submit',lambda fn,*args:fn(*args))
    saved=research.start(story)['result']
    with db.get_conn() as conn:
        conn.execute('UPDATE news_story_research SET started_at=? WHERE processed_id=?',
                     ((datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat(),story))
    def fail(query):raise RuntimeError('Search failed with secret provider details')
    monkeypatch.setattr(research,'search',fail)
    result=research.start(story,refresh=True)
    assert result['status']=='failed' and result['result']==saved
    assert 'secret' not in result['error']


def test_interrupted_run_can_restart(story, monkeypatch):
    old=(datetime.now(timezone.utc)-timedelta(minutes=16)).isoformat()
    with db.get_conn() as conn:
        conn.execute("INSERT INTO news_story_research(processed_id,status,started_at,run_id) VALUES(?,'running',?,'old')",(story,old))
    assert research.read(story)['status']=='failed'
    monkeypatch.setattr(research._EXECUTOR,'submit',lambda *args:None)
    assert research.start(story)['status']=='running'


def test_api_reports_missing_setup_without_starting(story, monkeypatch):
    from owis.apps.api.main import app
    monkeypatch.setattr(research,'capabilities',lambda:{'available':False,'setup_required':'Brave Search API key'})
    monkeypatch.setattr(research._EXECUTOR,'submit',lambda *args:pytest.fail('Should not start'))
    with TestClient(app) as client:
        result=client.get(f'/api/news/item/{story}/research').json()
        assert result['available'] is False
        assert client.post(f'/api/news/item/{story}/research').status_code==409
        assert client.get('/api/news/item/99999/research').status_code==404

def test_researched_articles_are_not_archived(story):
    with db.get_conn() as conn:
        conn.execute("UPDATE news_raw_items SET published_at='2020-01-01'")
        conn.execute("INSERT INTO news_story_research(processed_id,status,started_at,run_id) VALUES(?,'completed',?,'saved')",
                     (story,datetime.now(timezone.utc).isoformat()))
    assert NewsRepository().archive_old_unprotected_items('2026-01-01')['archived']==0


def test_no_results_does_not_invent_new_coverage(story, analysis, monkeypatch):
    analysis['sources']=analysis['sources'][:1]
    monkeypatch.setattr(research,'search',lambda query:[])
    monkeypatch.setattr(research.AIClient,'_post_json_prompt',lambda *a,**kw:analysis)
    result=research.analyse(NewsRepository().get_item(story))
    assert len(result['sources'])==1 and result['whats_new']==[]


def test_tavily_search_normalizes_results_and_limits_cost(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY','test-key')
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY','unused')
    monkeypatch.setattr(research.httpx,'get',lambda *a,**k:pytest.fail('Must prefer Tavily'))
    def post(url,headers,json,timeout):
        assert url=='https://api.tavily.com/search'
        assert headers['Authorization']=='Bearer test-key'
        assert json['search_depth']=='basic' and json['auto_parameters'] is False
        assert json['max_results']==5 and json['include_answer'] is False
        assert json['include_raw_content'] is False
        return research.httpx.Response(200,json={'results':[{'url':'https://example.org/a','title':'Report','content':'Evidence'}]*7},request=research.httpx.Request('POST',url))
    monkeypatch.setattr(research.httpx,'post',post)
    rows=research.search('offshore wind')
    assert len(rows)==5 and rows[0]['description']=='Evidence'


def test_tavily_failure_does_not_silently_charge_brave(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY','test-key')
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY','unused')
    monkeypatch.setattr(research.httpx,'get',lambda *a,**k:pytest.fail('No automatic fallback'))
    monkeypatch.setattr(research.httpx,'post',lambda url,**k:research.httpx.Response(401,request=research.httpx.Request('POST',url)))
    with pytest.raises(research.httpx.HTTPStatusError):research.search('test')


def test_brave_still_available_without_tavily(monkeypatch):
    monkeypatch.delenv('TAVILY_API_KEY',raising=False)
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY','test-key')
    monkeypatch.setattr(research.httpx,'get',lambda url,**k:research.httpx.Response(200,json={'web':{'results':[{'url':'https://example.org','description':'Text'}]}},request=research.httpx.Request('GET',url)))
    assert research.search('test')[0]['description']=='Text'


def test_tavily_key_satisfies_search_configuration(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY','test-key')
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY',raising=False)
    monkeypatch.setattr(research,'AIClient',lambda:type('Client',(),{'enabled':True})())
    assert research.capabilities()['available'] is True


def test_unused_omitted_sources_are_preserved_as_unassessed(story, analysis, monkeypatch):
    analysis['sources'].pop()
    mock_analysis(monkeypatch, analysis)
    result = research.analyse(NewsRepository().get_item(story))
    assert result['sources'][1]['relationship'] == 'unassessed'
    assert 'not assessed' in result['limitations']


def test_claim_cannot_cite_omitted_source(story, analysis, monkeypatch):
    analysis['sources'].pop()
    analysis['what_happened'][0]['source_ids'] = [2]
    mock_analysis(monkeypatch, analysis)
    with pytest.raises(ValueError, match='unsupported source references'):
        research.analyse(NewsRepository().get_item(story))


@pytest.mark.parametrize('entry', [{'source_id':1,'relationship':'original'}, {'source_id':99,'relationship':'background'}])
def test_duplicate_or_unknown_classifications_are_rejected(story, analysis, monkeypatch, entry):
    analysis['sources'].append(entry)
    mock_analysis(monkeypatch, analysis)
    with pytest.raises(ValueError, match='invalid source classifications'):
        research.analyse(NewsRepository().get_item(story))


@pytest.mark.parametrize("status", ["running", "completed", "failed"])
def test_research_history_includes_every_attempt(story, status):
    from owis.apps.api.main import app
    with TestClient(app) as client:
        assert client.get('/api/news/researched').json() == []
        with db.get_conn() as conn:
            conn.execute("INSERT INTO news_story_research(processed_id,status,started_at,run_id) VALUES(?,?,?,?)",
                         (story, status, datetime.now(timezone.utc).isoformat(), 'history'))
        rows = client.get('/api/news/researched').json()
        assert len(rows) == 1
        assert rows[0]['id'] == story
        assert rows[0]['research_status'] == status
        assert rows[0]['title'] == 'New offshore wind contract'


def test_research_history_marks_interrupted_attempt(story):
    from owis.modules.news.presentation.api import researched_stories
    with db.get_conn() as conn:
        conn.execute("INSERT INTO news_story_research(processed_id,status,started_at,run_id) VALUES(?,'running',?,'old')",
                     (story, (datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()))
    assert researched_stories()[0]['research_status'] == 'failed'
