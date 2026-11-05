from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from owis.core.sources import registry
from owis.core.storage import db
from owis.modules.policy import collector, storage, api

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


def source(sid='one', **values):
    return dict(id=sid, name=sid, url=f'https://example.org/{sid}', method='rss',
                enabled=True, follow='inherit', topics=[], organisation_id='child', jurisdiction_id='NO',
                content_types=['regulation'], interval_minutes=360, selector='', **values)


@pytest.fixture
def setup(monkeypatch):
    data = dict(jurisdictions=[dict(id='NO', code='NO', name='Norway', enabled=True, groups=['Nordics'])],
        organisations=[dict(id='parent', name='Parent', enabled=True, follow='all', topics=['wind']),
                       dict(id='child', name='Ministry', enabled=True, follow='topics', topics=[], parent_id='parent')],
        sources=[source()])
    monkeypatch.setattr(registry, 'snapshot', lambda: data)
    monkeypatch.setattr('owis.modules.news.processing.content.public_url', lambda url: url)
    responses = {}
    requests = []
    def handle(request):
        requests.append(str(request.url))
        value = responses[request.url.path]
        if isinstance(value, Exception):
            raise value
        return httpx.Response(200, text=value, headers={'content-type':'text/html; charset=utf-8'})
    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handle), **kwargs))
    return data, responses, requests


def rss(entries):
    return '<rss version="2.0"><channel><title>Policy</title>' + ''.join(
        f'<item><title>{title}</title><link>https://example.org/{url}</link><description>{summary}</description>'
        + (f'<pubDate>{format_datetime(date)}</pubDate>' if date else '') + '</item>'
        for title, url, summary, date in entries) + '</channel></rss>'


