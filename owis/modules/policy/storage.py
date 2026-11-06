"""Policy records and collection history."""
from datetime import datetime, timedelta, timezone

from owis.core.storage.db import get_conn
from owis.core.sources import registry


def ensure():
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS policy_items (
                id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
                summary TEXT NOT NULL, published_at TEXT, source_id TEXT NOT NULL,
                organisation_id TEXT, jurisdiction_id TEXT, content_type TEXT NOT NULL,
                first_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS policy_runs (
                id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, started_at TEXT NOT NULL,
                status TEXT NOT NULL, items_read INTEGER NOT NULL DEFAULT 0,
                items_saved INTEGER NOT NULL DEFAULT 0, items_filtered INTEGER NOT NULL DEFAULT 0,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS policy_runs_source ON policy_runs(source_id, id);
            CREATE TABLE IF NOT EXISTS policy_slots (slot TEXT PRIMARY KEY);
        ''')
        if 'deadline' not in {r['name'] for r in conn.execute('PRAGMA table_info(policy_items)')}:
            conn.execute('ALTER TABLE policy_items ADD COLUMN deadline TEXT')


def eligible(source):
    return (source['method'] in {'rss', 'html_list', 'api'} and 'news' not in source['content_types']
            and bool(set(source['content_types']) & {'regulation', 'consultation', 'calendar'}))


def following(source, organisations):
    mode, topics = source['follow'], source.get('topics') or []
    oid = source.get('organisation_id')
    while oid:
        org = organisations[oid]
        if mode == 'inherit':
            mode = org['follow']
        if not topics:
            topics = org.get('topics') or []
        oid = org.get('parent_id')
    return mode, topics


def region(jurisdiction):
    code = jurisdiction.get('code')
    if code in {'NO', 'EU'}:
        return 'Norway' if code == 'NO' else 'EU'
    groups = jurisdiction.get('groups', [])
    return next((g for g in ('Nordics', 'Asia-Pacific', 'Americas', 'Middle East') if g in groups), 'Europe')


def items(now=None, recent=False, snapshot=None):
    ensure()
    now = now or datetime.now(timezone.utc)
    field = 'first_seen_at' if recent else 'COALESCE(published_at,first_seen_at)'
    with get_conn() as conn:
        rows = conn.execute(f'''SELECT * FROM policy_items WHERE ({field} >= ? AND {field} <= ?)
            OR (content_type='consultation' AND deadline > ?)
            ORDER BY {field} DESC,id DESC''',
            ((now - timedelta(days=1 if recent else 30)).isoformat(), now.isoformat(), now.isoformat())).fetchall()
    if not rows:
        return []
    data = snapshot if snapshot is not None else registry.snapshot()
    orgs = {r['id']: r for r in data['organisations']}
    jurisdictions = {r['id']: r for r in data['jurisdictions']}
    sources = {r['id']: r for r in data['sources']}
    result = []
    for row in rows:
        item = dict(row)
        jurisdiction = jurisdictions.get(item['jurisdiction_id'], {})
        source = sources.get(item['source_id'], {})
        item.update(organisation=orgs.get(item['organisation_id'], {}).get('name', source.get('name', '')),
                    jurisdiction=jurisdiction.get('name', ''), region=region(jurisdiction),
                    follows_all=following(source, orgs)[0] == 'all' if source else False)
        result.append(item)
    if recent:
        def priority(row):
            deadline = row.get('deadline')
            urgent = row['content_type'] == 'consultation' and deadline and now.isoformat() < deadline <= (now + timedelta(days=14)).isoformat()
            return (not urgent, deadline if urgent else '', not row['follows_all'])
        result.sort(key=priority)
        return result[:40]
    return result


def source_status(snapshot):
    ensure()
    result = []
    with get_conn() as conn:
        for source in snapshot['sources']:
            if not eligible(source):
                continue
            runs = conn.execute('SELECT * FROM policy_runs WHERE source_id=? ORDER BY id DESC', (source['id'],)).fetchall()
            failures = 0
            for run in runs:
                if run['status'] != 'error':
                    break
                failures += 1
            last_saved = next((r['started_at'] for r in runs if r['items_saved']), None)
            result.append(dict(id=source['id'], name=source['name'],
                last_fetched=runs[0]['started_at'] if runs else None, last_saved=last_saved,
                error=runs[0]['error'] if runs else None, consecutive_failures=failures))
    return sorted(result, key=lambda r: (r['consecutive_failures'] < 3, r['name']))
