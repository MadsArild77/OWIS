"""Persisted morning briefs and a once-per-Oslo-day background runner."""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from uuid import uuid4
from zoneinfo import ZoneInfo

from owis.core.storage.db import get_conn
from owis.modules.news.processing import governance

OSLO = ZoneInfo('Europe/Oslo')
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='owis-morning')
LEASE = timedelta(hours=2)
logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def schedule_info():
    return {'enabled': os.getenv('OWI_MORNING_REPORT_ENABLED', 'false').lower() == 'true',
            'hour': 6, 'timezone': 'Europe/Oslo'}


def read(report_date=None):
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM news_morning_reports WHERE report_date=?', (report_date,)).fetchone() if report_date else conn.execute(
            'SELECT * FROM news_morning_reports ORDER BY report_date DESC LIMIT 1').fetchone()
    state = {'status': 'not_started', 'result': None, 'schedule': schedule_info()}
    if row:
        state.update({k: row[k] for k in ('report_date', 'status', 'started_at', 'completed_at', 'error')})
        state['result'] = json.loads(row['result_json']) if row['result_json'] else None
        if row['status'] == 'running' and timestamp(row['started_at']) < utcnow() - LEASE:
            state.update(status='failed', error='Report generation was interrupted. Generate again to retry.')
    return state


def history():
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(
            'SELECT report_date,status,completed_at FROM news_morning_reports ORDER BY report_date DESC LIMIT 30')]


def start(refresh=False, now=None, synchronous=False):
    now = now or utcnow()
    day = now.astimezone(OSLO).date().isoformat()
    run_id = uuid4().hex
    with get_conn() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM news_morning_reports WHERE report_date=?', (day,)).fetchone()
        if row:
            started = timestamp(row['started_at'])
            active = row['status'] == 'running' and started > now - LEASE
            if active or (not refresh and row['status'] != 'running'):
                return read(day)
            if started > now - timedelta(minutes=5):
                raise ValueError('Please wait five minutes before generating another report.')
        conn.execute('''INSERT INTO news_morning_reports(report_date,status,started_at,run_id)
            VALUES(?,'running',?,?) ON CONFLICT(report_date) DO UPDATE SET
            status='running',started_at=excluded.started_at,run_id=excluded.run_id,error=NULL''',
                     (day, now.isoformat(), run_id))
    if synchronous:
        run(day, run_id, now)
    else:
        EXECUTOR.submit(run, day, run_id, now)
    return read(day)


def refresh_news():
    """Use existing collectors, but bound processing and avoid retention side effects."""
    from owis.modules.news.collectors.rss_fetcher import fetch_rss_items_with_report
    from owis.modules.news.collectors.scrape_fetcher import fetch_scrape_items_with_report
    from owis.modules.news.storage.repository import NewsRepository
    from owis.modules.news.processing.content import prepare
    from owis.modules.news.processing.pipeline import process_raw_item
    repo = NewsRepository()
    source_report, warnings = [], []
    cutoff = utcnow() - timedelta(days=2)
    for collector in (fetch_rss_items_with_report, fetch_scrape_items_with_report):
        try:
            items, health = collector()
            source_report.extend(health)
            for item in items:
                published = timestamp(item.get('published_at'))
                if not published or published >= cutoff:
                    repo.upsert_raw_item(item)
        except Exception:
            logger.exception('Morning news collection failed')
            warnings.append('A news collector failed; the last 24 hours may be incomplete.')
    errors = 0
    for raw in repo.list_unprocessed_raw(limit=100):
        try:
            repo.save_processed_item(process_raw_item(prepare(raw)))
            repo.mark_raw_processed(raw['id'])
        except Exception:
            errors += 1
    if errors:
        warnings.append(f'{errors} articles could not be processed.')
    if repo.list_unprocessed_raw(limit=1):
        warnings.append('Unprocessed articles remain; this report may be incomplete (100-article processing limit).')
    if not source_report:
        warnings.append('No news-source health reports available.')
    if any(row.get('error') for row in source_report):
        warnings.append('Some news sources failed; see source coverage.')
    from owis.modules.news.presentation.api import run_matching_after_fetch
    matching = run_matching_after_fetch()  # group coverage of the same story before the report is built
    if matching.get('skipped') and matching['skipped'] != 'AI is not enabled':
        warnings.append('Stories from different sources could not be grouped automatically this time.')
    return source_report, warnings


