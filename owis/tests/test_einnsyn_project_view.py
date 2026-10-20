import json
from datetime import date

from owis.core.storage.db import get_conn
from owis.modules.einnsyn import project_view, public_sources

TODAY = date(2026, 10, 15)


def _data():
    return {
        "saker": [
            {"Name": "Ventyr SN II - nettilknytning", "Saksnummer": "2024/1", "Status": "Aktiv", "_id": "p1",
             "URL": "https://einnsyn.no/saksmappe?id=iri-1", "Prosjektområde": "Sørlige Nordsjø II", "Tema": "Konsesjon/Tildeling"},
            {"Name": "Utsira Nord - utlysning", "Saksnummer": "2025/2", "Status": "Aktiv", "_id": "p2",
             "URL": "https://einnsyn.no/saksmappe?id=iri-2", "Prosjektområde": "Utsira Nord"},
            {"Name": "Avvist", "Saksnummer": "2025/3", "Status": "Ikke relevant", "_id": "p3", "Prosjektområde": "Utsira Nord"},
        ],
        "logg": [
            {"Name": "Søknad om konsesjon", "Saksnummer": "2024/1", "Sak": "p1", "Publisert": "2026-09-01", "Fra": "Ventyr SN II AS"},
            {"Name": "Svar fra NVE", "Saksnummer": "2024/1", "Sak": "p1", "Publisert": "2026-10-10", "Til": "Ventyr SN II AS"},
            {"Name": "Gammel post", "Saksnummer": "2025/2", "Sak": "p2", "Publisert": "2025-01-05"},
            {"Name": "Om en avvist sak", "Saksnummer": "2025/3", "Sak": "p3", "Publisert": "2026-10-01"},
        ],
        "sok": [{"Name": '"Sørlige Nordsjø II" | SN2', "Status": "Aktiv"}, {"Name": '"Utsira Nord"', "Status": "Aktiv"}],
    }


def _store_public():
    public_sources._ensure_tables()
    with get_conn() as conn:
        conn.execute("DELETE FROM public_items")
    public_sources._store("stortinget", [
        {"id": "written_question-1", "kind": "written_question", "title": "Når får SN2 konsesjon?", "day": "2026-10-05",
         "status": "Answered 2026-10-09", "person": "Kari (H)", "body": "energiministeren", "url": "https://stortinget.no/q1"},
        {"id": "written_question-2", "kind": "written_question", "title": "Om havvind generelt", "day": "2026-10-02", "url": "u"}])


def test_project_timeline_merges_journal_posts_and_storting_records():
    _store_public()
    m = project_view.material(_data(), project="Sørlige Nordsjø II", today=TODAY)
    entries = project_view.timeline(m)
    assert [(e["date"], e["kind"]) for e in entries] == [
        ("2026-10-10", "journal_post"), ("2026-10-05", "written_question"), ("2026-09-01", "journal_post")]
    assert entries[0]["case_url"].endswith("iri-1") and entries[0]["case_number"] == "2024/1"
    assert entries[1]["person"] == "Kari (H)"


def test_portfolio_covers_followed_cases_of_the_last_60_days():
    _store_public()
    m = project_view.material(_data(), today=TODAY)
    titles = [p["title"] for p in m["posts"]]
    assert titles == ["Svar fra NVE", "Søknad om konsesjon"]  # old post and the rejected case's post left out
    assert {p["title"] for p in m["public"]} == {"Når får SN2 konsesjon?", "Om havvind generelt"}


def test_cases_with_the_same_number_at_two_agencies_keep_their_own_activity(monkeypatch):
    _store_public()
    data = _data()
    data["saker"].append({"Name": "Annen etat, samme nummer", "Saksnummer": "2024/1", "Status": "Aktiv", "_id": "p9",
                          "URL": "https://einnsyn.no/saksmappe?id=iri-9", "Prosjektområde": "Utsira Nord"})
    data["logg"].append({"Name": "Post i den andre saken", "Saksnummer": "2024/1", "Sak": "p9", "Publisert": "2026-10-12"})
    sent = []

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            sent.append(json.loads(text))
            return {"headline": "h", "summary": "s", "projects": []}

    monkeypatch.setattr(project_view, "AIClient", FakeAI)
    project_view.write(project_view.material(data, today=TODAY), TODAY)
    areas = {p["name"]: p for p in sent[0]["projects"]}
    assert areas["Sørlige Nordsjø II"]["latest_journal_posts"] == ["Svar fra NVE", "Søknad om konsesjon"]
    assert areas["Utsira Nord"]["latest_journal_posts"] == ["Post i den andre saken"]


def test_view_is_written_once_and_rewritten_when_the_material_changes(monkeypatch):
    _store_public()
    calls = []

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            calls.append(json.loads(text))
            return {"headline": "SN II nears its grid licence", "status": "Grid licence under review",
                    "summary": "Ventyr applied [1] and asked again [9].", "actors": [{"name": "Ventyr", "role": "developer"}],
                    "recent": ["The Storting asked about the licence [1]."], "next": "Likely: a decision.", "risks": ""}

    monkeypatch.setattr(project_view, "AIClient", FakeAI)
    m = project_view.material(_data(), project="Sørlige Nordsjø II", today=TODAY)
    assert project_view.stored(m, TODAY) is None
    view = project_view.write(m, TODAY)
    assert view["complete"] and view["status"] == "Grid licence under review"
    assert view["summary"] == "Ventyr applied [1] and asked again."  # no source 9
    assert [s["n"] for s in view["sources"]] == [1] and view["sources"][0]["source"] == "Written question"
    sent = calls[0]
    assert sent["project"] == "Sørlige Nordsjø II" and sent["cases"][0]["case_number"] == "2024/1"
    assert [p["title"] for p in sent["latest_journal_posts"]] == ["Svar fra NVE", "Søknad om konsesjon"]
    data = _data()
    data["logg"].append({"Name": "Vedtak", "Saksnummer": "2024/1", "Sak": "p1", "Publisert": "2026-10-14"})
    newer = project_view.material(data, project="Sørlige Nordsjø II", today=TODAY)
    assert project_view.stored(newer, TODAY)["complete"] is False


def test_portfolio_view_lists_project_areas(monkeypatch):
    _store_public()
    sent = []

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            sent.append(json.loads(text))
            return {"headline": "Two projects", "summary": "SN II moves.", "next": "",
                    "projects": [{"name": "Sørlige Nordsjø II", "status": "Licence", "momentum": "high"},
                                 {"name": "Utsira Nord", "status": "Quiet", "momentum": "nonsense"}]}

    monkeypatch.setattr(project_view, "AIClient", FakeAI)
    view = project_view.write(project_view.material(_data(), today=TODAY), TODAY)
    assert [p["name"] for p in sent[0]["projects"]] == ["Sørlige Nordsjø II", "Utsira Nord"]
    assert sent[0]["projects"][0]["journal_posts_30d"] == 1
    assert [p["momentum"] for p in view["projects"]] == ["high", ""]
