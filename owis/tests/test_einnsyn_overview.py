import json
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


def test_switching_a_search_term_writes_status_to_notion_and_updates_the_overview():
    sent = []

    class Fake:
        def load(self):
            data = _data()
            for i, k in enumerate(data["sok"]):
                k["_id"] = f"kw{i}"
            return data

        def set_status(self, page_id, status, note=None):
            sent.append((page_id, status) if note is None else (page_id, status, note))

    cache = OverviewCache(Fake())
    before = cache.get()
    assert before["keyword_suggestions"][0]["id"] == "kw2"
    assert cache.set_keyword_status("kw2", True) == "Aktiv"  # accept the suggestion
    after = cache.get()
    assert sent[0][:2] == ("kw2", "Aktiv") and after["keyword_suggestions"] == []
    assert sent[0][2].startswith("Tatt i bruk fra OWIS") and "forslag fra ukentlig sjekk (2026-10-12)" in sent[0][2]
    cache.set_keyword_status("kw2", False)  # an accepted suggestion, paused later, stays a search term
    assert sent[-1] == ("kw2", "Pause") and cache.get()["keyword_suggestions"] == []
    assert {k["query"]: k["status"] for k in cache.get()["keywords"]}['"Windport"'] == "Pause"
    cache.set_keyword_status("kw2", True)
    assert sent[-1] == ("kw2", "Aktiv")  # no new note the second time
    assert {k["query"]: k["status"] for k in after["keywords"]}['"Windport"'] == "Aktiv"
    assert after["loaded_at"] == before["loaded_at"]
    cache.set_keyword_status("kw0", False)
    assert sent[-1] == ("kw0", "Pause") and cache.get()["summary"]["active_keywords"] == 1
    import pytest
    with pytest.raises(KeyError):  # only search terms can be changed
        cache.set_keyword_status("some-case-page", True)


def test_reader_sets_status_with_a_page_patch():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.read())))
        return httpx.Response(200, json={"id": "kw1"})

    reader = EinnsynNotionReader("key", "s", "l", "k", client=httpx.Client(transport=httpx.MockTransport(handler)))
    reader.set_status("kw1", "Pause")
    reader.set_status("kw1", "Aktiv", "Tatt i bruk")
    assert seen == [("PATCH", "/v1/pages/kw1", {"properties": {"Status": {"select": {"name": "Pause"}}}}),
                    ("PATCH", "/v1/pages/kw1", {"properties": {"Status": {"select": {"name": "Aktiv"}},
                                                               "Notat": {"rich_text": [{"text": {"content": "Tatt i bruk"}}]}}})]


def test_api_explains_missing_configuration(monkeypatch):
    from owis.apps.api.main import app
    from owis.modules.einnsyn import api
    monkeypatch.setattr(api.reader, "api_key", "")
    resp = TestClient(app).get("/api/einnsyn/overview")
    assert resp.status_code == 503 and "OWI_EINNSYN_SAKER_DB_ID" in resp.json()["detail"]
    page = TestClient(app).get("/einnsyn")
    assert page.status_code == 200 and "eInnsyn" in page.text


def _tagged():
    data = _data()
    data["saker"][0].update({"Prosjektområde": "Utsira Nord", "Tema": "Konsesjon/Tildeling, Støtte/Finansiering"})
    data["saker"][1].update({"Prosjektområde": "Sørlige Nordsjø II", "Tema": "Støtte/Finansiering"})
    return data


def test_multi_select_is_read_as_joined_names():
    prop = {"type": "multi_select", "multi_select": [{"name": "Utsira Nord"}, {"name": "Brage Havvind"}]}
    assert notion_reader._text(prop) == "Utsira Nord, Brage Havvind"
    assert notion_reader._text({"type": "multi_select", "multi_select": []}) == ""


