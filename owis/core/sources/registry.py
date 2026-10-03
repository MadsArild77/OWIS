"""Authoritative shared registry with a compatible view for legacy news jobs."""
import json
from uuid import uuid4

from owis.core.storage.db import get_conn, init_db
from owis.core.sources.models import ConfigBundle, Jurisdiction, Organisation, Source

MODELS = {'jurisdictions': Jurisdiction, 'organisations': Organisation, 'sources': Source}
TABLES = {'jurisdictions': 'source_jurisdictions', 'organisations': 'source_organisations', 'sources': 'configured_sources'}
EU_COUNTRIES = {'AT': 'Austria', 'BE': 'Belgium', 'BG': 'Bulgaria', 'HR': 'Croatia', 'CY': 'Cyprus',
                'CZ': 'Czechia', 'DK': 'Denmark', 'EE': 'Estonia', 'FI': 'Finland', 'FR': 'France',
                'DE': 'Germany', 'GR': 'Greece', 'HU': 'Hungary', 'IE': 'Ireland', 'IT': 'Italy',
                'LV': 'Latvia', 'LT': 'Lithuania', 'LU': 'Luxembourg', 'MT': 'Malta', 'NL': 'Netherlands',
                'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania', 'SK': 'Slovakia', 'SI': 'Slovenia',
                'ES': 'Spain', 'SE': 'Sweden'}


class Conflict(ValueError):
    pass


def initialized(conn):
    return bool(conn.execute("SELECT 1 FROM source_config_meta WHERE key='initialized'").fetchone())


def revision(conn):
    row = conn.execute("SELECT value FROM source_config_meta WHERE key='revision'").fetchone()
    return int(row['value']) if row else 0


def bump(conn):
    conn.execute("INSERT OR REPLACE INTO source_config_meta VALUES('revision',?)", (str(revision(conn)+1),))


def records(conn, kind):
    return [json.loads(row['payload']) for row in conn.execute(f'SELECT payload FROM {TABLES[kind]} ORDER BY rowid')]


def store(conn, kind, value):
    conn.execute(f'''INSERT INTO {TABLES[kind]}(id,payload) VALUES(?,?)
        ON CONFLICT(id) DO UPDATE SET payload=excluded.payload''',
                 (value['id'], json.dumps(value, ensure_ascii=False)))


def from_legacy(raw):
    # Preserve every original setting in legacy_json; do not infer jurisdiction.
    url = (raw.get('url') or raw.get('homepage')) if raw.get('type') == 'rss' else (raw.get('homepage') or raw.get('url'))
    return Source(id=uuid4().hex, name=raw.get('name') or 'Source', url=url,
                  enabled=bool(raw.get('enabled')), content_types=['news'],
                  method='rss' if raw.get('type') == 'rss' else 'html_list',
                  topics=[raw['interest_topic']] if raw.get('interest_topic') not in {None, '', 'all'} else [],
                  follow='all').model_dump()


def ensure():
    from owis.modules.news.registry import source_discovery as old
    init_db()
    if not old._use_db_registry():
        raise Conflict('Shared configuration requires the database source registry. The external YAML registry remains unchanged.')
    with get_conn() as conn:
        if initialized(conn):
            return
    old.load_source_registry()  # Seed legacy defaults only according to its existing rules.
    with get_conn() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if initialized(conn):
            return
        countries = {'NO': 'Norway', **EU_COUNTRIES, 'IS': 'Iceland', 'GB': 'United Kingdom'}
        store(conn, 'jurisdictions', Jurisdiction(id='EU', code='EU', name='European Union', kind='supranational', groups=['Europe']).model_dump())
        for code, name in countries.items():
            groups = ['Europe'] + (['EU members'] if code in EU_COUNTRIES else [])
            if code in {'NO', 'SE', 'DK', 'FI', 'IS'}:
                groups.append('Nordics')
            store(conn, 'jurisdictions', Jurisdiction(id=code, code=code, name=name, groups=groups).model_dump())
        rows = conn.execute('SELECT source_json FROM news_source_registry ORDER BY position,id').fetchall()
        for row in rows:
            raw = json.loads(row['source_json'])
            # Legacy data is retained even if it predates stricter URL validation.
            # Such records can be corrected in Settings; probes always validate again.
            try:
                value = from_legacy(raw)
            except ValueError:
                value = Source.model_construct(id=uuid4().hex, name=raw.get('name') or 'Source',
                    url=raw.get('url') or raw.get('homepage') or '', enabled=bool(raw.get('enabled')),
                    content_types=['news'], method='rss' if raw.get('type') == 'rss' else 'html_list', follow='all').model_dump()
            store(conn, 'sources', value)
            conn.execute('UPDATE configured_sources SET legacy_json=? WHERE id=?', (json.dumps(raw), value['id']))
        conn.execute("INSERT INTO source_config_meta VALUES('initialized','true')")
        bump(conn)


