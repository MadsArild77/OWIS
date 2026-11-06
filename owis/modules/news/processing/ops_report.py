"""Read-only operational report, shared by the API and command line."""
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from owis.modules.news.processing.search_budget import _number

OSLO = ZoneInfo('Europe/Oslo')
NO_DATA = 'No data in this period.'
NOT_RECORDED = 'Not recorded'


def timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def percent(count, total):
    return round(100 * count / total) if total else None


def build_report(conn, days=30, now=None):
    if not 1 <= days <= 366:
        raise ValueError('Days must be between 1 and 366.')
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(OSLO).date()
    dates = [today - timedelta(days=i) for i in reversed(range(days))]
    start = datetime.combine(dates[0], datetime.min.time(), OSLO)

    def rows(table, columns='*'):
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            return []
        cursor = conn.execute('SELECT ' + columns + ' FROM ' + table)
        names = [c[0] for c in cursor.description]
        return [dict(zip(names, row)) for row in cursor]

    def in_period(value):
        dt = timestamp(value)
        return dt is not None and start <= dt <= now

    reports = {r['report_date']: r for r in rows('news_morning_reports')}
    morning = []
    delivered = 0
    for day in dates:
        row = reports.get(day.isoformat(), {})
        done = timestamp(row.get('completed_at'))
        done = done.astimezone(OSLO) if done else None
        state = row.get('status', 'missing')
        if state == 'running':
            started = timestamp(row.get('started_at'))
            state = 'failed' if started and started < now - timedelta(hours=2) else NOT_RECORDED
        result = json.loads(row.get('result_json') or '{}') or {}
        delivered += int(state == 'completed' and done is not None and done.date() == day
                         and done <= datetime.combine(day, datetime.min.time(), OSLO) + timedelta(hours=7))
        morning.append([day.isoformat(), state, done.strftime('%H:%M') if done else None,
                        result.get('news_total'), ('AI' if (result.get('brief') or {}).get('ai') else 'Fallback')
                        if result else None])

    raw = rows('news_raw_items', 'id,source_name,fetched_at')
    articles = [r for r in raw if in_period(r['fetched_at'])]
    fetched = defaultdict(int)
    latest = {}
    for row in raw:
        dt = timestamp(row['fetched_at'])
        if dt and dt <= now:
            latest[row['source_name']] = max(dt, latest.get(row['source_name'], dt))
    for row in articles:
        fetched[timestamp(row['fetched_at']).astimezone(OSLO).date().isoformat()] += 1
    sources = set(latest)
    sources.update(r['source_name'] for r in rows('source_fetch_health'))
    for row in rows('news_source_registry'):
        source = json.loads(row['source_json'])
        if source.get('name'):
            sources.add(source['name'])
    stale = [[name, latest[name].astimezone(OSLO).date().isoformat() if name in latest else NOT_RECORDED]
             for name in sorted(sources) if name not in latest or latest[name] < now - timedelta(days=7)]

    basis = {r['raw_id']: r for r in rows('news_content_basis', 'raw_id,basis,access')}
    weeks, by_source = defaultdict(list), defaultdict(list)
    for row in articles:
        day = timestamp(row['fetched_at']).astimezone(OSLO).date()
        weeks[(day - timedelta(days=day.weekday())).isoformat()].append(row)
        by_source[row['source_name']].append(row)

    def coverage(group):
        records = [basis.get(r['id'], {}) for r in group]
        full = sum(r.get('basis') in {'fulltext', 'alternative_fulltext', 'feed_text'} for r in records)
        excerpt = sum(r.get('basis') == 'feed_excerpt' for r in records)
        paywall = sum(r.get('access') == 'restricted' for r in records)
        return [len(group), percent(full, len(group)), percent(excerpt, len(group)),
                percent(paywall, len(group)), sum(not r for r in records)]

    weekly = [[week, *coverage(group)] for week, group in sorted(weeks.items())]
    source_coverage = [[name, *coverage(group)] for name, group in by_source.items()]
    source_coverage.sort(key=lambda r: (r[2], r[0]))
    ids = {r['id'] for r in articles}
    processed = rows('news_processed_items', 'id,raw_item_id,title,signal_score')
    scored = [r for r in processed if r['raw_item_id'] in ids]
    domains = {r['processed_id']: r['domain_bucket'] for r in rows('news_domain_classification')}
    core = [r for r in scored if domains.get(r['id']) in {'offshore_wind', 'adjacent_energy'}]
    scores = [[label, sum(lo <= r['signal_score'] <= hi for r in scored),
               sum(lo <= r['signal_score'] <= hi for r in core)]
              for label, lo, hi in [('0–39', 0, 39), ('40–55', 40, 55), ('56–69', 56, 69),
                                    ('70–84', 70, 84), ('85–100', 85, 100)]]

    # Feedback retains automatic decisions even after the pair is reopened or rejudged.
    events = [r for r in rows('news_learning_feedback') if r['feedback_type'] == 'match_review_decision'
              and r['actor'] == 'auto' and in_period(r['created_at'])]
    merges = [r for r in events if r['feedback_value'] == 'accept']
    links = [r for r in events if r['feedback_value'] == 'link_update']
    pairs = {r['id']: r for r in rows('news_match_review_pairs')}
    items = {r['id']: r for r in processed}
    raw_map = {r['id']: r for r in raw}
    recent = []
    for event in sorted(merges, key=lambda r: timestamp(r['created_at']), reverse=True)[:50]:
        pair = pairs.get(event['pair_id'], {})
        a, b = items.get(pair.get('item_a_id'), {}), items.get(pair.get('item_b_id'), {})
        recent.append([a.get('title', NOT_RECORDED), raw_map.get(a.get('raw_item_id'), {}).get('source_name', NOT_RECORDED),
                       b.get('title', NOT_RECORDED), raw_map.get(b.get('raw_item_id'), {}).get('source_name', NOT_RECORDED),
                       percent(pair['ai_confidence'], 1) if pair.get('decided_at') == event['created_at'] else None,
                       timestamp(event['created_at']).astimezone(OSLO).isoformat()])
    month_start = now.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = sum(timestamp(r['used_at']) is not None and timestamp(r['used_at']) >= month_start
               for r in rows('news_search_usage'))

    def table(title, columns, data, percentages=()):
        return dict(title=title, columns=columns, rows=data, percentages=list(percentages))

    return {'days': days, 'from': dates[0].isoformat(), 'to': today.isoformat(), 'sections': [
        dict(title='Morning reports', summary=f'{delivered} of {days} days delivered by 07:00', tables=[
            table('', ['Date', 'Status', 'Completed (Europe/Oslo)', 'Stories', 'Summary'], morning)]),
        dict(title='Fetching', tables=[table('', ['Date', 'New articles'], [[d.isoformat(), fetched[d.isoformat()]] for d in dates]),
                                      table('Sources silent for 7 days', ['Source', 'Last article date'], stale)]),
        dict(title='Full text', tables=[table('By week (Monday–Sunday)', ['Week starting', 'Articles', 'Full text', 'Excerpt only', 'Paywall', 'Not recorded'], weekly, (2, 3, 4)),
                                       table('By source', ['Source', 'Articles', 'Full text', 'Excerpt only', 'Paywall', 'Not recorded'], source_coverage, (2, 3, 4))]),
        dict(title='Scores', tables=[table('', ['Score', 'All', 'Offshore wind & related'], scores if scored else []),
                                    table('', ['Metric', 'Share'], [['Offshore wind & related of all articles', percent(len(core), len(articles))]], (1,))]),
        dict(title='Merging', tables=[table('', ['Metric', 'Count'], [['Automatic merges', len(merges)], ['Automatic follow-up links', len(links)], ['Cases split again', NOT_RECORDED]]),
                                     table('Latest 50 automatic merges', ['Title A', 'Source A', 'Title B', 'Source B', 'AI confidence', 'Date'], recent, (4,))]),
        dict(title='Search budget', tables=[table('This month', ['Used', 'Limit'], [[used, _number('OWI_SEARCH_MONTHLY_LIMIT', '1000')]])])
    ]}


def read_report(db_path=None, days=30, now=None):
    if db_path is None:
        from owis.core.storage import db
        db_path = db.DB_PATH
    uri = Path(db_path).resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute('BEGIN')
        return build_report(conn, days, now)
    finally:
        conn.close()


def markdown(report):
    def cell(value, percentage=False):
        if value is None:
            return NOT_RECORDED
        return (str(value) + ('%' if percentage and isinstance(value, (int, float)) else '')).replace('|', '\\|').replace('\n', ' ')
    lines = [f"# System health ({report['from']} – {report['to']})"]
    for section in report['sections']:
        lines += ['', '## ' + section['title']]
        if section.get('summary'):
            lines += ['', section['summary']]
        for table in section['tables']:
            lines += ['', '### ' + table['title']] if table['title'] else ['']
            if not table['rows']:
                lines.append(NO_DATA)
                continue
            lines += ['| ' + ' | '.join(table['columns']) + ' |', '| ' + ' | '.join('---' for _ in table['columns']) + ' |']
            lines += ['| ' + ' | '.join(cell(v, i in table['percentages']) for i, v in enumerate(row)) + ' |' for row in table['rows']]
    return '\n'.join(lines) + '\n'
