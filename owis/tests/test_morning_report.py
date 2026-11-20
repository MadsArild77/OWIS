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
    monkeypatch.setattr(morning, 'collection_state', lambda as_of: (_ for _ in ()).throw(RuntimeError('fail')))
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
    monkeypatch.setattr(morning, 'collection_state', lambda as_of: ([], ['Test coverage']))
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


@pytest.mark.parametrize('day', [date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5),
                               date(2028, 2, 29), date(2026, 12, 31), date(2027, 1, 1)])
def test_global_groups_rotate_in_pairs_after_daily_searches(monkeypatch, day):
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': True})
    monkeypatch.setattr(governance, 'previous_sources', lambda today: [])
    calls = []
    def search(query, purpose):
        calls.append((query, purpose))
        return []
    monkeypatch.setattr(governance, 'search', search)
    result = governance.collect(day)
    pair = day.timetuple().tm_yday % 3
    indices = list(range(8)) + [8 + pair * 2, 9 + pair * 2]
    assert len(governance.REGIONS) == 14
    assert len(calls) == 10
    assert all(purpose == 'policy' for _, purpose in calls)
    assert all('site:' + governance.REGIONS[i][1][0] in call[0]
               for i, call in zip(indices, calls))
    assert [i for i, row in enumerate(result['coverage']) if row['status'] != 'not_scheduled'] == indices
    assert len(result['warnings']) == 10  # No warning for the four unscheduled groups.


@pytest.mark.parametrize('index,day', [(11, date(2026, 10, 1)), (12, date(2026, 10, 2)),
                                     (13, date(2026, 10, 2))])
def test_global_search_validates_domains_and_keeps_region(monkeypatch, index, day):
    region, domains, _ = governance.REGIONS[index]
    url = 'https://' + domains[0] + '/auction'
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': True})
    monkeypatch.setattr(governance, 'previous_sources', lambda today: [])
    def search(query, purpose):
        if 'site:' + domains[0] not in query:
            return []
        return [{'url': url, 'title': 'Auction'},
                {'url': 'https://' + domains[0] + '.evil.test/auction', 'title': 'Fake'}]
    monkeypatch.setattr(governance, 'search', search)
    fetched = []
    def fetch(url):
        fetched.append(url)
        return 'open', source()['text'], url
    monkeypatch.setattr(governance, 'fetch_public', fetch)
    event = model_event()
    event['jurisdiction'] = {'Asia-Pacific': 'Japan', 'Americas': 'USA', 'Middle East': 'Turkey'}[region]
    def answer(self, prompt, text, **kw):
        assert 'Region: ' + region in prompt
        assert 'An EU decision is NOT automatically in force in Norway' in prompt
        assert len(json.loads(text)) == 1
        return {'events': [event]}
    monkeypatch.setattr(governance.AIClient, '_post_json_prompt', answer)
    result = governance.collect(day)
    assert fetched == [url]
    assert len(result['events']) == 1
    assert result['events'][0]['region'] == region
    assert result['events'][0]['source']['url'] == url


def test_unscheduled_group_rechecks_previous_report_without_search(monkeypatch):
    known = dict(source(), url='https://meti.go.jp/auction')
    saved = {'upcoming': [{'event_date': '2026-10-03', 'source': known}]}
    with db.get_conn() as c:
        c.execute('INSERT INTO news_morning_reports VALUES(?,?,?,?,?,?,?)',
                  ('2026-10-01', 'completed', NOW.isoformat(), NOW.isoformat(), 'previous', json.dumps(saved), None))
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': True})
    calls, fetched = [], []
    def search(query, purpose):
        calls.append(query)
        assert 'site:meti.go.jp' not in query
        return []
    def fetch(url):
        fetched.append(url)
        return 'open', known['text'], url
    monkeypatch.setattr(governance, 'search', search)
    monkeypatch.setattr(governance, 'fetch_public', fetch)
    monkeypatch.setattr(governance.AIClient, '_post_json_prompt', lambda *a, **kw: {'events': [model_event()]})
    result = governance.collect(date(2026, 10, 3))
    assert len(calls) == 10
    assert fetched == [known['url']]
    assert result['coverage'][11]['status'] == 'completed'
    assert result['coverage'][11]['sources_read'] == 1
    assert result['events'][0]['region'] == 'Asia-Pacific'
    assert not any('Asia-Pacific' in warning for warning in result['warnings'])


def test_build_orders_global_regions_and_describes_coverage():
    regions = ['Norway', 'EU', 'Nordics', 'Europe', 'Asia-Pacific', 'Americas', 'Middle East']
    events = [dict(title=region, region=region, event_date=None) for region in reversed(regions)]
    result = morning.build(NOW, [], [], {'events': events, 'coverage': [], 'warnings': []})
    assert [event['region'] for event in result['watchlist']] == regions
    assert 'Asia-Pacific, Americas and Middle East coverage is search-based' in result['coverage_note']


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


