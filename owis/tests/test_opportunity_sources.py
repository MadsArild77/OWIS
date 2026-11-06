import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from owis.core.storage import db
from owis.modules.opportunities.collectors import dealengine_fetchers as fetchers
from owis.modules.opportunities.collectors import open_data
from owis.modules.opportunities.presentation import api
from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
from owis.modules.opportunities.storage.repository import OpportunitiesRepository


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"opportunity_{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def mock_http(monkeypatch):
    original = httpx.Client

    def install(handler):
        monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))

    return install


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network is not allowed in opportunity tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


def test_worldbank_new_endpoint_query_and_local_date_filter(mock_http):
    data = fixture("worldbank")
    data["total"] = str(len(data["procnotices"]))
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/api/v2/procnotices"
        assert request.url.params["qterm"] == "offshore wind"
        assert "q" not in request.url.params and "strdate" not in request.url.params
        return httpx.Response(200, json=data)

    mock_http(handler)
    bundle = {"keywords_by_company": {"OWIS": ["offshore wind"]}}
    items, report = fetchers.fetch_worldbank_notices(bundle, days_back=10000)
    assert len(items) == len(data["procnotices"])
    row = data["procnotices"][0]
    assert items[0]["title"] == row["bid_description"]
    assert items[0]["deadline_raw"] == row["submission_deadline_date"]
    assert items[0]["buyer"] == row["contact_organization"]
    assert items[0]["url"].endswith(row["id"])
    assert report["status"] == "ok"
    items, report = fetchers.fetch_worldbank_notices(bundle, days_back=1)
    assert all(item["publication_date"] >= datetime.now(timezone.utc).date().isoformat() for item in items)
    assert report["filtered"] > 0


def test_worldbank_paginates_with_offset(mock_http):
    data = fixture("worldbank")
    rows = data["procnotices"]
    offsets = []

    def handler(request):
        offset = int(request.url.params["os"])
        offsets.append(offset)
        return httpx.Response(200, json={"total": 2, "procnotices": rows[offset:offset + 1]})

    mock_http(handler)
    with httpx.Client() as client:
        result = fetchers._worldbank_keyword_search(client, "wind", "2020-01-01")
    assert len(result) == 2
    assert offsets == [0, 1]


def test_doffin_post_filters_and_source_fields(mock_http):
    data = fixture("doffin")
    data["numHitsTotal"] = len(data["hits"])
    payloads = []

    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == fetchers.DOFFIN_SEARCH_URL
        payload = json.loads(request.content)
        payloads.append(payload)
        assert payload["facets"]["type"]["checkedItems"] == fetchers.RELEVANT_DOFFIN_TYPES
        assert "from" in payload["facets"]["publicationDate"]
        return httpx.Response(200, json=data)

    mock_http(handler)
    items, report = fetchers.fetch_doffin_notices(
        {"all_cpv_codes": ["31121300"], "keywords_by_company": {"OWIS": ["havvindpark"]}}, 10000)
    assert len(items) == 2
    assert "searchString" not in payloads[0]
    assert payloads[0]["facets"]["cpvCodesId"]["checkedItems"] == ["31121300"]
    assert payloads[1]["searchString"] == "havvindpark"
    assert items[0]["deadline_raw"] == data["hits"][0]["deadline"]
    assert items[0]["estimated_value"] == data["hits"][0]["estimatedValue"]["amount"]
    assert items[0]["currency"] == "NOK"
    assert items[0]["url"] == "https://doffin.no/notices/" + data["hits"][0]["id"]
    assert report["status"] == "ok"


def test_doffin_rejects_awards_and_incomplete_pagination(mock_http):
    data = fixture("doffin")
    data["numHitsTotal"] = 2
    data["hits"][0]["type"] = "RESULT"
    data["hits"][0]["allTypes"] = ["RESULT"]
    mock_http(lambda request: httpx.Response(200, json=data))
    items, _ = fetchers.fetch_doffin_notices({"all_qualifiers": ["wind"]}, 10000)
    assert len(items) == 1
    data["numHitsTotal"] = 1001
    data["numHitsAccessible"] = 2
    _, report = fetchers.fetch_doffin_notices({"all_qualifiers": ["wind"]}, 10000)
    assert report["status"] == "error"


