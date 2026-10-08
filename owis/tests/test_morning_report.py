import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from owis.core.storage import db
from owis.modules.news.processing import morning, governance
from owis.modules.news.storage.repository import NewsRepository
from owis.modules.news.processing.pipeline import process_raw_item

NOW = datetime(2026, 10, 2, 4, tzinfo=timezone.utc)  # 06:00 Oslo


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'morning.db'))
    monkeypatch.setenv('OWI_MORNING_REPORT_ENABLED', 'false')
    monkeypatch.setattr(morning, 'utcnow', lambda: NOW)
    monkeypatch.setattr(governance.AIClient, '_post_json_prompt', lambda *a, **kw: None)
    db.init_db()


def article(url, published, fetched=NOW.isoformat(), group=None):
    repo = NewsRepository()
    raw = dict(source_name='Test source', article_url=url, title_raw='Offshore wind policy update',
               summary_raw='Grid policy update.', content_raw='Grid policy update.', content_hash=url,
               fetched_at=fetched, published_at=published)
    raw['id'] = repo.upsert_raw_item_get_id(raw)
    item_id = repo.save_processed_item(process_raw_item(raw))
    if group:
        with db.get_conn() as c:
            c.execute('INSERT INTO news_collection_overrides VALUES(?,?,?,?)', (item_id, group, '', NOW.isoformat()))
    return item_id


def test_exact_window_missing_dates_and_grouping():
    article('https://example.org/a', (NOW-timedelta(hours=24)).isoformat(), group='same')
    article('https://example.org/b', (NOW-timedelta(hours=1)).isoformat(), group='same')
    article('https://example.org/old', (NOW-timedelta(hours=24, seconds=1)).isoformat())
    article('https://example.org/future', NOW.isoformat())
    article('https://example.org/undated', None)
    article('https://example.org/date-only', '2026-10-02')
    rows, unknown = morning.recent_news(NOW)
    assert len(rows) == 1
    assert len(rows[0]['sources']) == 2
    assert unknown == 2


def test_hidden_articles_are_excluded():
    item_id = article('https://example.org/a', (NOW-timedelta(hours=1)).isoformat())
    with db.get_conn() as c:
        c.execute('INSERT INTO news_item_relevance VALUES(?,?,?)', (item_id, 0, NOW.isoformat()))
    assert morning.recent_news(NOW)[0] == []


def test_running_and_completed_reports_are_not_started_twice(monkeypatch):
    calls = []
    monkeypatch.setattr(morning.EXECUTOR, 'submit', lambda *args: calls.append(args))
    assert morning.start()['status'] == 'running'
    morning.start(refresh=True)
    assert len(calls) == 1
    with db.get_conn() as c:
        c.execute("UPDATE news_morning_reports SET status='completed'")
    morning.start()
    assert len(calls) == 1
    with pytest.raises(ValueError, match='five minutes'):
        morning.start(refresh=True)


def test_interrupted_run_retries_but_failed_schedule_does_not_loop(monkeypatch):
    calls = []
    monkeypatch.setattr(morning.EXECUTOR, 'submit', lambda *args: calls.append(args))
    morning.start(now=NOW-timedelta(hours=3))
    assert morning.read()['status'] == 'failed'
    morning.start()
    assert len(calls) == 2
    with db.get_conn() as c:
        c.execute("UPDATE news_morning_reports SET status='failed'")
    morning.start(now=NOW+timedelta(minutes=10))
    assert len(calls) == 2


def test_failed_refresh_keeps_saved_report_and_old_worker_cannot_overwrite(monkeypatch):
    with db.get_conn() as c:
        c.execute('INSERT INTO news_morning_reports VALUES(?,?,?,?,?,?,?)',
                  ('2026-10-02', 'running', NOW.isoformat(), None, 'new', '{"news":[]}', None))
    monkeypatch.setattr(morning, 'refresh_news', lambda **k: (_ for _ in ()).throw(RuntimeError('fail')))
    morning.run('2026-10-02', 'old', NOW)
    assert morning.read()['status'] == 'running'
    morning.run('2026-10-02', 'new', NOW)
    assert morning.read()['status'] == 'failed'
    assert morning.read()['result'] == {'news': []}


