import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from owis.core.storage import db
from owis.modules.news.processing.ops_report import build_report, markdown, read_report

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


def insert(conn, table, **values):
    columns = ','.join(values)
    conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))


def tables(report, section):
    return next(s['tables'] for s in report['sections'] if s['title'] == section)


def test_known_database_every_metric(monkeypatch):
    monkeypatch.setenv('OWI_SEARCH_MONTHLY_LIMIT', '123')
    with db.get_conn() as conn:
        for day, status, completed, result in [
            ('2026-10-24', 'completed', '2026-10-24T05:00:00Z', {'news_total': 4, 'brief': {'ai': True}}),
            ('2026-10-25', 'completed', '2026-10-25T06:01:00Z', {'news_total': 3, 'brief': {'ai': False}}),
            ('2026-10-26', 'failed', None, None),
        ]:
            insert(conn, 'news_morning_reports', report_date=day, status=status, completed_at=completed,
                   started_at=day + 'T04:00:00Z', run_id=day, result_json=json.dumps(result) if result else None)
        for i, (score, basis, access, source, fetched, domain) in enumerate([
            (39, 'fulltext', 'open', 'A', '2026-10-24T12:00:00Z', 'offshore_wind'),
            (40, 'feed_excerpt', 'restricted', 'B', '2026-10-25T12:00:00Z', 'other_energy'),
            (55, 'alternative_fulltext', 'restricted', 'A', '2026-10-25T13:00:00Z', 'adjacent_energy'),
            (56, 'feed_text', 'unknown', 'A', '2026-10-26T12:00:00Z', 'offshore_wind'),
            (69, 'feed_excerpt', 'blocked', 'B', '2026-10-26T13:00:00Z', 'other_energy'),
            (70, None, None, 'B', '2026-10-27T10:00:00Z', 'other_energy'),
            (84, 'fulltext', 'open', 'A', '2026-10-27T11:00:00Z', 'offshore_wind'),
            (85, 'fulltext', 'open', 'A', '2026-10-27T11:01:00Z', 'adjacent_energy'),
            (100, 'fulltext', 'open', 'A', '2026-10-27T11:02:00Z', 'offshore_wind'),
        ], 1):
            insert(conn, 'news_raw_items', id=i, source_name=source, article_url=f'https://example.test/{i}',
                   title_raw=f'Title {i}', content_hash=str(i), fetched_at=fetched)
            insert(conn, 'news_processed_items', id=i, raw_item_id=i, title=f'Title {i}', cleaned_text='',
                   summary='', theme_tags='', geography_tags='', actors='', why_it_matters='', signal_score=score,
                   confidence=1, linkedin_angle='', linkedin_candidate=0, processed_at=fetched)
            insert(conn, 'news_domain_classification', processed_id=i, domain_bucket=domain, domain_confidence=1, classified_at=fetched)
            if basis:
                insert(conn, 'news_content_basis', raw_id=i, relevance='relevant', reason='', access=access,
                       basis=basis, text='', source_url='', checked_at=fetched)
        insert(conn, 'news_raw_items', id=10, source_name='Old', article_url='https://example.test/old',
               title_raw='Old', content_hash='old', fetched_at='2026-10-01T10:00:00Z')
        insert(conn, 'news_source_registry', position=0, source_json='{"name":"Never"}', updated_at=NOW.isoformat())
        for i, value, actor in [(1, 'accept', 'auto'), (2, 'link_update', 'auto'), (3, 'accept', 'user')]:
            insert(conn, 'news_match_review_pairs', id=i, item_a_id=1, item_b_id=i+1, ai_same_story='yes',
                   ai_confidence=.96, status='accepted', decided_by=actor, decided_at=NOW.isoformat(), created_at=NOW.isoformat())
            insert(conn, 'news_learning_feedback', pair_id=i, feedback_type='match_review_decision',
                   feedback_value=value, actor=actor, created_at=NOW.isoformat())
        insert(conn, 'news_search_usage', purpose='research', used_at=NOW.isoformat())
        insert(conn, 'news_search_usage', purpose='extract', used_at='2026-09-30T23:00:00Z')
    report = read_report(days=4, now=NOW)
    assert [s['title'] for s in report['sections']] == ['Morning reports', 'Fetching', 'Full text', 'Scores', 'Merging', 'Search budget']
    assert report['sections'][0]['summary'] == '1 of 4 days delivered by 07:00'
    assert tables(report, 'Morning reports')[0]['rows'] == [
        ['2026-10-24', 'completed', '07:00', 4, 'AI'], ['2026-10-25', 'completed', '07:01', 3, 'Fallback'],
        ['2026-10-26', 'failed', None, None, None], ['2026-10-27', 'missing', None, None, None]]
    assert tables(report, 'Fetching')[0]['rows'] == [['2026-10-24', 1], ['2026-10-25', 2], ['2026-10-26', 2], ['2026-10-27', 4]]
    assert tables(report, 'Fetching')[1]['rows'] == [['Never', 'Not recorded'], ['Old', '2026-10-01']]
    assert tables(report, 'Full text')[0]['rows'] == [['2026-10-19', 3, 67, 33, 67, 0], ['2026-10-26', 6, 67, 17, 0, 1]]
    assert tables(report, 'Full text')[1]['rows'] == [['B', 3, 0, 67, 33, 1], ['A', 6, 100, 0, 17, 0]]
    assert tables(report, 'Scores')[0]['rows'] == [['0–39', 1, 1], ['40–55', 2, 1], ['56–69', 2, 1], ['70–84', 2, 1], ['85–100', 2, 2]]
    assert tables(report, 'Scores')[1]['rows'][0][1] == 67
    assert tables(report, 'Merging')[0]['rows'] == [['Automatic merges', 1], ['Automatic follow-up links', 1], ['Cases split again', 'Not recorded']]
    assert tables(report, 'Merging')[1]['rows'] == [['Title 1', 'A', 'Title 2', 'B', 96, '2026-10-27T13:00:00+01:00']]
    assert tables(report, 'Search budget')[0]['rows'] == [[1, 123]]
    assert '67%' in markdown(report)


