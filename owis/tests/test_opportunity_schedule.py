from datetime import datetime, timezone

import pytest

from owis.core.storage.db import get_conn
from owis.modules.opportunities.processing import pipeline, schedule
from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
from owis.modules.opportunities.storage.repository import OpportunitiesRepository

PROFILES = ['AGR', 'MAV', 'OWIS']


def classify(title, country='IRL'):
    bundle = load_profile_bundle(active_profiles=PROFILES)
    result = pipeline.classify_notice({'description': title.lower(), 'country': country}, bundle, PROFILES)
    return result and result['profile_name']


@pytest.mark.parametrize('title', [
    'Ireland – Human resources management consultancy services – Request for Tender for the Provision of HR Support '
    'and Advisory Services to Clare Tourism Development DAC',
    'Ireland – IT services: consulting, software development, Internet and support – The provision of brand strategy, '
    'creative design, and website development and maintenance services',
    'Germany – Feasibility study, advisory service, analysis – Erstellung einer strukturierten Bedarfs- und '
    'Entwicklungsplanung für die Feuerwehr Hamburg',
    'Sweden – General management consultancy services – Advisory support to the International Affairs Department',
    'Consultancy for Transactional Advisory Services (IPP/PPP) support to prepare Wind/ Solar/ BESS projects',
])
def test_mav_no_longer_matches_general_advisory_seen_in_production(title):
    assert classify(title) != 'MAV'


def test_mav_matches_offshore_wind_advisory():
    assert classify('Norway – Feasibility study for a floating wind port and supply base in Rogaland', 'NOR') == 'MAV'
    assert classify('Market study and advisory support for the offshore wind support scheme', 'DNK') == 'MAV'


def raw_with_processed(repo, notice_id, title, state=None):
    repo.upsert_raw_item({'id': notice_id, 'source': 'TED', 'url': 'https://example.org/' + notice_id,
                          'title': title, 'country': 'IRL', 'buyer': 'Buyer', 'publication_date': '2026-11-01'})
    with get_conn() as conn:
        raw_id = conn.execute('SELECT id FROM opportunity_raw_items WHERE notice_id = ?', (notice_id,)).fetchone()[0]
    item_id = repo.save_processed_item({
        'raw_item_id': raw_id, 'title': title, 'source_name': 'TED', 'source_url': 'https://example.org',
        'summary': title, 'opportunity_family': 'procurement_tenders', 'mechanism_type': 'tender',
        'strategic_fit': 'Medium', 'competition_level': 'High', 'matched_services': 'Strategy & Advisory',
        'matched_qualifiers': 'port', 'recommended_action': 'Review', 'why_it_matters': 'w', 'signal_score': 20,
        'confidence': 0.6, 'profile_name': 'MAV', 'processed_at': '2026-11-06T07:12:10+00:00'})
    if state:
        repo.set_state(item_id, state)
    return raw_id


def test_reclassify_removes_old_matches_but_keeps_saved_and_valid():
    repo = OpportunitiesRepository()
    hr = raw_with_processed(repo, 'hr', 'Human resources consultancy for Clare Tourism, HR support and advisory')
    kept = raw_with_processed(repo, 'saved', 'Human resources consultancy and advisory support', state='saved')
    valid = raw_with_processed(repo, 'ok', 'Advisory services for offshore wind consenting in Ireland')
    assert schedule.reclassify(repo) == 1
    remaining = {row['id'] for row in repo.processed_raw_items()}
    assert remaining == {kept, valid}
    with get_conn() as conn:
        assert conn.execute('SELECT status FROM opportunity_raw_items WHERE id = ?', (hr,)).fetchone()[0] == 'rejected'


def test_runs_once_a_day_after_the_configured_oslo_time(monkeypatch):
    monkeypatch.setenv('OWI_OPP_SCHEDULED_FETCH_ENABLED', 'true')
    calls = []
    monkeypatch.setattr(schedule, 'run', lambda: calls.append(1))
    assert not schedule.tick(datetime(2026, 11, 20, 3, 29, tzinfo=timezone.utc))  # 04:29 Oslo
    assert schedule.tick(datetime(2026, 11, 20, 3, 31, tzinfo=timezone.utc))
    assert not schedule.tick(datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc))
    assert schedule.tick(datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc))  # catches up after a late start
    assert len(calls) == 2
    monkeypatch.setenv('OWI_OPP_SCHEDULED_FETCH_ENABLED', 'false')
    assert not schedule.tick(datetime(2026, 11, 22, 4, 0, tzinfo=timezone.utc))


def cowi(title, country):
    bundle = load_profile_bundle(active_profiles=['COWI'])
    result = pipeline.classify_notice({'description': title.lower(), 'country': country}, bundle, ['COWI'])
    return bool(result)


@pytest.mark.parametrize('title,country', [
    ('Statnett – prosjektering av ny transformatorstasjon og kraftledning i Rogaland', 'NOR'),
    ("Owner's engineer services for the Muir Mhor offshore wind farm", 'GBR'),
    ('Environmental impact assessment for Energinet export cable landfall', 'DNK'),
    ('Concept design of HVDC converter station for offshore grid connection', 'DEU'),
    ('Detailed design of new quay for offshore wind base at the port of Esbjerg', 'DNK'),
])
def test_cowi_profile_matches_engineering_for_offshore_wind_grid_and_ports(title, country):
    assert cowi(title, country)


@pytest.mark.parametrize('title,country', [
    ("Owner's engineer for floating offshore wind farm in Brittany", 'FRA'),  # outside the Nordics and North Sea
    ('Detailed design of school building and sports hall', 'NOR'),
    ('Engineering services for road maintenance programme', 'SWE'),
    ('Software development for port community system', 'NLD'),
    ('Cleaning services for offshore wind O&M base', 'GBR'),
    # Matched in production on 20 November 2026: works contracts and World Bank notices without a country.
    ('Bygg- og grunnentreprise Tjeldbergodden transformatorstasjon', 'NOR'),
    ('E0019EBE - Skur Dokkeskjærskaien - rivingsarbeider og ny trafostasjon', 'NOR'),
    ('154/33 kV SELİMPAŞA Gas Insulated Switchgear Substation (GIS) transmission', ''),
    ('Design, Supply and Installation of high voltage substations for transmission', ''),
])
def test_cowi_profile_skips_other_work_and_other_countries(title, country):
    assert not cowi(title, country)


def test_profile_countries_are_optional_and_default_profiles_include_cowi():
    from owis.core.config import settings
    bundle = load_profile_bundle(active_profiles=['AGR', 'COWI'])
    assert bundle['by_company']['AGR'][0]['countries'] == []
    assert 'COWI' in settings.OPPORTUNITIES_ACTIVE_PROFILES or 'OWI_OPP_ACTIVE_PROFILES' in __import__('os').environ


def test_listed_tenders_are_checked_against_profiles_at_startup(monkeypatch):
    monkeypatch.setenv('OWI_OPP_SCHEDULED_FETCH_ENABLED', 'true')
    started, calls = [], []
    monkeypatch.setattr(schedule, 'Thread', lambda target, **kw: type('T', (), {'start': lambda self: started.append(target)})())
    monkeypatch.setattr(schedule, 'reclassify', lambda: calls.append('reclassify'))
    monkeypatch.setattr(schedule, 'tick', lambda: calls.append('tick'))
    stop = schedule.start_scheduler()
    stop.set()
    started[0]()
    assert calls == ['reclassify']