@pytest.mark.parametrize('utc_hour,month', [(4, 7), (5, 1)])
def test_scheduler_uses_oslo_summer_and_winter_time(monkeypatch, utc_hour, month):
    monkeypatch.setenv('OWI_MORNING_REPORT_ENABLED', 'true')
    calls = []
    monkeypatch.setattr(morning, 'start', lambda **kw: calls.append(kw))
    due = datetime(2026, month, 2, utc_hour, tzinfo=timezone.utc)
    morning.tick(due-timedelta(minutes=1))
    assert calls == []
    morning.tick(due)
    assert len(calls) == 1
    monkeypatch.setenv('OWI_MORNING_REPORT_ENABLED', 'false')
    morning.tick(due)
    assert len(calls) == 1


def test_build_separates_today_upcoming_and_undated():
    events = [dict(title='EU later', region='EU', event_date='2026-10-03'),
              dict(title='Norway today', region='Norway', event_date='2026-10-02'),
              dict(title='Sweden unknown', region='Nordics', event_date=None)]
    result = morning.build(NOW, [], [], {'events': events, 'coverage': [], 'warnings': ['Limited coverage']})
    assert result['today'][0]['title'] == 'Norway today'
    assert result['upcoming'][0]['title'] == 'EU later'
    assert result['watchlist'][0]['title'] == 'Sweden unknown'
    assert result['window_start'] == (NOW-timedelta(hours=24)).isoformat()
    assert result['warnings'] == ['Limited coverage']


def model_event(**overrides):
    return dict(title='Consultation deadline', jurisdiction='Norway', kind='deadline',
                legal_status='consultation', event_date='2026-10-03',
                date_quote='Deadline 3 October 2026.', evidence_quote='Grid consultation is open.',
                summary='Grid consultation.', implications='Grid operators can respond.', source_id=1, **overrides)


def source(basis='fulltext'):
    return dict(id=1, url='https://regjeringen.no/example', title='Grid consultation', basis=basis,
                text='Grid consultation is open. Deadline 3 October 2026.')


def extract_event(monkeypatch, event, src=None):
    monkeypatch.setattr(governance.AIClient, '_post_json_prompt', lambda *a, **k: {'events': [event]})
    return governance.extract([src or source()], date(2026, 10, 2), 'Norway')


def test_official_quote_and_full_date_required(monkeypatch):
    events, rejected = extract_event(monkeypatch, model_event())
    assert events[0]['event_date'] == '2026-10-03'
    assert events[0]['date_basis'] == 'official_text'
    event = model_event()
    event['event_date'] = '2026-10-04'  # Real quotation, wrong extracted day.
    events, _ = extract_event(monkeypatch, event)
    assert events[0]['event_date'] is None
    assert events[0]['proposed_date'] == '2026-10-04'


def test_search_excerpts_are_not_confirmed_calendar_events(monkeypatch):
    events, _ = extract_event(monkeypatch, model_event(), source('search_excerpt'))
    assert events[0]['event_date'] is None


@pytest.mark.parametrize('change', [{'source_id': 99}, {'evidence_quote': 'An invented quote.'}])
def test_unsupported_evidence_rejected(monkeypatch, change):
    event = model_event()
    event.update(change)
    events, rejected = extract_event(monkeypatch, event)
    assert events == [] and rejected == 1


def test_past_events_excluded(monkeypatch):
    event = model_event()
    event['event_date'] = '2025-10-03'
    assert extract_event(monkeypatch, event)[0] == []


def test_official_domain_check_rejects_lookalikes():
    assert governance.official_url('https://regjeringen.no.evil.test/x', ['regjeringen.no']) is None
    assert governance.official_url('https://evil.test/?url=regjeringen.no', ['regjeringen.no']) is None
    assert governance.official_url('https://energy.ec.europa.eu/a', ['ec.europa.eu'])


def test_missing_setup_is_visible(monkeypatch):
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': False, 'setup_required': 'Search key'})
    monkeypatch.setattr(governance, 'search', lambda *a: pytest.fail('Must not search'))
    result = governance.collect(date(2026, 10, 2))
    assert result['events'] == [] and 'Search key' in result['warnings'][0]


def test_collect_continues_after_failure_and_rejects_external_redirect(monkeypatch):
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': True})
    monkeypatch.setattr(governance, 'REGIONS', [('Norway', ['regjeringen.no'], 'energy'), ('EU', ['ec.europa.eu'], 'energy')])
    def search(query, **kw):
        if 'regjeringen.no' in query:
            raise RuntimeError('Search offline')
        return [dict(url='https://ec.europa.eu/a', title='Event', description='Search excerpt')]
    monkeypatch.setattr(governance, 'search', search)
    monkeypatch.setattr(governance, 'fetch_public', lambda url: ('open', 'Wrong host content', 'https://evil.test/a'))
    def extract(sources, *args):
        assert sources[0]['basis'] == 'search_excerpt'
        assert sources[0]['url'] == 'https://ec.europa.eu/a'
        return [], 0
    monkeypatch.setattr(governance, 'extract', extract)
    result = governance.collect(date(2026, 10, 2))
    assert [row['status'] for row in result['coverage']] == ['failed', 'completed']
    assert result['warnings']


