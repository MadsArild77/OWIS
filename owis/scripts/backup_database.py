"""Consistent SQLite backup including preferences, sources and drafts."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from owis.core.storage import db

def backup(destination=None):
    source=Path(db.DB_PATH).resolve()
    target=Path(destination) if destination else source.parent/'backups'/f"owi-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}.db"
    if target.resolve()==source:raise ValueError('Backup must differ from live database')
    if not source.exists():raise FileNotFoundError(source)
    target.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity check failed')
    return target

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output');args=p.parse_args()
    print(backup(args.output))
