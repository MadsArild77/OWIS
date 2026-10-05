import pytest
from fastapi.testclient import TestClient

from owis.apps.api.main import app
from owis.core.storage import db
from owis.scripts.backup_database import prune_startup_backups


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'access.db'))
    monkeypatch.setenv('OWI_MORNING_REPORT_ENABLED', 'false')
    monkeypatch.delenv('RAILWAY_ENVIRONMENT_ID', raising=False)
    with TestClient(app) as c:
        yield c


def test_open_without_password(client, monkeypatch):
    monkeypatch.delenv('OWI_ACCESS_PASSWORD', raising=False)
    assert client.get('/news').status_code == 200


def test_password_required_when_configured(client, monkeypatch):
    monkeypatch.setenv('OWI_ACCESS_PASSWORD', 'test-secret')
    denied = client.get('/news')
    assert denied.status_code == 401
    assert denied.headers['www-authenticate'].startswith('Basic')
    assert client.get('/api/source-config').status_code == 401
    assert client.get('/news', auth=('owis', 'wrong')).status_code == 401
    assert client.get('/news', auth=('other', 'test-secret')).status_code == 401
    assert client.get('/news', auth=('owis', 'test-secret')).status_code == 200


def test_custom_user_and_open_health(client, monkeypatch):
    monkeypatch.setenv('OWI_ACCESS_PASSWORD', 'test-secret')
    monkeypatch.setenv('OWI_ACCESS_USER', 'mads')
    assert client.get('/health').status_code == 200
    assert client.get('/news', auth=('mads', 'test-secret')).status_code == 200
    assert client.get('/news', headers={'Authorization': 'Basic not-base64!'}).status_code == 401


def test_prune_startup_backups_keeps_newest(tmp_path):
    for day in range(1, 21):
        (tmp_path / f'startup-2026-09-{day:02d}.db').write_bytes(b'x')
    (tmp_path / 'owi-manual.db').write_bytes(b'x')
    prune_startup_backups(tmp_path, keep=14)
    left = sorted(p.name for p in tmp_path.glob('startup-*.db'))
    assert len(left) == 14 and left[0] == 'startup-2026-09-07.db'
    assert (tmp_path / 'owi-manual.db').exists()