def effective(source, jurisdictions, organisations):
    if not source['enabled'] or source['follow'] == 'off':
        return False
    jid = source.get('jurisdiction_id')
    if jid and not jurisdictions[jid]['enabled']:
        return False
    oid = source.get('organisation_id')
    while oid:
        org = organisations[oid]
        if not org['enabled'] or org['follow'] == 'off':
            return False
        oid = org.get('parent_id')
    return True


def compatible(source):
    return 'news' in source['content_types'] and source['method'] in {'rss', 'html_list'}


def legacy_view(conn):
    jurisdictions = {r['id']: r for r in records(conn, 'jurisdictions')}
    organisations = {r['id']: r for r in records(conn, 'organisations')}
    result = []
    for row in conn.execute('SELECT * FROM configured_sources WHERE legacy_visible=1 ORDER BY rowid'):
        value = json.loads(row['payload'])
        if not compatible(value):
            continue
        raw = json.loads(row['legacy_json'])
        raw.update(name=value['name'], url=value['url'], type='rss' if value['method'] == 'rss' else 'scrape',
                   enabled=value['enabled'], _config_id=value['id'],
                   _collection_enabled=effective(value, jurisdictions, organisations))
        raw.setdefault('homepage', value['url'])
        result.append(raw)
    return result


def save_legacy(conn, sources):
    """Called under the legacy writer's transaction. Preserve configuration/auth."""
    previous = {r['_config_id'] for r in legacy_view(conn)}
    seen = set()
    for raw in sources:
        sid = raw.get('_config_id')
        row = conn.execute('SELECT payload FROM configured_sources WHERE id=?', (sid,)).fetchone() if sid else None
        if row:
            value = json.loads(row['payload'])
            url = (raw.get('url') or raw.get('homepage')) if raw.get('type') == 'rss' else (raw.get('homepage') or raw.get('url'))
            value.update(name=raw.get('name') or 'Source', url=url,
                         enabled=bool(raw.get('enabled')), method='rss' if raw.get('type') == 'rss' else 'html_list')
        else:
            value = from_legacy(raw)
        seen.add(value['id'])
        store(conn, 'sources', value)
        clean = {k: v for k, v in raw.items() if not k.startswith('_config') and k != '_collection_enabled'}
        conn.execute('UPDATE configured_sources SET legacy_json=?,legacy_visible=1,last_test_json=NULL WHERE id=?',
                     (json.dumps(clean), value['id']))
    for sid in previous - seen:
        row = conn.execute('SELECT payload FROM configured_sources WHERE id=?', (sid,)).fetchone()
        value = json.loads(row['payload'])
        value['enabled'] = False
        store(conn, 'sources', value)
        conn.execute('UPDATE configured_sources SET legacy_visible=0 WHERE id=?', (sid,))
    bump(conn)


