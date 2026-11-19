import sqlite3

from owis.core.storage import db
from owis.scripts.backup_database import backup


def test_database_uses_wal_and_waits_for_locks():
    with db.get_conn() as conn:
        assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == db.BUSY_TIMEOUT_SECONDS * 1000


def test_reader_is_not_blocked_by_open_write():
    with db.get_conn() as writer:
        writer.execute("INSERT INTO source_config_meta (key, value) VALUES ('k', 'v')")
        reader = sqlite3.connect(db.DB_PATH, timeout=0)
        try:
            assert reader.execute('SELECT COUNT(*) FROM source_config_meta').fetchone()[0] == 0
        finally:
            reader.close()


def test_backup_includes_recent_writes(tmp_path):
    with db.get_conn() as conn:
        conn.execute("INSERT INTO source_config_meta (key, value) VALUES ('kept', 'yes')")
    target = backup(tmp_path / 'copy.db')
    with sqlite3.connect(target) as copy:
        assert copy.execute("SELECT value FROM source_config_meta WHERE key = 'kept'").fetchone()[0] == 'yes'