def test_report_waits_for_the_morning_fetch(monkeypatch):
    from owis.modules.news.processing import fetch_scheduler
    monkeypatch.setenv('OWI_MORNING_REPORT_ENABLED', 'true')
    calls = []
    monkeypatch.setattr(morning, 'start', lambda **kw: calls.append(kw))
    monkeypatch.setattr(fetch_scheduler, '_fetch_running', lambda: True)
    morning.tick(NOW)
    assert calls == []
    monkeypatch.setattr(fetch_scheduler, '_fetch_running', lambda: False)
    morning.tick(NOW)
    assert len(calls) == 1


def test_report_uses_stored_news_and_flags_a_stale_fetch():
    article('https://example.org/a', (NOW - timedelta(hours=1)).isoformat(), fetched=(NOW - timedelta(hours=7)).isoformat())
    report, warnings = morning.collection_state(NOW)
    assert any('latest fetch' in w for w in warnings)
    article('https://example.org/b', (NOW - timedelta(hours=1)).isoformat(), fetched=(NOW - timedelta(hours=1)).isoformat())
    assert not any('latest fetch' in w for w in morning.collection_state(NOW)[1])


def test_trends_use_earlier_days_and_are_cited(monkeypatch):
    old = article('https://example.org/old', (NOW - timedelta(days=3)).isoformat())
    new = article('https://example.org/new', (NOW - timedelta(hours=2)).isoformat())
    seen = {}
    def answer(self, prompt, text, **kw):
        seen['prompt'], seen['input'] = prompt, json.loads(text)
        return {'headline': 'H', 'key_developments': [],
                'trends': [{'headline': 'Grid policy keeps moving', 'detail': 'd', 'story_ids': [old, new, 999]}]}
    monkeypatch.setattr(morning.AIClient, '__init__', lambda self: None)
    monkeypatch.setattr(morning.AIClient, 'enabled', True, raising=False)
    monkeypatch.setattr(morning.AIClient, '_post_json_prompt', answer)
    result = morning.build(NOW, [], [], {'events': [], 'coverage': [], 'warnings': []})
    assert 'earlier_stories' in seen['prompt'] and [s['id'] for s in seen['input']['earlier_stories']] == [old]
    assert result['brief']['trends'][0]['story_ids'] == [old, new]
    assert [s['id'] for s in result['trend_stories']] == [old]


def test_brief_input_keeps_policy_trends_and_all_stories_at_full_size():
    stories = [dict(id=i, title='T' * 120, summary='s' * 900, why_it_matters='w' * 400, signal_score=80,
                    sources=[{'source_name': 'Recharge'}, {'source_name': 'Europower'}]) for i in range(30)]
    policy = [dict(title='P' * 160, organisation='Energidepartementet', jurisdiction='Norway', content_type='consultation',
                   published_at=NOW.isoformat(), first_seen_at=NOW.isoformat(), deadline=NOW.isoformat()) for _ in range(40)]
    earlier = [dict(id=100 + i, title='E' * 120, published_at=NOW.isoformat(), signal_score=70) for i in range(60)]
    events = [dict(title='V' * 120, jurisdiction='EU', event_date='2026-10-05', kind='vote', legal_status='proposal',
                   summary='x' * 400) for _ in range(10)]
    text = morning.brief_input(stories, events, earlier, policy)
    data = json.loads(text)
    assert len(text) <= morning.BRIEF_INPUT_CHARS
    assert len(data['stories']) == 30 and len(data['monitored_policy']) == 40
    assert len(data['earlier_stories']) == 60 and len(data['policy_events']) == 10


def test_brief_input_drops_lowest_stories_rather_than_policy(monkeypatch):
    monkeypatch.setattr(morning, 'BRIEF_INPUT_CHARS', 3000)
    stories = [dict(id=i, title='T' * 100, summary='s' * 400, signal_score=90 - i, sources=[]) for i in range(30)]
    policy = [dict(title='Havvind consultation', deadline='2026-10-20')]
    data = json.loads(morning.brief_input(stories, (), [], policy))
    assert data['monitored_policy'][0]['title'] == 'Havvind consultation'
    assert 0 < len(data['stories']) < 30 and data['stories'][0]['id'] == 0


def test_policy_warnings_are_condensed():
    lines = morning.condense_policy_warnings([
        'Norway: limited source coverage; missing text or excerpt-only results.',
        'Europe: 1 findings omitted because the evidence could not be validated.',
        'Europe: limited source coverage; missing text or excerpt-only results.',
        'Europe: 2 findings omitted because the evidence could not be validated.',
        'Europe: limited source coverage; missing text or excerpt-only results.',
        'Nordics: policy search or analysis failed for this source group.',
        'EU: discovery failed; only previously known sources could be rechecked.'])
    assert lines == ['EU: discovery failed; only previously known sources could be rechecked.',
                     'Policy search failed for: Nordics.',
                     'Policy search left out 3 findings that could not be checked against the source (Europe).',
                     'Policy search had only excerpts or no text for some sources: Norway, Europe.']