def snapshot():
    ensure()
    with get_conn() as conn:
        conn.execute('BEGIN')
        data = {kind: records(conn, kind) for kind in TABLES}
        data['revision'] = revision(conn)
        tests = {r['id']: json.loads(r['last_test_json']) if r['last_test_json'] else None
                 for r in conn.execute('SELECT id,last_test_json FROM configured_sources')}
    jurisdictions = {r['id']: r for r in data['jurisdictions']}
    organisations = {r['id']: r for r in data['organisations']}
    for value in data['sources']:
        value['effective_enabled'] = effective(value, jurisdictions, organisations)
        value['collection_status'] = ('paused' if not value['effective_enabled'] else
            'news_pipeline' if compatible(value) else 'adapter_pending')
        value['last_test'] = tests[value['id']]
    return data


def validate_graph(data):
    jurisdictions = {r['id']: r for r in data['jurisdictions']}
    organisations = {r['id']: r for r in data['organisations']}
    if len({r['code'] for r in data['jurisdictions']}) != len(jurisdictions):
        raise ValueError('Jurisdiction codes must be unique.')
    for org in organisations.values():
        if org['jurisdiction_id'] not in jurisdictions:
            raise ValueError('Organisation jurisdiction does not exist.')
        current, seen = org, set()
        while current:
            if current['id'] in seen:
                raise ValueError('Organisation hierarchy cannot contain cycles.')
            seen.add(current['id'])
            parent = current.get('parent_id')
            if not parent:
                break
            current = organisations.get(parent)
            if not current or current['jurisdiction_id'] != org['jurisdiction_id']:
                raise ValueError('Parent organisation must belong to the same jurisdiction.')
    for source in data['sources']:
        jid, oid = source.get('jurisdiction_id'), source.get('organisation_id')
        if jid and jid not in jurisdictions:
            raise ValueError('Source jurisdiction does not exist.')
        if oid and (oid not in organisations or organisations[oid]['jurisdiction_id'] != jid):
            raise ValueError('Source organisation must belong to its jurisdiction.')


def apply(expected_revision, changes, importing=False):
    ensure()
    with get_conn() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if expected_revision != revision(conn):
            raise Conflict('Configuration changed in another window. Reload before saving.')
        data = {kind: records(conn, kind) for kind in TABLES}
        updates = {}
        for kind, items in changes.items():
            current = {r['id']: r for r in data[kind]}
            updates[kind] = []
            ids = set()
            for item in items:
                value = MODELS[kind].model_validate(item).model_dump()
                sid = value['id']
                if importing and not sid:
                    raise ValueError('Every imported record must have a stable ID. Use the editor to create new records.')
                if sid and sid not in current and not importing:
                    raise ValueError('Record no longer exists. Reload the configuration.')
                value['id'] = sid or uuid4().hex
                if value['id'] in ids:
                    raise ValueError('Duplicate IDs in import.')
                ids.add(value['id'])
                current[value['id']] = value
                updates[kind].append(value)
            data[kind] = list(current.values())
        validate_graph(data)
        for kind, items in updates.items():
            for value in items:
                store(conn, kind, value)
                if kind == 'sources':
                    row = conn.execute('SELECT legacy_json FROM configured_sources WHERE id=?', (value['id'],)).fetchone()
                    legacy = json.loads(row['legacy_json'])
                    legacy.setdefault('manual_override', True)
                    # Legacy scraper reads homepage; respect the exact configured list URL.
                    if value['method'] == 'html_list':
                        legacy['homepage'] = value['url']
                    conn.execute('UPDATE configured_sources SET legacy_visible=1,last_test_json=NULL,legacy_json=? WHERE id=?',
                                 (json.dumps(legacy), value['id']))
        bump(conn)
    return snapshot()


def export_config():
    ensure()
    with get_conn() as conn:
        conn.execute('BEGIN')
        return {'version': 1, **{kind: records(conn, kind) for kind in TABLES}}


def import_config(bundle, expected_revision):
    bundle = ConfigBundle.model_validate(bundle)
    return apply(expected_revision, {kind: [v.model_dump() for v in getattr(bundle, kind)] for kind in TABLES}, importing=True)