def rows(table='policy_items'):
    with db.get_conn() as conn:
        return [dict(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY id')]


def test_rss_inherited_topics_interval_and_paused_parent(setup):
    data, responses, requests = setup
    responses['/one'] = rss([('WIND market', 'a?utm_source=x#top', '&lt;b&gt;Grid&lt;/b&gt;', NOW),
                             ('Unrelated', 'b', 'Sport', NOW)])
    collector.collect(NOW)
    assert len(rows()) == 1
    assert rows()[0]['summary'] == 'Grid'
    assert rows()[0]['url'] == 'https://example.org/a'
    assert rows('policy_runs')[0]['items_filtered'] == 1
    collector.collect(NOW + timedelta(minutes=359))
    assert len(requests) == 1
    collector.collect(NOW + timedelta(minutes=360))
    assert len(requests) == 2
    data['organisations'][0]['enabled'] = False
    collector.collect(NOW + timedelta(days=1))
    assert len(requests) == 2
    with db.get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM news_raw_items').fetchone()[0] == 0


def test_html_selector_all_links_and_undated(setup):
    data, responses, _ = setup
    data['sources'][0].update(method='html_list', selector='.policy', follow='all')
    responses['/one'] = '<a href="/outside">Outside policy document</a><main class="policy">' + ''.join(
        f'<a href="/item{i}">Public policy document {i}</a>' for i in range(8)) + '<a href="/short">Short</a></main>'
    collector.collect(NOW)
    assert len(rows()) == 8
    assert all(r['published_at'] is None for r in rows())


def test_first_success_window_type_and_duplicate_priority(setup):
    data, responses, _ = setup
    data['sources'] = [source('one'), source('two'), source('three')]
    for s in data['sources']:
        s['follow'] = 'all'
    data['sources'][1]['content_types'] = ['calendar', 'consultation']
    data['sources'][2]['content_types'] = ['consultation']
    responses['/one'] = rss([('Boundary', 'a', '', NOW-timedelta(days=30)),
        ('Old', 'old', '', NOW-timedelta(days=31)), ('Missing date', 'undated', '', None)])
    responses['/two'] = rss([('Calendar entry', 'a?utm_medium=x#part', '', NOW),
        ('Old calendar', 'calendar', '', NOW-timedelta(days=31)),
        ('Old consultation', 'excluded', '', NOW-timedelta(days=31))])
    responses['/three'] = rss([('Request for comment', 'a', '', NOW)])
    collector.collect(NOW)
    result = {r['url'].split('/')[-1]: r for r in rows()}
    assert set(result) == {'a', 'undated', 'calendar'}
    assert result['a']['content_type'] == 'consultation'
    assert result['a']['source_id'] == 'one'
    assert result['a']['first_seen_at'] == NOW.isoformat()
    collector.collect(NOW+timedelta(hours=6))
    assert len(rows()) == 5  # The date limit applies only to the first successful fetch.


def test_failure_isolated_and_three_failures_first(setup):
    data, responses, _ = setup
    data['sources'] = [source('broken'), source('one')]
    responses['/broken'] = 'Not a feed'
    responses['/one'] = rss([('Wind policy', 'a', '', NOW)])
    for hours in (0, 6, 12):
        collector.collect(NOW + timedelta(hours=hours))
    assert len(rows()) == 1
    statuses = storage.source_status(data)
    assert statuses[0]['id'] == 'broken'
    assert statuses[0]['consecutive_failures'] == 3
    assert statuses[0]['error']
    assert statuses[1]['last_saved'] == NOW.isoformat()


def test_news_and_unsupported_sources_are_not_fetched(setup):
    data, _, requests = setup
    data['sources'][0]['content_types'].append('news')
    data['sources'].append(source('api'))
    data['sources'][1]['method'] = 'api'
    collector.collect(NOW)
    assert requests == []


def test_atom_updated_summary_limit_and_source_topics(setup):
    data, responses, _ = setup
    data['sources'][0]['topics'] = ['electricity']
    responses['/one'] = '<feed xmlns="http://www.w3.org/2005/Atom"><title>Policy</title><entry><title>Electricity market</title><link href="https://example.org/atom"/><updated>2026-11-04T12:00:00Z</updated><summary>' + 'x'*1100 + '</summary></entry></feed>'
    collector.collect(NOW)
    assert len(rows()[0]['summary']) == 1000
    assert rows()[0]['published_at'] == '2026-11-04T12:00:00+00:00'


def test_scheduler_own_claim(setup, monkeypatch):
    calls = []
    monkeypatch.setenv('OWI_SCHEDULED_FETCH_ENABLED', 'true')
    monkeypatch.setenv('OWI_FETCH_HOURS', '5,8,12')
    monkeypatch.setattr(collector, 'collect', lambda now: calls.append(now))
    assert collector.tick(NOW)
    assert not collector.tick(NOW)
    assert len(calls) == 1
    with db.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM news_registry_meta WHERE key LIKE 'scheduled_fetch:%'").fetchone()[0] == 0


def test_recent_priority_api_regions_and_pagination(setup, monkeypatch):
    data, responses, _ = setup
    data['sources'].append(source('all'))
    data['sources'][1]['follow'] = 'all'
    responses['/one'] = rss([(f'Wind document {i}', f't{i}', '', NOW) for i in range(105)])
    responses['/all'] = rss([('All source document', 'all', '', NOW)])
    collector.collect(NOW)
    recent = storage.items(NOW, recent=True)
    assert len(recent) == 40
    assert recent[0]['title'] == 'All source document'
    actual_items = storage.items
    monkeypatch.setattr(storage, 'items', lambda **kw: actual_items(NOW, **kw))
    assert len(api.items(region='Norway', offset=0)['items']) == 100
    assert len(api.items(region='Norway', offset=100)['items']) == 6
    assert not api.items(region='Americas', offset=0)['items']
    assert not api.items(content_type='calendar', offset=0)['items']
    for group in ('Nordics', 'Asia-Pacific', 'Americas', 'Middle East'):
        assert storage.region({'groups':[group]}) == group
    assert storage.region({'code':'NO', 'groups':['Nordics']}) == 'Norway'
    assert storage.region({'code':'EU'}) == 'EU'


def test_morning_payload_and_saved_report(setup, monkeypatch):
    from owis.modules.news.processing import morning
    data, responses, _ = setup
    responses['/one'] = rss([('Wind consultation', 'a', '', NOW)])
    collector.collect(NOW)
    sent = []
    class AI:
        enabled = True
        def _post_json_prompt(self, prompt, payload, **kwargs):
            sent.append((prompt, payload))
            return {'headline':'Policy update'}
    monkeypatch.setattr(morning, 'AIClient', AI)
    report = morning.build(NOW, [], [], dict(events=[], coverage=[], warnings=[]))
    assert report['monitored_policy'][0]['title'] == 'Wind consultation'
    assert 'monitored_policy' in sent[0][1]
    assert 'Ministry' in sent[0][1]
    assert 'power markets' in sent[0][0]
