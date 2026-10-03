import json

import httpx
import pytest
from fastapi.testclient import TestClient

from owis.core.storage import db
from owis.core.sources import registry, probe
from owis.core.sources.models import Source
from owis.modules.news.registry import source_discovery as legacy


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'config.db'))
    monkeypatch.setattr(legacy, '_use_db_registry', lambda: True)
    monkeypatch.setenv('OWI_MORNING_REPORT_ENABLED', 'false')
    db.init_db()
    legacy.save_source_registry([])
    return registry.snapshot()


def save(kind, item):
    return registry.apply(registry.snapshot()['revision'], {kind: [item]})


def add_org(name='Energy committee', jid='NO', parent=None):
    state = save('organisations', dict(name=name, jurisdiction_id=jid, kind='committee', parent_id=parent))
    return next(o for o in state['organisations'] if o['name'] == name)


def add_source(**changes):
    item = dict(name='Source', url='https://example.org/feed', content_types=['news'], method='rss', jurisdiction_id='NO')
    item.update(changes)
    state = save('sources', item)
    return next(s for s in state['sources'] if s['name'] == item['name'])


def clean(source):
    return {k: v for k, v in source.items() if k in Source.model_fields}


def test_defaults_have_eu_and_each_member_as_separate_jurisdictions(setup):
    countries = {j['code']: j for j in setup['jurisdictions']}
    assert len(registry.EU_COUNTRIES) == 27
    assert countries['EU']['kind'] == 'supranational'
    assert countries['SE']['kind'] == 'country'
    assert countries['NO']['groups'] == ['Europe', 'Nordics']
    assert setup['sources'] == []
    assert registry.snapshot()['revision'] == setup['revision']


def test_migration_preserves_disabled_auth_and_other_legacy_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'old.db'))
    monkeypatch.setattr(legacy, '_use_db_registry', lambda: True)
    original = dict(name='Old source', url='https://example.org/rss', homepage='https://example.org',
                    type='rss', enabled=False, priority='high', interest_topic='grid', geography_tags=['europe'],
                    auth={'headers': {'Authorization': {'env': 'MY_KEY'}}}, manual_override=True, extra='keep')
    legacy.save_source_registry([original])
    state = registry.snapshot()
    source = state['sources'][0]
    assert source['jurisdiction_id'] is None and source['enabled'] is False
    restored = legacy.load_source_registry()[0]
    assert all(restored[k] == v for k, v in original.items())
    assert source['id'] == registry.snapshot()['sources'][0]['id']
    assert 'MY_KEY' not in json.dumps(registry.export_config())
    assert 'auth' not in json.dumps(registry.export_config())


def test_old_deleted_sources_do_not_return_from_yaml(setup, monkeypatch):
    monkeypatch.setattr(legacy, '_load_source_registry_from_yaml', lambda: pytest.fail('Do not reseed'))
    assert registry.snapshot()['sources'] == []
    assert legacy.load_source_registry() == []


def test_legacy_edits_and_shared_edits_use_same_source(setup):
    source = add_source()
    assert legacy.load_source_registry()[0]['_config_id'] == source['id']
    legacy.update_source(0, {'name':'Changed in old UI', 'auth':{'headers':{'Authorization':'secret'}}, 'priority':'high'})
    source = registry.snapshot()['sources'][0]
    assert source['name'] == 'Changed in old UI'
    source.update(name='Changed in new UI')
    save('sources', clean(source))
    row = legacy.load_source_registry()[0]
    assert row['name'] == 'Changed in new UI' and row['priority'] == 'high'
    assert row['auth']['headers']['Authorization'] == 'secret'
    assert 'secret' not in json.dumps(registry.export_config())