def test_empty_read_only_cli_and_invalid_days(monkeypatch, capsys):
    from owis.scripts.ops_report import main
    report = read_report(days=2, now=NOW)
    assert tables(report, 'Full text')[0]['rows'] == []
    assert 'No data in this period.' in markdown(report)
    with pytest.raises(ValueError):
        read_report(days=0)
    monkeypatch.setattr('sys.argv', ['ops_report', '--db', db.DB_PATH, '--days', '2'])
    main()
    assert capsys.readouterr().out == markdown(read_report(days=2))
    with db.get_conn() as conn:
        conn.execute('PRAGMA query_only=ON')
        assert build_report(conn, 2, NOW) == report


def test_api_auth_and_validation(monkeypatch):
    from owis.apps.api.main import app
    monkeypatch.setenv('OWI_ACCESS_USER', 'owis')
    monkeypatch.setenv('OWI_ACCESS_PASSWORD', 'fixture-password')
    client = TestClient(app)
    assert client.get('/api/news/ops-report').status_code == 401
    client.auth = ('owis', 'fixture-password')
    assert client.get('/api/news/ops-report?days=2').json() == read_report(days=2)
    assert client.get('/api/news/ops-report?days=0').status_code == 422
    assert client.get('/api/news/ops-report?days=367').status_code == 422


def test_absent_database_is_not_created(tmp_path):
    path = tmp_path / 'missing.db'
    with pytest.raises(sqlite3.OperationalError):
        read_report(path)
    assert not path.exists()


def test_latest_50_and_old_decisions_keep_counts():
    with db.get_conn() as conn:
        for i in range(55):
            insert(conn, 'news_learning_feedback', pair_id=999, feedback_type='match_review_decision',
                   feedback_value='accept', actor='auto', created_at=f'2026-10-27T11:{i:02d}:00Z')
        for when in ['2026-10-23T21:59:59Z', '2026-10-27T12:00:01Z']:
            insert(conn, 'news_learning_feedback', pair_id=999, feedback_type='match_review_decision',
                   feedback_value='accept', actor='auto', created_at=when)
    report = read_report(days=4, now=NOW)
    assert tables(report, 'Merging')[0]['rows'][0][1] == 55
    recent = tables(report, 'Merging')[1]['rows']
    assert len(recent) == 50
    assert recent[0] == ['Not recorded'] * 4 + [None, '2026-10-27T12:54:00+01:00']
    assert recent[-1][-1] == '2026-10-27T12:05:00+01:00'


def test_local_midnight_and_late_report():
    with db.get_conn() as conn:
        for i, fetched in enumerate(['2026-10-23T21:59:59Z', '2026-10-23T22:00:00Z', '2026-10-27T12:00:01Z']):
            insert(conn, 'news_raw_items', source_name='A', article_url=f'https://example.test/{i}',
                   title_raw='Title', content_hash=str(i), fetched_at=fetched)
        insert(conn, 'news_morning_reports', report_date='2026-10-24', status='completed',
               started_at='2026-10-24T04:00:00Z', completed_at='2026-10-25T05:00:00Z', run_id='late')
    report = read_report(days=4, now=NOW)
    assert report['sections'][0]['summary'] == '0 of 4 days delivered by 07:00'
    assert tables(report, 'Fetching')[0]['rows'] == [['2026-10-24', 1], ['2026-10-25', 0], ['2026-10-26', 0], ['2026-10-27', 0]]


def test_running_and_null_brief():
    with db.get_conn() as conn:
        for day, started in [('2026-10-26', '2026-10-26T04:00:00Z'), ('2026-10-27', '2026-10-27T11:00:00Z')]:
            insert(conn, 'news_morning_reports', report_date=day, status='running', started_at=started,
                   run_id=day, result_json='{"news_total":0,"brief":null}')
    report = read_report(days=2, now=NOW)
    assert [r[1] for r in tables(report, 'Morning reports')[0]['rows']] == ['failed', 'Not recorded']
    assert tables(report, 'Morning reports')[0]['rows'][0][4] == 'Fallback'
