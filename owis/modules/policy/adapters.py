"""Public policy APIs, bounded to 500 records on their configured endpoint."""
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from owis.core.sources import probe


def adapter(url):
    parts = urlsplit(url)
    if parts.hostname == 'ec.europa.eu' and parts.path.endswith('/brpapi/searchInitiatives'):
        return 'hys'
    return {'oda.ft.dk': 'ft', 'gegevensmagazijn.tweedekamer.nl': 'tk',
            'data.stortinget.no': 'storting'}.get(parts.hostname)


def date(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('/', '-').replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def page_url(url, values):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(values)
    return urlunsplit(parts._replace(query=urlencode(query)))


def records(source, now=None, preview=False):
    now = now or datetime.now(timezone.utc)
    kind = adapter(source['url'])
    if kind == 'storting':
        return
    if not kind:
        raise ValueError('No adapter for this API')
    cutoff = now - timedelta(days=30)
    count, page = 0, 0
    while count < 500:
        size = min(100, 500 - count)
        params = {'page': page, 'size': size} if kind == 'hys' else {
            '$skip': count, '$top': size,
            '$orderby': ('opdateringsdato' if kind == 'ft' else 'GewijzigdOp') + ' desc'}
        raw, _, _, _ = probe.fetch(page_url(source['url'], params))
        data = json.loads(raw)
        container = data['initiativeResultDtoPage'] if kind == 'hys' else data
        rows = container['content' if kind == 'hys' else 'value']
        if not rows:
            break
        for row in rows[:size]:
            count += 1
            if kind == 'hys':
                periods = row.get('currentStatuses') or []
                current = next((p for p in periods if p.get('isCurrent')), {})
                opened = next((p for p in periods if p.get('receivingFeedbackStatus') == 'OPEN'
                    and date(p.get('feedbackStartDate')) and date(p.get('feedbackStartDate')) <= now
                    and date(p.get('feedbackEndDate')) and date(p.get('feedbackEndDate')) > now), None)
                dates = [date(p.get(k)) for p in periods for k in ('feedbackStartDate', 'feedbackEndDate') if p.get(k)]
                published = date(current.get('feedbackStartDate'))
                yield dict(title=row.get('shortTitle') or '', summary='',
                    url=f"https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/{int(row['id'])}",
                    published_at=published.isoformat() if published else None,
                    deadline=date(opened['feedbackEndDate']).isoformat() if opened else None,
                    content_type='consultation' if opened else 'regulation',
                    retain=bool(opened or (dates and cutoff <= max(dates) <= now)))
            else:
                published = date(row.get('opdateringsdato' if kind == 'ft' else 'GewijzigdOp'))
                if not preview and published and published < cutoff:
                    return
                if kind == 'ft':
                    title = row.get('titel') or ''
                    period = row.get('Periode') or {}
                    session = period.get('kode', '')
                    prefix, number = row.get('nummerprefix'), row.get('nummernumerisk')
                    url = (f'https://www.ft.dk/samling/{session}/{prefix}/{number}/index.htm'
                           if session and prefix and number else source['url'].split('?')[0] + f"({row['id']})?$format=json")
                    summary = row.get('resume') or ''
                else:
                    title = row.get('Onderwerp') or row.get('Titel') or ''
                    summary = row.get('Titel') or ''
                    url = 'https://www.tweedekamer.nl/kamerstukken/detail?id=' + (row.get('Nummer') or row['Id'])
                yield dict(title=title, summary=summary[:1000], url=url,
                    published_at=published.isoformat() if published else None)
        if preview or (kind == 'hys' and (container.get('last') is True
                or page + 1 >= container.get('totalPages', 501))):
            break
        page += 1