def test_ted_requests_source_deadline_value_and_owis_keywords(mock_http):
    data = fixture("ted")
    data["totalNoticeCount"] = len(data["notices"])

    def handler(request):
        payload = json.loads(request.content)
        assert "deadline-receipt-tender-date-lot" in payload["fields"]
        assert "estimated-value-proc" in payload["fields"]
        assert 'FT ~ "havvindpark"' in payload["query"]
        return httpx.Response(200, json=data)

    mock_http(handler)
    items, report = fetchers.fetch_ted_notices({"keywords_by_company": {"OWIS": ["havvindpark"]}}, 30, ["NOR"])
    assert report["status"] == "ok"
    assert items[0]["estimated_value"] == 20000000
    assert items[0]["currency"] == "NOK"
    assert items[1]["deadline_raw"] == "2026-11-27"


@pytest.mark.parametrize("source,fixture_name,prefix", [("UK_FTS", "uk_fts", "updated"), ("UK_CF", "uk_cf", "published")])
def test_uk_fixtures_pagination_window_and_fields(mock_http, source, fixture_name, prefix):
    data = fixture(fixture_name)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            assert request.url.params[prefix + "From"].startswith("2026-11-01T00:00:00")
            return httpx.Response(200, json=data)
        assert str(request.url) == data["links"]["next"]
        return httpx.Response(200, json={"releases": []})

    mock_http(handler)
    items, report = open_data.fetch_uk_notices(source, 30, "2026-11-01T00:00:00+00:00", "2026-11-06T00:00:00+00:00")
    assert len(calls) == 2
    assert len(items) == 2
    assert items[0]["id"] == data["releases"][0]["ocid"]
    assert items[0]["country"] == "GBR"
    assert items[0]["cpv_codes"]
    assert items[0]["deadline_raw"] == data["releases"][0]["tender"]["tenderPeriod"]["endDate"]
    assert items[0]["estimated_value"] == data["releases"][0]["tender"]["value"]["amount"]
    assert report["status"] == "ok"


@pytest.mark.parametrize("status,accepted", [("active", True), ("planned", True), ("complete", False), ("cancelled", False), ("unsuccessful", False)])
def test_uk_only_open_tenders(status, accepted):
    raw = fixture("uk_fts")["releases"][0]
    raw["tender"]["status"] = status
    assert (open_data.normalize_ocds(raw, "UK_FTS") is not None) == accepted


def test_uk_latest_closed_release_wins(mock_http):
    raw = fixture("uk_fts")["releases"][0]
    closed = copy.deepcopy(raw)
    closed["date"] = "2026-11-06T00:00:00Z"
    closed["tender"]["status"] = "complete"
    mock_http(lambda request: httpx.Response(200, json={"releases": [closed, raw]}))
    items, report = open_data.fetch_uk_notices("UK_FTS", 30)
    assert items == []
    assert report["filtered"] == 2


def test_uk_planning_without_status_and_cpv_items():
    raw = fixture("uk_fts")["releases"][0]
    raw["tag"] = ["planning"]
    raw["tender"].pop("status")
    raw["tender"]["items"] = [{"additionalClassifications": [{"scheme": "CPV", "id": "31121300"}]}]
    assert "31121300" in open_data.normalize_ocds(raw, "UK_FTS")["cpv_codes"]
    raw["tender"]["status"] = "cancelled"
    assert open_data.normalize_ocds(raw, "UK_FTS") is None