def test_api_persistence_history_and_date_validation(monkeypatch):
    from owis.apps.api.main import app
    monkeypatch.setattr(morning.EXECUTOR, 'submit', lambda fn, *args: fn(*args))
    monkeypatch.setattr(morning, 'refresh_news', lambda **k: ([], ['Test coverage']))
    monkeypatch.setattr(governance, 'collect', lambda today: {'events': [], 'coverage': [], 'warnings': []})
    with TestClient(app) as client:
        assert client.get('/api/news/morning-report').json()['status'] == 'not_started'
        assert client.post('/api/news/morning-report').json()['status'] == 'completed'
        assert client.get('/api/news/morning-report/history').json()[0]['report_date'] == '2026-10-02'
        assert client.get('/api/news/morning-report?report_date=bad').status_code == 400
    with TestClient(app) as client:
        assert client.get('/api/news/morning-report?report_date=2026-10-02').json()['result']['warnings'] == ['Test coverage']


def test_known_upcoming_sources_are_rechecked_when_search_is_empty(monkeypatch):
    saved = {'upcoming': [{'event_date': '2026-10-03', 'source': source()}]}
    with db.get_conn() as c:
        c.execute('INSERT INTO news_morning_reports VALUES(?,?,?,?,?,?,?)',
                  ('2026-10-01', 'completed', NOW.isoformat(), NOW.isoformat(), 'previous', json.dumps(saved), None))
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': True})
    monkeypatch.setattr(governance, 'REGIONS', [('Norway', ['regjeringen.no'], 'energy')])
    monkeypatch.setattr(governance, 'search', lambda query, **kw: [])
    fetched = []
    def fetch(url):
        fetched.append(url)
        return 'open', source()['text'], url
    monkeypatch.setattr(governance, 'fetch_public', fetch)
    monkeypatch.setattr(governance.AIClient, '_post_json_prompt', lambda *a, **kw: {'events': [model_event()]})
    result = governance.collect(date(2026, 10, 2))
    assert fetched == [source()['url']]
    assert result['events'][0]['event_date'] == '2026-10-03'


def test_blank_quote_is_not_evidence(monkeypatch):
    event = model_event()
    event['evidence_quote'] = '   '
    assert extract_event(monkeypatch, event) == ([], 1)


def test_brief_keeps_only_known_story_ids(monkeypatch):
    stories = [{'id': 1, 'title': 'A', 'summary': 's', 'why_it_matters': 'w', 'signal_score': 9, 'sources': [{'source_name': 'X'}]}]
    monkeypatch.setattr(morning.AIClient, 'enabled', True, raising=False)
    monkeypatch.setattr(morning.AIClient, '__init__', lambda self: None)
    monkeypatch.setattr(morning.AIClient, '_post_json_prompt', lambda *a, **k: {
        'headline': 'Big award', 'overview': 'Busy day.', 'watch': ['Auction'], 'policy': 'not a list',
        'key_developments': [{'headline': 'Award', 'what_happened': 'x', 'why_it_matters': 'y', 'story_ids': [1, 99, '1']},
                             {'what_happened': 'no headline'}]})
    brief = morning.write_brief(stories)
    assert brief['headline'] == 'Big award' and brief['ai'] is True
    assert brief['key_developments'] == [{'headline': 'Award', 'what_happened': 'x', 'why_it_matters': 'y', 'story_ids': [1]}]
    assert brief['policy'] == [] and brief['watch'] == ['Auction']
    assert morning.write_brief([]) is None
    monkeypatch.setattr(morning.AIClient, '_post_json_prompt', lambda *a, **k: {
        'headline': 'Odd shape', 'key_developments': 'text', 'watch': 3})
    assert morning.write_brief(stories)['key_developments'] == []
    monkeypatch.setattr(morning.AIClient, '_post_json_prompt', lambda *a, **k: {
        'headline': 'Odd ids', 'key_developments': [{'headline': 'A', 'story_ids': 1}]})
    assert morning.write_brief(stories)['key_developments'][0]['story_ids'] == []