@pytest.mark.parametrize('day,searches', [(date(2026, 11, 23), 10), (date(2026, 11, 24), 0), (date(2026, 11, 29), 0)])
def test_policy_search_runs_on_mondays_by_default(monkeypatch, day, searches):
    monkeypatch.delenv('OWI_POLICY_SEARCH_WEEKDAYS')
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': True})
    monkeypatch.setattr(governance, 'previous_sources', lambda today: [])
    calls = []
    monkeypatch.setattr(governance, 'search', lambda query, purpose: calls.append(query) or [])
    result = governance.collect(day)
    assert len(calls) == searches
    if not searches:
        assert {row['status'] for row in result['coverage']} == {'not_scheduled'}
        assert result['warnings'] == []


def test_weekly_search_rotates_global_pairs_by_week(monkeypatch):
    monkeypatch.setenv('OWI_POLICY_SEARCH_WEEKDAYS', '0')
    monkeypatch.setattr(governance, 'capabilities', lambda: {'available': True})
    monkeypatch.setattr(governance, 'previous_sources', lambda today: [])
    monkeypatch.setattr(governance, 'search', lambda query, purpose: [])
    pairs = set()
    for monday in (date(2026, 11, 23), date(2026, 11, 30), date(2026, 12, 7)):
        coverage = governance.collect(monday)['coverage']
        pairs.add(tuple(i for i, row in enumerate(coverage) if i >= 8 and row['status'] != 'not_scheduled'))
    assert pairs == {(8, 9), (10, 11), (12, 13)}


def test_brief_groups_items_by_section_and_links_policy(monkeypatch):
    stories = [{'id': 1, 'title': 'A', 'summary': 's', 'signal_score': 9, 'sources': [{'source_name': 'X'}]}]
    policy = [{'title': 'Grid package consultation', 'url': 'https://ec.europa.eu/x', 'content_type': 'consultation'}]
    seen = {}
    def answer(self, prompt, text, **kw):
        seen['input'] = json.loads(text)
        return {'headline': 'Netherlands opens 2 GW tender', 'in_brief': ['One', 'Two', 'Three', 'Four'],
                'sections': {'europe': [{'headline': 'NL tender', 'what': 'w', 'so_what': 'Bidders must ...', 'story_ids': [1, 7]}],
                             'policy': [{'headline': 'EU grid package', 'what': 'w', 'policy_ids': ['p0', 'p0', 'p9']}],
                             'norway': [], 'unknown': [{'headline': 'ignored'}]},
                'watch': ['Award 5 Dec']}
    monkeypatch.setattr(morning.AIClient, '__init__', lambda self: None)
    monkeypatch.setattr(morning.AIClient, 'enabled', True, raising=False)
    monkeypatch.setattr(morning.AIClient, '_post_json_prompt', answer)
    brief = morning.write_brief(stories, monitored_policy=policy)
    assert seen['input']['monitored_policy'][0]['id'] == 'p0'
    assert [s['key'] for s in brief['sections']] == ['europe', 'policy']
    assert brief['sections'][0]['items'][0] == {'headline': 'NL tender', 'what_happened': 'w', 'why_it_matters': 'Bidders must ...',
                                                'story_ids': [1], 'policy': []}
    assert brief['sections'][1]['items'][0]['policy'] == [{'title': 'Grid package consultation', 'url': 'https://ec.europa.eu/x'}]
    assert brief['in_brief'] == ['One', 'Two', 'Three'] and len(brief['key_developments']) == 2


def test_deadlines_and_new_tenders_come_from_the_data(monkeypatch):
    from owis.modules.policy import storage
    from owis.modules.opportunities.storage.repository import OpportunitiesRepository
    monkeypatch.setattr(storage, 'items', lambda now, **kw: [
        dict(content_type='consultation', deadline='2026-10-08T23:59:59+00:00', title='Soon', organisation='DG ENER', url='https://a'),
        dict(content_type='consultation', deadline='2026-11-30T23:59:59+00:00', title='Later', organisation='DG ENER', url='https://b'),
        dict(content_type='regulation', deadline=None, title='No date', url='https://c')])
    tenders = [dict(id=1, title='TenneT survey', buyer='TenneT', country='NLD', deadline='2026-10-10', fit='Medium',
                    profile_name='AGR', source_url='https://t', processed_at=(NOW - timedelta(hours=2)).isoformat()),
               dict(id=2, title='Old match', buyer='B', country='GBR', deadline='2027-01-10', fit='Low',
                    profile_name='MAV', source_url='https://o', processed_at=(NOW - timedelta(days=3)).isoformat())]
    monkeypatch.setattr(OpportunitiesRepository, 'list_items', lambda self, **kw: {'items': tenders})
    events = [dict(title='Council vote', event_date='2026-10-05', kind='council_vote', jurisdiction='EU',
                   source={'url': 'https://e'}), dict(title='Undated', event_date=None)]
    rows = morning.deadlines(NOW, events)
    assert [(r['date'], r['kind'], r['title']) for r in rows] == [
        ('2026-10-05', 'Council vote', 'Council vote'), ('2026-10-08', 'Consultation', 'Soon'), ('2026-10-10', 'Tender', 'TenneT survey')]
    assert [t['title'] for t in morning.new_tenders(NOW)] == ['TenneT survey']
