"""Persistent source attempts, shared by web jobs and scheduled collectors."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from owis.core.storage.db import get_conn

SCHEMA = """CREATE TABLE IF NOT EXISTS news_source_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL,
    source_url TEXT NOT NULL, operation TEXT NOT NULL, status TEXT NOT NULL,
    category TEXT NOT NULL, http_status INTEGER, message TEXT NOT NULL,
    items INTEGER, created_at TEXT NOT NULL
)"""


def safe_url(value):
    try:
        p = urlsplit(str(value))
        return urlunsplit((p.scheme, p.hostname or '', p.path, '', ''))
    except ValueError:
        return '[invalid URL]'


def safe_message(value):
    message = re.sub(r'https?://[^\s<>\"\']+', lambda m: safe_url(m.group()), str(value or ''))
    return re.sub(r'(?i)(token|api[_-]?key|password|authorization)([=:]\s*)[^\s,;]+', r'\1\2[redacted]', message)[:2000]


def error_message(exc):
    response = getattr(exc, 'response', None)
    if response is not None:
        return f'HTTP {response.status_code}: {exc.__class__.__name__}'
    return safe_message(f'{exc.__class__.__name__}: {exc}')


def record_attempts(rows, operation):
    with get_conn() as conn:
        conn.execute(SCHEMA)
        conn.execute('CREATE INDEX IF NOT EXISTS source_events_url_id ON news_source_events(source_url,id)')
        for row in rows:
            message = safe_message(row.get('error') or row.get('detail'))
            failed = row.get('status') not in {'ok', 'healthy'}
            match = re.search(r'(?i)(?:http[_ :]+|status[^0-9]{0,12})([45][0-9]{2})', message)
            code = int(match.group(1)) if match else None
            low = message.lower()
            category = ('http' if code else 'timeout' if 'timeout' in low else
                        'connection' if any(x in low for x in ('connect', 'dns', 'ssl')) else
                        'invalid_feed' if any(x in low for x in ('rss', 'atom', 'parse')) else
                        'access' if any(x in low for x in ('paywall', 'forbidden')) else 'other') if failed else 'none'
            status = 'error' if failed else 'empty' if row.get('items') == 0 else 'ok'
            conn.execute("""INSERT INTO news_source_events
                (source_name,source_url,operation,status,category,http_status,message,items,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (
                row.get('source', 'unknown'), safe_url(row.get('url') or row.get('homepage') or ''),
                operation, status, category, code, message, row.get('items'),
                datetime.now(timezone.utc).isoformat()))


def list_events(source_url=None, limit=100):
    with get_conn() as conn:
        conn.execute(SCHEMA)
        conn.execute('CREATE INDEX IF NOT EXISTS source_events_url_id ON news_source_events(source_url,id)')
        where = 'WHERE source_url = ?' if source_url is not None else ''
        args = [safe_url(source_url)] if source_url is not None else []
        return [dict(row) for row in conn.execute(
            f'SELECT * FROM news_source_events {where} ORDER BY id DESC LIMIT ?',
            [*args, max(1, min(limit, 500))])]
