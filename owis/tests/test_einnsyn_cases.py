import json

import httpx

from owis.core.storage.db import get_conn
from owis.modules.einnsyn import big_picture, case_accounts, links
from owis.modules.einnsyn.case_source import CaseSource, case_ref

FOLDER = {"id": "sm_1", "offentligTittel": "Ventyr SN II AS - Konsesjonsbehandling av nettilknytning av Sørlige Nordsjø II",
          "saksnummer": "2024/8749", "journalenhet": "enh_1"}
POSTS = [
    {"id": "jp_1", "journalpostnummer": 1, "journaldato": "2026-09-01", "offentligTittel": "Søknad om konsesjon",
     "journalposttype": "inngaaende_dokument",
     "korrespondansepart": [{"korrespondanseparttype": "avsender", "korrespondansepartNavn": "Ventyr SN II AS"}],
     "dokumentbeskrivelse": [
         {"tittel": "Søknad", "tilknyttetRegistreringSom": ".../hoveddokument", "dokumentobjekt": [{"id": "do_1"}]},
         {"tittel": "Kart", "tilknyttetRegistreringSom": ".../vedlegg", "dokumentobjekt": [{"id": "do_2"}]}]},
    {"id": "jp_2", "journalpostnummer": 2, "journaldato": "2026-09-20", "offentligTittel": "Svar på søknad",
     "journalposttype": "utgaaende_dokument", "skjerming": {"id": "skj"},
     "korrespondansepart": [{"korrespondanseparttype": "mottaker", "korrespondansepartNavn": "*"}],
     "dokumentbeskrivelse": []},
]


