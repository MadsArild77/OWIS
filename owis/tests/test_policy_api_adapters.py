import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from owis.core.sources import probe, registry
from owis.core.storage import db
from owis.modules.policy import adapters, collector, storage, api

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
URLS = {
    'eu-hys-ener': 'https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives?topic=ENER&size=10&language=EN',
    'dk-ft-sager': 'https://oda.ft.dk/api/Sag?$top=100&$format=json',
    'nl-tk-zaken': 'https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Zaak?$top=100',
}


def fixture(name):
    return json.loads((Path(__file__).parent / 'fixtures' / f'policy_{name}.json').read_text(encoding='utf-8'))


def source(name):
    return dict(id=name, name=name, url=URLS[name], method='api', enabled=True, follow='topics',
                topics=['no matching topic'], organisation_id=None, jurisdiction_id='EU',
                content_types=['regulation', 'consultation'], interval_minutes=60, selector='')


def mock_pages(monkeypatch, pages):
    calls = []
    def fetch(url):
        calls.append(url)
        data = pages[min(len(calls) - 1, len(pages) - 1)]
        return json.dumps(data).encode(), url, 'application/json', 'utf-8'
    monkeypatch.setattr(probe, 'fetch', fetch)
    return calls


def snapshot(monkeypatch, sources):
    data = dict(sources=sources, organisations=[], jurisdictions=[dict(id='EU', code='EU', name='EU', enabled=True)])
    monkeypatch.setattr(registry, 'snapshot', lambda: data)
    return data


def rows(table='policy_items'):
    with db.get_conn() as conn:
        return [dict(r) for r in conn.execute(f'SELECT * FROM {table}')]


@pytest.mark.parametrize('name', URLS)
def test_real_response_and_preview(monkeypatch, name):
    data = fixture(name)
    calls = mock_pages(monkeypatch, [data, {'value': []}])
    items = list(adapters.records(source(name), NOW, preview=True))
    assert items and all(i['title'] and i['url'].startswith('https://') for i in items)
    assert len(calls) == 1
    mock_pages(monkeypatch, [data])
    preview = probe.preview(source(name))
    assert preview['status'] == 'ok'
    assert len(preview['items']) <= 5
    if name == 'eu-hys-ener':
        assert items[0]['url'].endswith('/18695')
        assert items[0]['published_at'] == '2026-10-26T10:17:00+00:00'
        assert items[0]['deadline'] == '2026-11-23T23:59:59+00:00'
        assert items[0]['content_type'] == 'consultation'
    elif name == 'dk-ft-sager':
        assert items[0]['url'].endswith('(106343)?$format=json')
    else:
        assert items[0]['published_at'] == '2026-11-05T22:00:04.753000+00:00'


def test_hys_unsorted_old_open_and_closure(monkeypatch):
    data = fixture('eu-hys-ener')
    page = data['initiativeResultDtoPage']
    page['last'] = True
    page['content'] = page['content'][:1]
    period = page['content'][0]['currentStatuses'][0]
    period['feedbackStartDate'] = '2025/01/01 12:00:00'
    src = source('eu-hys-ener')
    snapshot(monkeypatch, [src])
    old = copy.deepcopy(data)
    old['initiativeResultDtoPage']['last'] = False
    oldrow = old['initiativeResultDtoPage']['content'][0]
    oldrow['id'] = 1
    oldrow['currentStatuses'][0].update(receivingFeedbackStatus='CLOSED', feedbackEndDate='2025/02/01 12:00:00')
    calls = mock_pages(monkeypatch, [old, data])
    collector.collect(NOW)
    assert len(calls) == 2
    assert len(rows()) == 1
    assert len(storage.items(NOW)) == 1
    assert len(storage.items(NOW, recent=True)) == 1
    period.update(receivingFeedbackStatus='CLOSED', feedbackEndDate='2025/02/01 12:00:00')
    mock_pages(monkeypatch, [data])
    collector.collect(NOW + timedelta(hours=2))
    assert rows()[0]['deadline'] is None
    assert rows()[0]['content_type'] == 'regulation'
    assert not storage.items(NOW + timedelta(hours=2))