def test_parent_pause_and_resume_preserve_source_enabled_choice(setup):
    parliament = add_org('Parliament')
    committee = add_org(parent=parliament['id'])
    source = add_source(organisation_id=committee['id'])
    parliament['enabled'] = False
    save('organisations', parliament)
    row = legacy.load_source_registry()[0]
    assert row['enabled'] is True and row['_collection_enabled'] is False
    from owis.modules.news.collectors.rss_fetcher import load_sources
    assert load_sources() == []
    parliament['enabled'] = True
    save('organisations', parliament)
    assert load_sources()[0]['_config_id'] == source['id']
    norway = next(j for j in registry.snapshot()['jurisdictions'] if j['id'] == 'NO')
    norway['enabled'] = False
    save('jurisdictions', norway)
    assert load_sources() == []


def test_multiple_sources_on_same_host_are_not_deduped(setup):
    add_source(name='Feed one')
    add_source(name='Feed two', url='https://example.org/other-feed')
    assert legacy.dedupe_sources()['removed_count'] == 0
    assert len(registry.snapshot()['sources']) == 2


def test_unimplemented_sources_do_not_enter_news_pipeline(setup):
    add_source(name='Calendar', content_types=['calendar'], method='html_page')
    add_source(name='Policy feed', content_types=['regulation'])
    assert legacy.load_source_registry() == []
    assert all(s['collection_status'] == 'adapter_pending' for s in registry.snapshot()['sources'])


def test_legacy_delete_pauses_but_retains_shared_record(setup):
    source = add_source()
    legacy.delete_source(0)
    assert legacy.load_source_registry() == []
    state = registry.snapshot()
    assert state['sources'][0]['id'] == source['id']
    assert state['sources'][0]['enabled'] is False
    source['enabled'] = True
    save('sources', clean(source))
    assert len(legacy.load_source_registry()) == 1


def test_cross_jurisdiction_and_cycles_are_rejected_atomically(setup):
    org = add_org()
    revision = registry.snapshot()['revision']
    with pytest.raises(ValueError, match='jurisdiction'):
        add_source(jurisdiction_id='SE', organisation_id=org['id'])
    assert registry.snapshot()['revision'] == revision
    org['parent_id'] = org['id']
    with pytest.raises(ValueError, match='cycles'):
        save('organisations', org)


def test_stale_revision_is_rejected(setup):
    add_org()
    with pytest.raises(registry.Conflict):
        registry.apply(setup['revision'], {'organisations':[dict(name='Stale',jurisdiction_id='NO')]})
    assert len(registry.snapshot()['organisations']) == 1


def test_import_roundtrip_and_failed_import_rollback(setup):
    org = add_org()
    source = add_source(organisation_id=org['id'])
    bundle = registry.export_config()
    source_id = source['id']
    bundle['sources'][0]['name'] = 'Imported name'
    registry.import_config(bundle, registry.snapshot()['revision'])
    assert registry.snapshot()['sources'][0]['name'] == 'Imported name'
    assert registry.snapshot()['sources'][0]['id'] == source_id
    bundle['organisations'][0]['parent_id'] = 'missing'
    bundle['sources'][0]['name'] = 'Must roll back'
    with pytest.raises(ValueError):
        registry.import_config(bundle, registry.snapshot()['revision'])
    assert registry.snapshot()['sources'][0]['name'] == 'Imported name'


def test_import_preserves_absent_records_and_merges_hierarchy(setup):
    old = add_source(name='Existing')
    bundle = {'version':1, 'jurisdictions':[dict(id='XJ',code='XJ',name='Custom')],
              'organisations':[dict(id='gov',name='Government',jurisdiction_id='XJ')],
              'sources':[dict(id='external',name='Calendar',url='https://example.org/calendar',
                              content_types=['calendar'],method='ics',jurisdiction_id='XJ',organisation_id='gov')]}
    result = registry.import_config(bundle, registry.snapshot()['revision'])
    assert {s['id'] for s in result['sources']} == {old['id'], 'external'}
    assert next(s for s in result['sources'] if s['id']=='external')['collection_status'] == 'adapter_pending'