def recent_news(as_of):
    lower = as_of - timedelta(hours=24)
    with get_conn() as conn:
        rows = conn.execute('''SELECT p.id,p.title,p.summary,p.why_it_matters,p.signal_score,
            r.source_name,r.article_url,r.published_at,r.fetched_at,o.collection_key
            FROM news_processed_items p JOIN news_raw_items r ON r.id=p.raw_item_id
            LEFT JOIN news_collection_overrides o ON o.processed_id=p.id
            WHERE NOT EXISTS (SELECT 1 FROM news_item_relevance x WHERE x.processed_id=p.id AND x.relevance=0)
            AND NOT EXISTS (SELECT 1 FROM news_editorial_state s JOIN news_editorial_events e ON e.id=s.event_id
                WHERE s.processed_id=p.id AND e.value='non_relevant' AND s.topic='all')
            ORDER BY p.signal_score DESC,r.published_at DESC''').fetchall()
    groups, uncertain = {}, 0
    for record in rows:
        row = dict(record)
        published = timestamp(row['published_at'])
        if not published:
            fetched = timestamp(row['fetched_at'])
            if fetched and lower <= fetched <= as_of:
                uncertain += 1
            continue
        if not lower <= published < as_of:
            continue
        key = row.pop('collection_key') or row['article_url']
        source = {k: row[k] for k in ('id', 'source_name', 'article_url', 'published_at')}
        if key in groups:
            groups[key]['sources'].append(source)
        else:
            groups[key] = {**row, 'sources': [source]}
    return list(groups.values()), uncertain


def build(as_of, source_report, warnings, policy):
    stories, uncertain = recent_news(as_of)
    if uncertain:
        warnings = [*warnings, f'{uncertain} newly collected articles lack an exact publication timestamp and are excluded from the 24-hour window.']
    day = as_of.astimezone(OSLO).date().isoformat()
    events = sorted(policy['events'], key=lambda e: (
        {'Norway': 0, 'EU': 1, 'Nordics': 2, 'Europe': 3}.get(e['region'], 4),
        e['event_date'] or '9999', e['title']))
    return {'report_date': day, 'window_start': (as_of - timedelta(hours=24)).isoformat(),
            'window_end': as_of.isoformat(), 'generated_at': utcnow().isoformat(),
            'timezone': 'Europe/Oslo', 'news': stories[:30], 'news_total': len(stories),
            'today': [e for e in events if e['event_date'] == day],
            'upcoming': [e for e in events if e['event_date'] and e['event_date'] > day],
            'watchlist': [e for e in events if not e['event_date']],
            'policy_coverage': policy['coverage'], 'news_coverage': source_report,
            'warnings': [*warnings, *policy['warnings']],
            'coverage_note': 'Targeted official-source discovery, not a complete legal calendar. Norway and EU are prioritised; Nordic and other European coverage depends on the listed sources. Dates and legal status are AI-extracted; check the cited original before acting.'}


def run(day, run_id, as_of):
    try:
        source_report, warnings = refresh_news()
        policy = governance.collect(as_of.astimezone(OSLO).date())
        result = build(as_of, source_report, warnings, policy)
        with get_conn() as conn:
            conn.execute('''UPDATE news_morning_reports SET status='completed',completed_at=?,result_json=?,error=NULL
                WHERE report_date=? AND run_id=?''', (utcnow().isoformat(), json.dumps(result, ensure_ascii=False), day, run_id))
    except Exception:
        logger.exception('Morning report generation failed')
        with get_conn() as conn:
            conn.execute("UPDATE news_morning_reports SET status='failed',error=? WHERE report_date=? AND run_id=?",
                         ('Report generation failed. Previous saved report, if any, is preserved.', day, run_id))


def tick(now=None):
    now = now or utcnow()
    if schedule_info()['enabled'] and now.astimezone(OSLO).hour >= 6:
        # The database claim prevents duplicate runs across app workers/restarts.
        start(now=now)


def start_scheduler():
    stop = Event()
    def loop():
        while not stop.is_set():
            try:
                tick()
            except Exception:
                logger.exception('Morning scheduler tick failed')
            stop.wait(60)
    if schedule_info()['enabled']:
        Thread(target=loop, name='owis-morning-clock', daemon=True).start()
    return stop