def _source():
    def handler(request):
        path = request.url.path
        if path == "/saksmappe":
            return httpx.Response(200, json={"items": [FOLDER]})
        if path == "/saksmappe/sm_1/journalpost":
            return httpx.Response(200, json={"items": POSTS})
        if path == "/enhet/enh_1":
            return httpx.Response(200, json={"navn": "NVE"})
        return httpx.Response(404)
    return CaseSource(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_case_ref_from_links():
    assert case_ref("https://einnsyn.no/saksmappe?id=http%3A%2F%2Fdata.einnsyn.no%2Fx") == "http://data.einnsyn.no/x"
    assert case_ref("sm_1") == "sm_1"


def test_case_reads_posts_documents_and_parties():
    case = _source().case("https://einnsyn.no/saksmappe?id=iri-1")
    assert (case["case_number"], case["agency"], case["open_documents"], case["posts_with_documents"]) == ("2024/8749", "NVE", 2, 1)
    latest, first = case["journal_posts"]
    assert latest["id"] == "jp_2" and latest["direction"] == "outgoing" and latest["restricted"] and latest["to"] == ""
    assert first["from"] == "Ventyr SN II AS" and [d["role"] for d in first["documents"]] == ["main", "attachment"]
    assert first["documents"][0]["url"] == "https://api.einnsyn.no/dokumentobjekt/do_1/download"


def test_account_is_kept_and_marked_outdated_after_new_posts(monkeypatch):
    case = _source().case("iri-1")

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            assert json.loads(text)["journal_posts"][0]["open_document"] is True
            return {"title": "Ventyr seeks grid licence", "summary": "Ventyr applied.", "stage": "Under review",
                    "next_steps": "Likely: a decision.", "documents": ""}

    monkeypatch.setattr(case_accounts, "AIClient", FakeAI)
    assert case_accounts.stored(case) is None
    account = case_accounts.write(case)
    assert account["complete"] and account["next_steps"].startswith("Likely")
    newer = dict(case, journal_posts=case["journal_posts"] + [dict(case["journal_posts"][0], id="jp_3")])
    assert case_accounts.stored(newer)["complete"] is False


def _add_news(title, project, companies):
    with get_conn() as conn:
        raw = conn.execute("""INSERT INTO news_raw_items(source_name, article_url, title_raw, content_hash, published_at, fetched_at)
            VALUES('OffshoreWIND.biz', ?, ?, 'h', '2099-01-01T00:00:00Z', '2099-01-01')""", (f"https://x/{title}", title)).lastrowid
        pid = conn.execute("""INSERT INTO news_processed_items(raw_item_id, title, cleaned_text, summary, theme_tags,
            geography_tags, actors, why_it_matters, signal_score, confidence, linkedin_angle, linkedin_candidate, processed_at)
            VALUES(?, ?, '', '', '[]', '[]', '[]', '', 80, 0.9, '', 0, '2099-01-01')""", (raw, title)).lastrowid
        conn.execute("INSERT INTO news_event_cards(processed_id, card_json, created_at) VALUES(?,?, '2099-01-01')",
                     (pid, json.dumps({"project": project, "companies": companies})))
    return pid


def test_links_both_ways_on_project_and_specific_companies():
    sn2 = _add_news("Ventyr picks cable supplier", "Sørlige Nordsjø II offshore wind farm", ["Ventyr", "Equinor ASA"])
    other = _add_news("Equinor results", "", ["Equinor ASA"])
    case = _source().case("iri-1")
    related = links.news_for_case(case)
    assert [n["title"] for n in related] == ["Ventyr picks cable supplier"]
    assert related[0]["matched_on"] == ["sorlige nordsjo ii"]
    saker = [{"Name": FOLDER["offentligTittel"], "Saksnummer": "2024/8749", "Status": "Aktiv", "URL": "u"},
             {"Name": "Equinor - noe annet", "Saksnummer": "2025/1", "Status": "Aktiv", "URL": "v"}]
    assert [c["case_number"] for c in links.cases_for_news([sn2], saker)] == ["2024/8749"]
    assert links.cases_for_news([other], saker) == []  # single-word company names link nothing


SAKER = [
    {"Name": FOLDER["offentligTittel"], "Saksnummer": "2024/8749", "Status": "Aktiv",
     "URL": "https://einnsyn.no/saksmappe?id=iri-1", "Prosjektområde": "Sørlige Nordsjø II, Generelt/Tversgående"},
    {"Name": "Leverandørnettverk Sørlige Nordsjø II", "Saksnummer": "2025/36902", "Status": "Aktiv", "URL": "u2",
     "Prosjektområde": "Sørlige Nordsjø II"},
    {"Name": "Avvist sak", "Saksnummer": "2025/1", "Status": "Ikke relevant", "URL": "u3", "Prosjektområde": "Sørlige Nordsjø II"},
    {"Name": "Generell sak", "Saksnummer": "2025/2", "Status": "Aktiv", "URL": "u4", "Prosjektområde": "Generelt/Tversgående"},
]


def test_big_picture_context_uses_news_and_cases_on_the_same_project():
    _add_news("Ventyr signs grid deal", "Sørlige Nordsjø II", ["Ventyr"])
    case = _source().case("iri-1")
    ctx = big_picture.context(case, SAKER)
    assert ctx["projects"] == ["Sørlige Nordsjø II"]  # the broad area does not make cases related
    assert [c["case_number"] for c in ctx["cases"]] == ["2025/36902"]
    assert "Ventyr signs grid deal" in [n["title"] for n in ctx["news"]]
    assert big_picture.context(case, [])["cases"] == []  # case not in Notion: news only


def test_big_picture_is_kept_with_its_sources_and_marked_outdated(monkeypatch):
    _add_news("Ventyr picks substation design", "Sørlige Nordsjø II", ["Ventyr"])
    case = _source().case("iri-1")
    ctx = big_picture.context(case, SAKER)
    sent = {}

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            sent.update(json.loads(text))
            return {"headline": "Grid link for Sørlige Nordsjø II takes shape",
                    "summary": "The licence case runs alongside the supplier news [1] and a deal [99].", "watch": "Watch NVE [7].",
                    "cited": [1, 99]}

    monkeypatch.setattr(big_picture, "AIClient", FakeAI)
    result = big_picture.write(case, ctx, {"summary": "Ventyr applied.", "stage": "Under review"})
    assert sent["case"]["account"] == "Ventyr applied." and sent["other_cases"][0]["case_number"] == "2025/36902"
    assert sent["news"][0]["n"] == 1
    assert result["complete"] and result["headline"].startswith("Grid link")
    assert [s["n"] for s in result["sources"]] == [1]  # out-of-range citations are dropped
    assert result["sources"][0]["title"] == ctx["news"][0]["title"]
    assert result["summary"] == "The licence case runs alongside the supplier news [1] and a deal."
    assert result["watch"] == "Watch NVE."
    renamed = dict(ctx, cases=[dict(ctx["cases"][0], status="Pause")])
    assert big_picture.stored(case, renamed)["complete"] is False  # a changed case status brings a rewrite
    fewer = dict(ctx, cases=[])
    assert big_picture.stored(case, fewer)["complete"] is False
    assert big_picture.write(case, {"projects": [], "news": [], "cases": []}) is None  # nothing to put it in context with