@pytest.mark.parametrize('name', URLS)
def test_maximum_500_and_endpoint_preserved(monkeypatch, name):
    data = fixture(name)
    if name == 'eu-hys-ener':
        page = data['initiativeResultDtoPage']
        page.update(last=False, totalPages=100)
        page['content'] = [page['content'][0]] * 100
    else:
        data['value'] = [data['value'][0]] * 100
    calls = mock_pages(monkeypatch, [data])
    assert len(list(adapters.records(source(name), NOW))) == 500
    assert len(calls) == 5
    assert all(urlsplit(u).path == urlsplit(URLS[name]).path for u in calls)
    queries = [parse_qs(urlsplit(u).query) for u in calls]
    if name == 'eu-hys-ener':
        assert queries[-1]['page'] == ['4']
        assert all(q['topic'] == ['ENER'] for q in queries)
    else:
        assert queries[-1]['$skip'] == ['400']


@pytest.mark.parametrize('name,field', [('dk-ft-sager', 'opdateringsdato'), ('nl-tk-zaken', 'GewijzigdOp')])
def test_odata_date_boundary_and_topics(monkeypatch, name, field):
    data = fixture(name)
    old = copy.deepcopy(data)
    old['value'][0][field] = '2026-10-01T12:00:00Z'
    calls = mock_pages(monkeypatch, [data, old])
    assert len(list(adapters.records(source(name), NOW))) == 2
    assert len(calls) == 2
    src = source(name)
    src['topics'] = [data['value'][0]['titel' if name == 'dk-ft-sager' else 'Onderwerp']]
    snapshot(monkeypatch, [src])
    mock_pages(monkeypatch, [data, {'value': []}])
    collector.collect(NOW)
    assert len(rows()) == 1
    assert rows('policy_runs')[0]['items_filtered'] == 1


def test_storting_unknown_and_invalid_response(monkeypatch):
    sources = [source('eu-hys-ener') for _ in range(3)]
    for src, host in zip(sources, ('data.stortinget.no', 'example.org', 'oda.ft.dk')):
        src.update(id=host, url=f'https://{host}/api/Sag')
    snapshot(monkeypatch, sources)
    calls = mock_pages(monkeypatch, [{}])
    collector.collect(NOW)
    runs = rows('policy_runs')
    assert runs[0]['status'] == 'skipped'
    assert runs[0]['error'] == 'Collected by the Storting tab (D25)'
    assert runs[1]['error'] == 'No adapter for this API'
    assert runs[2]['status'] == 'error'
    assert len(calls) == 1


def test_deadline_priority_migration_and_morning(monkeypatch):
    from owis.modules.news.processing import morning
    data = fixture('eu-hys-ener')
    data['initiativeResultDtoPage']['last'] = True
    snapshot(monkeypatch, [source('eu-hys-ener')])
    mock_pages(monkeypatch, [data])
    collector.collect(NOW)
    recent = storage.items(NOW, recent=True)
    assert [r['deadline'][:10] for r in recent] == ['2026-11-06', '2026-11-10', '2026-11-23']
    actual = storage.items
    monkeypatch.setattr(storage, 'items', lambda **kwargs: actual(NOW, **kwargs))
    class Clock:
        @staticmethod
        def now(tz):
            return NOW
    monkeypatch.setattr(api, 'datetime', Clock)
    assert api.items(content_type='consultation', offset=0)['items'][0]['deadline'].startswith('2026-11-06')
    sent = []
    class AI:
        enabled = True
        def _post_json_prompt(self, prompt, payload, **kwargs):
            sent.append(json.loads(payload))
            return {'headline': 'Policy'}
    monkeypatch.setattr(morning, 'AIClient', AI)
    morning.write_brief([], monitored_policy=recent)
    assert sent[0]['monitored_policy'][0]['deadline'] == recent[0]['deadline']
    storage.ensure()
    assert len(rows()) == 3
