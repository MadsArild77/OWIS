import httpx
import pytest
from owis.core.storage import db
from owis.modules.news.storage import source_events as events
from owis.modules.news.registry import source_discovery
from owis.modules.news.collectors import rss_fetcher

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'events.db'))
    from owis.modules.news.collectors import http_retry
    monkeypatch.setattr(http_retry.time, 'sleep', lambda _: None)


def test_error_survives_recovery_and_restart():
    url = 'https://example.com/rss'
    events.record_attempts([dict(source='A', url=url, status='error', error='HTTP 429: Too many requests', items=0)], 'fetch')
    events.record_attempts([dict(source='Renamed', url=url, status='ok', items=3)], 'fetch')
    db.init_db()
    rows = events.list_events(url)
    assert len(rows) == 2
    assert rows[0]['status'] == 'ok'
    assert rows[1]['http_status'] == 429
    assert rows[1]['category'] == 'http'
    assert rows[1]['created_at']
    assert events.list_events('https://other.com/rss') == []


def test_empty_is_not_error_and_sensitive_urls_are_redacted():
    events.record_attempts([dict(source='A', url='https://user:secret@example.com/rss?token=private', status='ok', items=0)], 'fetch')
    assert events.list_events()[0]['status'] == 'empty'
    assert events.list_events()[0]['source_url'] == 'https://example.com/rss'
    assert 'private' not in events.safe_message('Failed https://example.com/rss?token=private token=private')


def test_rss_timeout_is_persisted(monkeypatch):
    monkeypatch.setattr(rss_fetcher, 'load_sources', lambda: [dict(name='A', url='https://example.com/rss', type='rss')])
    def fail(url):
        raise httpx.ReadTimeout('')
    monkeypatch.setattr(rss_fetcher, '_parse_feed', fail)
    rss_fetcher.fetch_rss_items_with_report()
    row = events.list_events()[0]
    assert row['category'] == 'timeout'
    assert row['message'] == 'ReadTimeout: '


def test_health_http_failure_is_persisted(monkeypatch):
    monkeypatch.setattr(source_discovery, 'load_source_registry', lambda: [dict(name='A', url='https://example.com/rss', homepage='https://example.com', type='rss', enabled=True)])
    monkeypatch.setattr(httpx.Client, 'get', lambda self, url: httpx.Response(503, request=httpx.Request('GET', url)))
    result = source_discovery.source_health_report()
    assert result[0]['status'] == 'rss_invalid'
    assert events.list_events('https://example.com/rss')[0]['http_status'] == 503


def test_scrape_health_does_not_call_server_error_healthy(monkeypatch):
    monkeypatch.setattr(source_discovery, 'load_source_registry', lambda: [dict(name='A', url='https://example.com', type='scrape', enabled=True)])
    monkeypatch.setattr(httpx.Client, 'get', lambda self, url: httpx.Response(500, text='Server error', request=httpx.Request('GET', url)))
    assert source_discovery.source_health_report()[0]['status'] == 'error'
    assert events.list_events()[0]['http_status'] == 500
