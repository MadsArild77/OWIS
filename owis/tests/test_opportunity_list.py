from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from owis.core.storage.db import get_conn
from owis.modules.opportunities.presentation import api
from owis.modules.opportunities.storage.repository import OpportunitiesRepository, country_region


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


@pytest.fixture
def notices():
    today = datetime.now(timezone.utc).date()
    repo = OpportunitiesRepository()
    ids = []
    for index, days in enumerate([None, 14, 0, -1, 15, 7]):
        repo.upsert_raw_item({
            "id": str(index), "source": "TED" if index != 5 else "DOFFIN",
            "url": "https://example.org/notice", "title": f"Tender {index}",
            "country": "NOR", "buyer": "Wind Authority", "cpv_codes": ["71354500"],
            "publication_date": (today - timedelta(days=index)).isoformat(),
        })
        with get_conn() as conn:
            raw_id = conn.execute("SELECT id FROM opportunity_raw_items WHERE notice_id = ?", (str(index),)).fetchone()[0]
        ids.append(repo.save_processed_item({
            "raw_item_id": raw_id, "title": f"Tender {index}", "source_name": "TED" if index != 5 else "DOFFIN",
            "source_url": "https://example.org/notice", "buyer": "Wind Authority",
            "country": "NOR" if index != 5 else "GBR", "summary": "Marine survey",
            "opportunity_family": "procurement_tenders", "mechanism_type": "tender",
            "deadline": (today + timedelta(days=days)).isoformat() if days is not None else None,
            "strategic_fit": "Strong" if index != 5 else "Weak", "competition_level": "Low",
            "matched_services": "Marine Survey & Geoscience" if index != 5 else "Strategy & Advisory",
            "matched_qualifiers": "offshore", "recommended_action": "Review",
            "why_it_matters": "Market signal", "signal_score": 20, "confidence": 0.8,
            "profile_name": "AGR" if index != 5 else "MAV", "processed_at": today.isoformat(),
        }))
    return ids


def test_list_deadlines_views_counts_and_limit(client, notices):
    data = client.get('/api/opportunities/list').json()
    assert [i['id'] for i in data['items']] == [notices[i] for i in [2, 5, 1, 4, 0]]
    assert data['counts'] == {'open': 5, 'closing-soon': 3, 'new': 5, 'saved': 0, 'hidden': 0}
    assert data['total'] == 6
    assert data['items'][0]['cpv_codes'] == '["71354500"]'
    soon = client.get('/api/opportunities/list?view=closing-soon').json()
    assert [i['id'] for i in soon['items']] == [notices[i] for i in [2, 5, 1]]
    new = client.get('/api/opportunities/list?view=new').json()
    assert [i['id'] for i in new['items']] == [notices[i] for i in [0, 1, 2, 4, 5]]
    limited = client.get('/api/opportunities/list?limit=1').json()
    assert len(limited['items']) == 1
    assert limited['counts'] == data['counts']
    assert client.get('/api/opportunities/list?limit=0').status_code == 422
    assert client.get('/api/opportunities/list?view=invalid').status_code == 422


def test_filters_and_multiple_profiles(client, notices):
    base = '/api/opportunities/list'
    for params in ({'region': 'UK'}, {'fit': 'Low'}, {'source': 'DOFFIN'}, {'profile': 'Strategy & Advisory'}, {'q': 'tEnDeR 5'}):
        assert [i['id'] for i in client.get(base, params=params).json()['items']] == [notices[5]]
    data = client.get(base, params={'profile': ['Marine Survey & Geoscience', 'Strategy & Advisory']}).json()
    assert len(data['items']) == 5
    assert client.get(base, params={'region': 'UK', 'fit': 'High'}).json()['items'] == []
    assert client.get(base, params={'q': 'Wind Authority'}).json()['counts']['open'] == 5


def test_state_persists_and_expired_saved_is_visible(client, notices):
    def state(index, value):
        return client.post(f'/api/opportunities/item/{notices[index]}/state', json={'state': value})
    assert state(3, 'saved').status_code == 200
    assert state(2, 'hidden').status_code == 200
    repo = OpportunitiesRepository()
    assert [i['id'] for i in repo.list_items(view='saved')['items']] == [notices[3]]
    assert [i['id'] for i in repo.list_items(view='hidden')['items']] == [notices[2]]
    for view in ['open', 'closing-soon', 'new']:
        assert not {notices[2], notices[3]} & {i['id'] for i in repo.list_items(view=view)['items']}
    assert state(2, 'none').status_code == 200
    assert repo.list_items()['counts']['hidden'] == 0
    assert repo.list_items()['counts']['open'] == 5
    assert state(2, 'invalid').status_code == 422
    assert client.post('/api/opportunities/item/99999/state', json={'state': 'saved'}).status_code == 404


@pytest.mark.parametrize('country,region', [('NOR','Norway'),('SWE','Nordics'),('GBR','UK'),('DEU','Europe'),('EU','Europe'),('CAN','Americas'),('BRA','Americas'),('IND','Asia-Pacific'),('NZL','Asia-Pacific'),('ARE','Middle East & Africa'),('ZAF','Middle East & Africa'),('UNKNOWN',''),('','')])
def test_country_regions(country, region):
    assert country_region(country) == region


def test_empty_and_profiles(client):
    assert client.get('/api/opportunities/list').json()['total'] == 0
    profiles = client.get('/api/opportunities/profiles').json()
    assert {p['name'] for p in profiles['profiles']} >= {'Offshore wind market', 'Marine Survey & Geoscience', 'Strategy & Advisory'}


def test_new_week_boundary(client, notices):
    today = datetime.now(timezone.utc).date()
    with get_conn() as conn:
        conn.execute('UPDATE opportunity_raw_items SET publication_date = ?', ((today-timedelta(days=7)).isoformat(),))
    assert client.get('/api/opportunities/list?view=new').json()['items'] == []
