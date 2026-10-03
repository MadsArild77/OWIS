"""Bounded public source previews, without creating articles or spending AI calls."""
import json
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx
from bs4 import BeautifulSoup

from owis.core.sources.models import Source
from owis.core.sources import registry
from owis.core.storage.db import get_conn


def fetch(url):
    from owis.modules.news.processing.content import public_url
    with httpx.Client(timeout=httpx.Timeout(12, connect=5), follow_redirects=False,
                      trust_env=False, headers={'User-Agent': 'OWIS/1.0 SourcePreview'}) as client:
        for _ in range(4):
            public_url(url)  # Validate each redirect, not only the submitted URL.
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers['location'])
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError('Source exceeds the 2 MB preview limit.')
                    chunks.append(chunk)
                return b''.join(chunks), url, response.headers.get('content-type', ''), response.encoding or 'utf-8'
    raise ValueError('Too many redirects.')


def preview(value):
    source = Source.model_validate(value)
    if source.method in {'ics', 'api'}:
        return {'status': 'unsupported', 'message': 'Configuration can be saved. This preview adapter is not implemented yet.', 'items': []}
    raw, url, content_type, encoding = fetch(source.url)
    if source.method == 'rss':
        feed = feedparser.parse(raw)
        if not feed.get('version'):
            raise ValueError('The URL did not return an RSS or Atom feed.')
        items = [{'title': str(entry.get('title', '')), 'url': str(entry.get('link', '')),
                  'text': BeautifulSoup(str(entry.get('summary', '')), 'html.parser').get_text(' ', strip=True)[:700]}
                 for entry in feed.entries[:5]]
        return {'status': 'ok' if items else 'empty', 'message': f'RSS/Atom preview: {len(feed.entries)} entries. Showing up to five.', 'items': items}
    if 'html' not in content_type.lower():
        raise ValueError('The URL did not return HTML. PDF and other document adapters are not available yet.')
    soup = BeautifulSoup(raw.decode(encoding, errors='replace'), 'html.parser')
    if any(x in soup.get_text(' ', strip=True).lower() for x in ('verify you are human', 'checking your browser', 'enable javascript and cookies')):
        raise ValueError('The source returned an access challenge instead of content.')
    nodes = soup.select(source.selector) if source.selector else [soup.find('main') or soup.find('article') or soup.body or soup]
    items = []
    if source.method == 'html_list':
        seen = set()
        for node in nodes:
            for anchor in ([node] if node.name == 'a' and node.has_attr('href') else node.select('a[href]')):
                target = urljoin(url, anchor['href'])
                title = anchor.get_text(' ', strip=True)
                if title and target not in seen and urlsplit(target).scheme in {'http', 'https'}:
                    seen.add(target)
                    items.append({'title': title[:240], 'url': target, 'text': ''})
                if len(items) >= 5:
                    break
            if len(items) >= 5:
                break
    else:
        for node in nodes:
            for tag in node.select('script,style,nav,footer,header'):
                tag.decompose()
        text = '\n'.join(node.get_text(' ', strip=True) for node in nodes)
        if text.strip():
            items = [{'title': soup.title.get_text(' ', strip=True) if soup.title else source.name,
                      'url': url, 'text': text[:2000]}]
    return {'status': 'ok' if items else 'empty',
            'message': 'HTML preview only. Links/text are not yet parsed as calendar events or legal records. No AI analysis was run.',
            'items': items}


def test_source(value):
    value = Source.model_validate(value).model_dump()
    try:
        result = preview(value)
    except httpx.HTTPStatusError as error:
        result = {'status': 'error', 'message': f'HTTP {error.response.status_code}: source could not be read.', 'items': []}
    except httpx.HTTPError:
        result = {'status': 'error', 'message': 'Connection or timeout error while reading the source.', 'items': []}
    except ValueError as error:
        result = {'status': 'error', 'message': str(error), 'items': []}
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    # A test of unsaved edits must not become the status of the saved source.
    if value['id']:
        with get_conn() as conn:
            row = conn.execute('SELECT payload FROM configured_sources WHERE id=?', (value['id'],)).fetchone()
            if row and json.loads(row['payload']) == value:
                conn.execute('UPDATE configured_sources SET last_test_json=? WHERE id=? AND payload=?',
                             (json.dumps(result), value['id'], row['payload']))
    return result