def test_canada_csv_english_fields_date_window(mock_http):
    content = (FIXTURES / "opportunity_canadabuys.csv").read_bytes()
    mock_http(lambda request: httpx.Response(200, content=content))
    items, report = open_data.fetch_canadabuys_notices(30, "2026-01-01T00:00:00Z", "2026-11-06T00:00:00Z")
    assert items[0]["title"] == "Open Construction Source List for CFB Halifax"
    assert items[0]["country"] == "CAN"
    assert items[0]["deadline_raw"] == "2029-03-31T13:00:00"
    assert items[0]["estimated_value"] is None
    assert report["status"] == "ok"
    items, _ = open_data.fetch_canadabuys_notices(30, "2030-01-01T00:00:00Z", "2030-01-02T00:00:00Z")
    assert items == []


def test_duplicate_ocid_across_uk_sources(mock_http):
    data = fixture("uk_fts")
    data.pop("links", None)
    mock_http(lambda request: httpx.Response(200, json=data))
    items, reports = fetchers.fetch_dealengine_style_notices_with_report({}, ["UK_FTS", "UK_CF"], 30)
    assert len(items) == 2
    assert len(reports) == 2
    repo = OpportunitiesRepository()
    assert repo.upsert_raw_item(items[0])
    duplicate = {**items[0], "source": "UK_CF"}
    assert not repo.upsert_raw_item(duplicate)


@pytest.mark.parametrize("source", ["UK_FTS", "UK_CF", "CANADABUYS"])
def test_source_errors_are_reported(mock_http, source):
    mock_http(lambda request: httpx.Response(503))
    _, reports = fetchers.fetch_dealengine_style_notices_with_report({}, [source], 30)
    assert reports[0]["status"] == "error"
    assert reports[0]["error"] == "HTTP 503"


def test_source_status_and_successful_watermark(monkeypatch):
    repo = OpportunitiesRepository()
    monkeypatch.setattr(api, "repo", repo)
    assert len(api.sources()) == 6
    assert all(item["status"] == "Not run yet" for item in api.sources())
    repo.save_source_run({"source": "UK_FTS", "status": "ok", "items": 5, "new_items": 2, "filtered": 3}, "2026-11-01T00:00:00Z", "2026-11-01T00:05:00Z")
    repo.save_source_run({"source": "UK_FTS", "status": "error", "error": "HTTP 503"}, "2026-11-02T00:00:00Z", "2026-11-02T00:05:00Z")
    assert repo.successful_source_starts() == {"UK_FTS": "2026-11-01T00:00:00Z"}
    item = next(item for item in api.sources() if item["source"] == "UK_FTS")
    assert item["status"] == "Failed: HTTP 503"
    assert item["name"] == "Find a Tender (UK)"


def test_run_processes_new_sources_counts_rejections_and_uses_watermark(monkeypatch):
    repo = OpportunitiesRepository()
    monkeypatch.setattr(api, "repo", repo)
    monkeypatch.setattr(api, "load_profile_bundle", lambda **kwargs: load_profile_bundle(["OWIS"]))
    calls = []
    items = [open_data.normalize_ocds(row, "UK_FTS") for row in fixture("uk_fts")["releases"]]
    items[0]["title"] = "havvindpark"

    def fetch(**kwargs):
        calls.append(kwargs)
        return copy.deepcopy(items), [{"source": "UK_FTS", "status": "ok", "items": 2, "filtered": 0}]

    monkeypatch.setattr(api, "fetch_dealengine_style_notices_with_report", fetch)
    result = api.run_fetch_process(api.RunOpportunitiesRequest(sources=["UK_FTS"], profiles=["OWIS"]))
    assert result["processed_items"] == 1
    assert result["rejected_items"] == 1
    status = next(item for item in api.sources() if item["source"] == "UK_FTS")
    assert (status["fetched"], status["new"], status["filtered"]) == (2, 2, 1)
    assert repo.latest()[0]["deadline_source"] == "source"
    assert repo.latest()[0]["estimated_value"] == items[0]["estimated_value"]
    api.run_fetch_process(api.RunOpportunitiesRequest(sources=["UK_FTS"], profiles=["OWIS"]))
    assert calls[1]["since_by_source"]["UK_FTS"] == status["started_at"]
    assert repo.latest_source_runs()["UK_FTS"]["new_items"] == 0