def test_project_and_theme_boxes():
    o = build_overview(_tagged(), today=TODAY)
    projects = {b["name"]: b for b in o["projects"]}
    assert projects["Utsira Nord"] == {"name": "Utsira Nord", "cases": 1, "suggested": 0, "journal_posts_30d": 2}
    assert projects["Sørlige Nordsjø II"]["journal_posts_30d"] == 1
    # The suggested case has no project, and «Ikke relevant» cases are not counted at all
    assert projects["Uklassifisert"] == {"name": "Uklassifisert", "cases": 1, "suggested": 1, "journal_posts_30d": 0}
    assert o["projects"][-1]["name"] == "Uklassifisert"
    themes = {b["name"]: b["cases"] for b in o["themes"]}
    assert themes == {"Støtte/Finansiering": 2, "Konsesjon/Tildeling": 1, "Uklassifisert": 1}


def test_filter_by_project_and_theme():
    o = build_overview(_tagged(), today=TODAY, project="Utsira Nord")
    assert o["filter"] == {"project": "Utsira Nord", "theme": ""}
    assert o["summary"]["active_cases"] == 1
    assert [p["case_number"] for p in o["recent_journal_posts"]] == ["2025/1", "2025/1"]
    assert [c["case_number"] for c in o["most_active_cases"]] == ["2025/1"]
    assert o["suggested_cases"] == []
    # Theme boxes are counted within the chosen project; project boxes stay unfiltered
    assert {b["name"] for b in o["themes"]} == {"Konsesjon/Tildeling", "Støtte/Finansiering"}
    assert len(o["projects"]) == 3

    o = build_overview(_tagged(), today=TODAY, theme="Støtte/Finansiering")
    assert o["summary"]["active_cases"] == 2
    assert {b["name"] for b in o["projects"]} == {"Utsira Nord", "Sørlige Nordsjø II"}

    o = build_overview(_tagged(), today=TODAY, project="Uklassifisert")
    assert [c["case_number"] for c in o["suggested_cases"]] == ["2026/9"]
    assert o["recent_journal_posts"] == []


def test_filter_joins_journal_posts_on_the_case_page_not_only_the_number():
    data = _tagged()
    data["saker"][0]["_id"] = "page-utsira"
    data["saker"].append({"Name": "Annen etat", "Saksnummer": "2025/1", "Status": "Aktiv", "_id": "page-other",
                          "Prosjektområde": "Brage Havvind"})
    for r in data["logg"]:
        if r["Saksnummer"] == "2025/1":
            r["Sak"] = "page-utsira"
    data["logg"].append({**_log("x", "2025/1", "2026-10-13", "Annen AS"), "Sak": "page-other"})
    o = build_overview(data, today=TODAY, project="Utsira Nord")
    assert [p["title"] for p in o["recent_journal_posts"]] == ["a", "b"]
    assert "Annen AS" not in {s["name"] for s in o["top_senders"]}
    projects = {b["name"]: b["journal_posts_30d"] for b in o["projects"]}
    assert projects["Utsira Nord"] == 2 and projects["Brage Havvind"] == 1


def test_cases_list_every_followed_case_in_the_selection():
    o = build_overview(_tagged(), today=TODAY, project="Utsira Nord")
    assert [c["case_number"] for c in o["cases"]] == ["2025/1"]
    case = o["cases"][0]
    assert case["latest"] == "2026-10-14" and case["journal_posts_30d"] == 2
    assert case["projects"] == ["Utsira Nord"] and case["themes"] == ["Konsesjon/Tildeling", "Støtte/Finansiering"]
    # Unfiltered: followed cases only (not «Ikke relevant»), most recently active first, cases without posts last
    assert [c["case_number"] for c in build_overview(_tagged(), today=TODAY)["cases"]] == ["2025/1", "2025/2", "2026/9"]


def test_posts_of_cases_marked_not_relevant_leave_the_lists_and_counts():
    data = _data()
    data["saker"][1]["Status"] = "Ikke relevant"  # 2025/2
    o = build_overview(data, today=TODAY)
    assert "2025/2" not in [p["case_number"] for p in o["recent_journal_posts"]]
    assert "2025/2" not in [c["case_number"] for c in o["most_active_cases"]]
    assert "Ventyr SN II AS" not in [s["name"] for s in o["top_senders"]]
    assert o["summary"]["journal_posts_30d"] == 2