def test_external_yaml_configuration_is_not_silently_migrated(setup, monkeypatch):
    monkeypatch.setattr(legacy, '_use_db_registry', lambda: False)
    with pytest.raises(registry.Conflict, match='YAML'):
        registry.snapshot()


@pytest.mark.parametrize('url', ['http://127.0.0.1/x','http://localhost/','http://192.168.1.2/',
                                 'https://example.org:8443/','https://user:password@example.org/','file:///tmp/a'])
def test_source_validation_rejects_private_or_credential_urls(url):
    with pytest.raises(ValueError):
        Source(name='Invalid', url=url, content_types=['news'])


def test_preview_rss_is_real_and_does_not_create_articles(setup, monkeypatch):
    monkeypatch.setattr(probe, 'fetch', lambda url: (b'<rss version="2.0"><channel><title>Feed</title><item><title>Actual item</title><link>https://example.org/a</link><description>Actual summary</description></item></channel></rss>',url,'application/rss+xml','utf-8'))
    source = add_source()
    result = probe.test_source(clean(source))
    assert result['items'][0]['title'] == 'Actual item'
    assert registry.snapshot()['sources'][0]['last_test']['status'] == 'ok'
    with db.get_conn() as c:
        assert c.execute('SELECT count(*) FROM news_raw_items').fetchone()[0] == 0
    source['url'] = 'https://example.org/edited'
    probe.test_source(clean(source))
    assert registry.snapshot()['sources'][0]['url'] == 'https://example.org/feed'


def test_preview_selector_and_unsupported_adapter(setup, monkeypatch):
    monkeypatch.setattr(probe, 'fetch', lambda url: (b'<html><nav><a href="/menu">Menu</a></nav><main><a href="/event">Actual event</a></main></html>',url,'text/html','utf-8'))
    source = Source(name='Calendar',url='https://example.org',content_types=['calendar'],method='html_list',selector='main a')
    result = probe.test_source(source.model_dump())
    assert [i['title'] for i in result['items']] == ['Actual event']
    source.method = 'ics'
    monkeypatch.setattr(probe, 'fetch', lambda url: pytest.fail('Unsupported preview must not fetch'))
    assert probe.test_source(source.model_dump())['status'] == 'unsupported'


def test_preview_rejects_private_redirect_and_oversize_response(setup, monkeypatch):
    from owis.modules.news.processing import content
    checked = []
    def validate(url):
        checked.append(url)
        if '127.0.0.1' in url:
            raise ValueError('Private network address rejected')
    monkeypatch.setattr(content, 'public_url', validate)
    original = httpx.Client
    transport = httpx.MockTransport(lambda req: httpx.Response(302,headers={'location':'http://127.0.0.1/admin'}))
    monkeypatch.setattr(probe.httpx,'Client',lambda **kwargs:original(transport=transport,**kwargs))
    with pytest.raises(ValueError,match='Private'):
        probe.fetch('https://example.org')
    assert len(checked) == 2
    transport = httpx.MockTransport(lambda req: httpx.Response(200,content=b'x'*2_000_001,headers={'content-type':'text/html'}))
    with pytest.raises(ValueError,match='2 MB'):
        probe.fetch('https://example.org')


def test_api_validation_conflict_and_restart_persistence(setup):
    from owis.apps.api.main import app
    with TestClient(app) as client:
        state = client.get('/api/source-config').json()
        payload = {'revision':state['revision'],'item':{'name':'Stortinget','jurisdiction_id':'NO','kind':'parliament'}}
        assert client.post('/api/source-config/organisations',json=payload).status_code == 200
        assert client.post('/api/source-config/organisations',json=payload).status_code == 409
        payload['revision'] += 1
        payload['item']['jurisdiction_id'] = 'MISSING'
        assert client.post('/api/source-config/organisations',json=payload).status_code == 422
    with TestClient(app) as client:
        state = client.get('/api/source-config').json()
        assert state['organisations'][0]['name'] == 'Stortinget'
        assert client.get('/api/source-config/export').json()['version'] == 1