def test_schema_migration_preserves_existing_rows():
    with db.get_conn() as conn:
        for table, columns in {"opportunity_raw_items": ["deadline_raw", "estimated_value", "currency"],
                               "opportunity_processed_items": ["estimated_value", "currency", "deadline_source"]}.items():
            for column in columns:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        conn.execute("""INSERT INTO opportunity_raw_items
                     (notice_id, source_name, notice_url, title_raw, content_hash, fetched_at)
                     VALUES ('old', 'TED', 'https://example.org', 'Old notice', 'hash', '2020-01-01')""")
    db.init_db()
    db.init_db()
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM opportunity_raw_items WHERE notice_id = 'old'").fetchone()
        assert row["title_raw"] == "Old notice"
        assert row["deadline_raw"] is None and row["estimated_value"] is None


@pytest.mark.parametrize("source", ["TED", "DOFFIN", "WORLDBANK"])
def test_existing_source_errors_are_visible(mock_http, source):
    mock_http(lambda request: httpx.Response(503))
    bundle = {"all_cpv_codes": ["31121300"], "all_qualifiers": ["wind"],
              "keywords_by_company": {"OWIS": ["offshore wind"]}}
    _, reports = fetchers.fetch_dealengine_style_notices_with_report(bundle, [source], 30)
    assert reports[0]["status"] == "error"
    assert reports[0]["error"] == "HTTP 503"


def test_uk_repeated_pagination_is_failure(mock_http):
    data = fixture("uk_fts")
    data["links"] = {"next": open_data.UK_ENDPOINTS["UK_FTS"]}
    mock_http(lambda request: httpx.Response(200, json=data))
    _, report = open_data.fetch_uk_notices("UK_FTS", 30)
    assert report["status"] == "error"
    assert report["error"] == "Repeated pagination link"


def test_unexpected_success_response_is_failure(mock_http):
    mock_http(lambda request: httpx.Response(200, json={"message": "Unavailable"}))
    _, report = open_data.fetch_uk_notices("UK_FTS", 30)
    assert report["status"] == "error"
    _, report = open_data.fetch_canadabuys_notices(30)
    assert report["status"] == "error"


def test_sources_http_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(api.router)
    response = TestClient(app).get("/api/opportunities/sources")
    assert response.status_code == 200
    assert {item["source"] for item in response.json()} == set(open_data.SOURCE_NAMES)
    assert all(item["status"] == "Not run yet" for item in response.json())


def test_worldbank_keeps_project_context_for_profile_matching():
    from owis.modules.opportunities.processing.pipeline import process_raw_item
    row = fixture("worldbank")["procnotices"][0]
    row["project_name"] = "Offshore wind development"
    row["bid_description"] = "Technical assessment"
    item = fetchers._normalize_worldbank(row)
    assert item["title"] == "Technical assessment"
    assert "offshore wind" in item["description"]
    result = process_raw_item({"id": 1, "title_raw": item["title"], "description_raw": item["description"]},
                              load_profile_bundle(["OWIS"]), ["OWIS"])
    assert result is not None


def test_uk_latest_release_compares_timezone_offsets(mock_http):
    active = fixture("uk_fts")["releases"][0]
    active["date"] = "2026-11-05T12:00:00+02:00"
    closed = copy.deepcopy(active)
    closed["date"] = "2026-11-05T11:00:00Z"
    closed["tender"]["status"] = "complete"
    mock_http(lambda request: httpx.Response(200, json={"releases": [active, closed]}))
    items, report = open_data.fetch_uk_notices("UK_FTS", 30)
    assert items == []
    assert report["status"] == "ok"


def test_uk_rate_limit_waits_and_retries(mock_http, monkeypatch):
    waits = []
    monkeypatch.setattr(open_data.time, "sleep", waits.append)
    answers = [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={"releases": []})]
    mock_http(lambda request: answers.pop(0))
    items, report = open_data.fetch_uk_notices("UK_CF", 30)
    assert waits == [7]
    assert report["status"] == "ok"
