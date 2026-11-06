"""Bounded RSS/HTML collection using the source preview's public fetch rules."""
import calendar
import logging
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser
from bs4 import BeautifulSoup

from owis.core.sources import probe, registry
from owis.core.storage.db import get_conn
from owis.modules.news.processing.fetch_scheduler import OSLO, schedule_info
from owis.modules.policy import storage, adapters

PRIORITY = {'regulation': 0, 'calendar': 1, 'consultation': 2}
CONSULTATION = ('consultation', 'call for evidence', 'request for comment', 'comment period', 'høringsfrist')
logger = logging.getLogger(__name__)


def normalize_url(value):
    parts = urlsplit(value)
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith('utm_')])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ''))


def parse(source):
    raw, url, content_type, encoding = probe.fetch(source['url'])
    if source['method'] == 'rss':
        feed = feedparser.parse(raw)
        if not feed.get('version'):
            raise ValueError('The URL did not return an RSS or Atom feed.')
        for entry in feed.entries:
            date = entry.get('published_parsed') or entry.get('updated_parsed')
            yield dict(title=BeautifulSoup(str(entry.get('title', '')), 'html.parser').get_text(' ', strip=True),
                url=urljoin(url, entry.get('link', '')) if entry.get('link') else '',
                summary=BeautifulSoup(str(entry.get('summary', '')), 'html.parser').get_text(' ', strip=True)[:1000],
                published_at=datetime.fromtimestamp(calendar.timegm(date), timezone.utc).isoformat() if date else None)
        return
    if 'html' not in content_type.lower():
        raise ValueError('The URL did not return HTML.')
    soup = BeautifulSoup(raw.decode(encoding, errors='replace'), 'html.parser')
    if any(x in soup.get_text(' ', strip=True).lower() for x in
           ('verify you are human', 'checking your browser', 'enable javascript and cookies')):
        raise ValueError('The source returned an access challenge instead of content.')
    nodes = soup.select(source['selector']) if source.get('selector') else [soup.find('main') or soup.find('article') or soup.body or soup]
    seen = set()
    for node in nodes:
        for anchor in ([node] if node.name == 'a' and node.has_attr('href') else node.select('a[href]')):
            target = urljoin(url, anchor['href'])
            title = anchor.get_text(' ', strip=True)
            if len(title) >= 15 and target not in seen and urlsplit(target).scheme in {'http', 'https'}:
                seen.add(target)
                yield dict(title=title[:240], url=target, summary='', published_at=None)


def collect(now=None):
    now = now or datetime.now(timezone.utc)
    storage.ensure()
    data = registry.snapshot()
    orgs = {r['id']: r for r in data['organisations']}
    jurisdictions = {r['id']: r for r in data['jurisdictions']}
    for source in data['sources']:
        if not storage.eligible(source) or not registry.effective(source, jurisdictions, orgs):
            continue
        with get_conn() as conn:
            conn.execute('BEGIN IMMEDIATE')
            last = conn.execute('SELECT started_at FROM policy_runs WHERE source_id=? ORDER BY id DESC LIMIT 1', (source['id'],)).fetchone()
            if last and datetime.fromisoformat(last['started_at']) > now - timedelta(minutes=source['interval_minutes']):
                continue
            first = not conn.execute("SELECT 1 FROM policy_runs WHERE source_id=? AND status='ok'", (source['id'],)).fetchone()
            run_id = conn.execute("INSERT INTO policy_runs(source_id,started_at,status) VALUES(?,?,'running')",
                                  (source['id'], now.isoformat())).lastrowid
        read, saved, filtered = 0, 0, 0
        try:
            api_kind = adapters.adapter(source['url']) if source['method'] == 'api' else None
            if api_kind == 'storting':
                with get_conn() as conn:
                    conn.execute("UPDATE policy_runs SET status='skipped',error=? WHERE id=?",
                                 ('Collected by the Storting tab (D25)', run_id))
                continue
            mode, topics = storage.following(source, orgs)
            parsed = []
            entries = adapters.records(source, now) if source['method'] == 'api' else parse(source)
            for item in entries:
                read += 1
                text = (item['title'] + ' ' + item['summary']).casefold()
                kind = item.get('content_type', source['content_types'][0])
                if api_kind != 'hys' and 'consultation' in source['content_types'] and any(word in text for word in CONSULTATION):
                    kind = 'consultation'
                url = normalize_url(item['url'])
                old = (api_kind != 'hys' and first and kind != 'calendar' and item['published_at']
                       and datetime.fromisoformat(item['published_at']) < now - timedelta(days=30))
                if not url or not item['title'] or old or (api_kind != 'hys' and mode != 'all' and not any(t.casefold() in text for t in topics if t.strip())):
                    filtered += 1
                    continue
                parsed.append({**item, 'url': url, 'content_type': kind})
            with get_conn() as conn:
                conn.execute('BEGIN IMMEDIATE')
                for item in parsed:
                    existing = conn.execute('SELECT id,content_type FROM policy_items WHERE url=?', (item['url'],)).fetchone()
                    if existing:
                        if api_kind == 'hys':
                            conn.execute('UPDATE policy_items SET content_type=?,deadline=?,published_at=? WHERE id=?',
                                (item['content_type'], item.get('deadline'), item['published_at'], existing['id']))
                        elif PRIORITY[item['content_type']] > PRIORITY[existing['content_type']]:
                            conn.execute('UPDATE policy_items SET content_type=? WHERE id=?', (item['content_type'], existing['id']))
                        continue
                    if not item.get('retain', True):
                        filtered += 1
                        continue
                    conn.execute('''INSERT INTO policy_items(url,title,summary,published_at,source_id,
                        organisation_id,jurisdiction_id,content_type,first_seen_at,deadline) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                        (item['url'], item['title'], item['summary'], item['published_at'], source['id'],
                         source.get('organisation_id'), source.get('jurisdiction_id'), item['content_type'], now.isoformat(), item.get('deadline')))
                    saved += 1
                conn.execute("UPDATE policy_runs SET status='ok',items_read=?,items_saved=?,items_filtered=? WHERE id=?",
                             (read, saved, filtered, run_id))
        except Exception as error:
            with get_conn() as conn:
                conn.execute("UPDATE policy_runs SET status='error',items_read=?,items_filtered=?,error=? WHERE id=?",
                             (read, filtered, str(error)[:1000], run_id))


def tick(now=None):
    now = now or datetime.now(timezone.utc)
    info = schedule_info()
    local = now.astimezone(OSLO)
    passed = [h for h in info['hours'] if h <= local.hour]
    if not info['enabled'] or not passed:
        return False
    storage.ensure()
    with get_conn() as conn:
        if not conn.execute('INSERT OR IGNORE INTO policy_slots VALUES(?)',
                            (f'{local.date()}:{passed[-1]:02d}',)).rowcount:
            return False
    collect(now)
    return True


def start_scheduler():
    stop = Event()
    def loop():
        while not stop.is_set():
            try:
                tick()
            except Exception:
                logger.exception('Scheduled policy collection failed')
            stop.wait(60)
    if schedule_info()['enabled']:
        Thread(target=loop, name='owis-policy-clock', daemon=True).start()
    return stop
