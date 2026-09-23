import httpx
import pytest
from owis.core.storage import db
from owis.modules.news.collectors import http_retry
from owis.modules.news.storage.source_events import list_events

@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'retry.db'))
    monkeypatch.setattr(http_retry.time, 'sleep', lambda _: None)


def test_stops_after_three_retries():
    calls = []
    def get(url):
        calls.append(url)
        raise httpx.ReadTimeout('slow')
    with pytest.raises(httpx.ReadTimeout):
        http_retry.get_with_retry(get, 'https://example.com/rss')
    assert len(calls) == 4
    assert len(list_events()) == 4
    assert 'Attempt 4/4' in list_events()[0]['message']


@pytest.mark.parametrize('status', [401, 403, 404])
def test_permanent_failures_are_not_retried(status):
    calls = []
    def get(url):
        calls.append(url)
        return httpx.Response(status, request=httpx.Request('GET', url))
    assert http_retry.get_with_retry(get, 'https://example.com/rss').status_code == status
    assert len(calls) == 1


def test_transient_failure_recovers():
    codes = iter([429, 503, 200])
    def get(url):
        return httpx.Response(next(codes), request=httpx.Request('GET', url))
    assert http_retry.get_with_retry(get, 'https://example.com/rss').status_code == 200
    assert len(list_events()) == 2


def test_long_retry_after_stops_instead_of_hanging():
    def get(url):
        return httpx.Response(429, headers={'Retry-After': '3600'}, request=httpx.Request('GET', url))
    with pytest.raises(httpx.HTTPStatusError):
        http_retry.get_with_retry(get, 'https://example.com/rss')
    assert len(list_events()) == 1
