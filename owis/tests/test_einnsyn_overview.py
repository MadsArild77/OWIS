from datetime import date

import httpx
from fastapi.testclient import TestClient

from owis.modules.einnsyn import notion_reader
from owis.modules.einnsyn.notion_reader import EinnsynNotionReader, OverviewCache, build_overview

TODAY = date(2026, 10, 15)


def _log(name, sak, published, fra=""):
    return {"Name": name, "Saksnummer": sak, "Publisert": published, "Fra": fra, "URL": f"https://einnsyn.no/{name}"}


def _data():
    return {
        "saker": [
            {"Name": "Utsira Nord", "Saksnummer": "2025/1", "Status": "Aktiv"},
            {"Name": "SN II", "Saksnummer": "2025/2", "Status": "Aktiv"},
            {"Name": "Ny sak", "Saksnummer": "2026/9", "Status": "Foreslått", "Kommentar": "Funnet av søkeprofil «havvind»",
             "_created": "2026-10-15"},
            {"Name": "Uinteressant", "Saksnummer": "2026/8", "Status": "Ikke relevant"},
        ],
        "logg": [
            _log("a", "2025/1", "2026-10-14", "Equinor ASA"),
            _log("b", "2025/1", "2026-10-10", "Equinor ASA"),
            _log("c", "2025/2", "2026-10-01", "Ventyr SN II AS"),
            _log("d", "2025/2", "2026-05-01", "Gammel AS"),
        ],
        "sok": [
            {"Name": '"Utsira Nord"', "Status": "Aktiv", "Notat": ""},
            {"Name": "SN2", "Status": "Pause", "Notat": "Slått sammen"},
            {"Name": '"Windport"', "Status": "Pause", "Notat": "Forslag fra ukentlig sjekk (2026-10-12): avsender i 3 saker"},
        ],
    }


def test_overview_counts_and_lists():
    o = build_overview(_data(), today=TODAY)
    s = o["summary"]
    assert (s["active_cases"], s["suggested_cases"], s["log_entries"]) == (2, 1, 4)
    assert (s["journal_posts_7d"], s["journal_posts_30d"]) == (2, 3)
    assert (s["active_keywords"], s["keyword_suggestions"]) == (1, 1)
    assert [p["title"] for p in o["recent_journal_posts"]] == ["a", "b", "c"]  # newest first, 14 days
    assert o["recent_journal_posts"][0]["case_title"] == "Utsira Nord"
    assert o["most_active_cases"][0] == {"case_number": "2025/1", "title": "Utsira Nord", "url": "", "journal_posts": 2}
    assert [x["name"] for x in o["top_senders"]] == ["Equinor ASA", "Ventyr SN II AS"]  # 90 days only
    assert [c["case_number"] for c in o["suggested_cases"]] == ["2026/9"]
    assert [k["query"] for k in o["keyword_suggestions"]] == ['"Windport"']
    assert [k["query"] for k in o["keywords"]] == ['"Utsira Nord"', "SN2"]  # active first


def _page(pid, title):
    return {"id": pid, "url": f"https://notion.so/{pid}", "created_time": "2026-10-15T08:00:00.000Z",
            "properties": {"Name": {"type": "title", "title": [{"plain_text": title}]},
                           "Status": {"type": "select", "select": {"name": "Aktiv"}},
                           "Publisert": {"type": "date", "date": {"start": "2026-10-14"}}}}


def test_reader_pages_through_results_and_retries(monkeypatch):
    monkeypatch.setattr(notion_reader.time, "sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(request)
        body = request.read()
        if len(calls) == 1:
            return httpx.Response(502)
        if b"start_cursor" not in body:
            return httpx.Response(200, json={"results": [_page("p1", "one")], "has_more": True, "next_cursor": "c1"})
        return httpx.Response(200, json={"results": [_page("p2", "two")], "has_more": False})

    reader = EinnsynNotionReader("key", "s", "l", "k", client=httpx.Client(transport=httpx.MockTransport(handler)))
    rows = [_r for _r in reader._query_all("db")]
    assert [r["id"] for r in rows] == ["p1", "p2"] and len(calls) == 3
    row = notion_reader._row(rows[0])
    assert (row["Name"], row["Status"], row["Publisert"], row["_created"]) == ("one", "Aktiv", "2026-10-14", "2026-10-15")


def test_cache_reuses_value_until_refresh():
    loads = []

    class Fake:
        def load(self):
            loads.append(1)
            return _data()

    cache = OverviewCache(Fake())
    cache.get(); cache.get()
    assert len(loads) == 1
    cache.get(refresh=True)
    assert len(loads) == 2


def test_api_explains_missing_configuration(monkeypatch):
    from owis.apps.api.main import app
    from owis.modules.einnsyn import api
    monkeypatch.setattr(api.reader, "api_key", "")
    resp = TestClient(app).get("/api/einnsyn/overview")
    assert resp.status_code == 503 and "OWI_EINNSYN_SAKER_DB_ID" in resp.json()["detail"]
    page = TestClient(app).get("/einnsyn")
    assert page.status_code == 200 and "eInnsyn" in page.text
