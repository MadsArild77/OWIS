import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
from owis.core.storage.db import get_conn


def save(raw_id, url, title, publisher, access, basis, text, suggest=False):
    """Keep original evidence even if a later retrieval changes the article."""
    now=datetime.now(timezone.utc).isoformat()
    digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
    with get_conn() as c:
        c.execute('''INSERT OR IGNORE INTO news_source_evidence
            (raw_id,url,title,publisher,access,basis,content_hash,text,checked_at) VALUES(?,?,?,?,?,?,?,?,?)''',
            (raw_id,url,title,publisher,access,basis,digest,text,now))
        row=c.execute('''SELECT id FROM news_source_evidence WHERE raw_id=? AND url=? AND content_hash=? AND access=? AND basis=?''',
                      (raw_id,url,digest,access,basis)).fetchone()
        if suggest:
            hostname=urlparse(url).hostname or ''
            c.execute('INSERT OR IGNORE INTO news_source_suggestions(hostname,example_url,discovered_at) VALUES(?,?,?)',(hostname,url,now))
        return row['id']
