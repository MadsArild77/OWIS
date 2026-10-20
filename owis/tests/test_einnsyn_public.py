import httpx

from owis.modules.einnsyn import big_picture, public_sources as ps

SAKER = [{"Prosjektområde": p, "Status": "Aktiv"} for p in
         ["Sørlige Nordsjø II", "Generelt / Tversgående", "METCentre / Karmøy", "Brage Havvind", "Havsul / Trollvind"]]
SOK = [{"Name": '"Sørlige Nordsjø II" | SN2', "Status": "Aktiv"}, {"Name": "havvind", "Status": "Aktiv"},
       {"Name": '"Marin energi testsenter" | METCentre', "Status": "Aktiv"}, {"Name": "Paused term", "Status": "Pause"}]
D = "/Date(1790773419482+0200)/"  # 2026-09-30


def test_terms_find_projects_by_name_and_search_term_aliases():
    t = ps.terms(SAKER, SOK)["projects"]
    assert t["Sørlige Nordsjø II"] == {"sorlige nordsjo ii", "sn2"}
    assert t["METCentre / Karmøy"] == {"metcentre karmoy", "metcentre", "marin energi testsenter"}  # not «karmoy»
    assert t["Brage Havvind"] == {"brage havvind"}  # the general term «havvind» does not make it Brage's
    assert t["Havsul / Trollvind"] == {"havsul trollvind", "havsul", "trollvind"}  # no search term: the parts
    assert "Generelt / Tversgående" not in t


def _client():
    def handler(request):
        path = request.url.path
        if path.endswith("/sesjoner"):
            return httpx.Response(200, json={"innevaerende_sesjon": {"id": "2026-2027"},
                                             "sesjoner_liste": [{"id": "2026-2027"}, {"id": "2025-2026"}]})
        if request.url.params.get("sesjonid") != "2026-2027":
            return httpx.Response(200, json={})
        if path.endswith("/skriftligesporsmal"):
            return httpx.Response(200, json={"sporsmal_liste": [
                {"id": 1, "tittel": "Når kommer konsesjonen for Sørlige Nordsjø II?", "datert_dato": D, "besvart_dato": D,
                 "sporsmal_fra": {"fornavn": "Kari", "etternavn": "Nordmann", "parti": {"id": "H"}},
                 "sporsmal_til_minister_tittel": "energiministeren"},
                {"id": 2, "tittel": "Om fiskekvoter", "datert_dato": D}]})
        if path.endswith("/saker"):
            return httpx.Response(200, json={"saker_liste": [
                {"id": 9, "tittel": "Representantforslag om havvindprosjektene", "korttittel": "Havvindprosjektene",
                 "sist_oppdatert_dato": D, "status": 1, "komite": {"navn": "Energi- og miljøkomiteen"}}]})
        if path.endswith("/horinger"):
            return httpx.Response(200, json={"horinger_liste": [
                {"id": 5, "horing_status": "Planlagt", "start_dato": D, "komite": {"navn": "Energi- og miljøkomiteen"},
                 "horing_sak_info_liste": [{"sak_id": 9, "sak_tittel": "Test av flytende vind på METCentre"}]}]})
        return httpx.Response(200, json={"sporsmal_liste": []})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_refresh_keeps_relevant_storting_records_and_links_them_to_projects(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    result = ps.refresh(SAKER, SOK, client=_client())
    assert result == {"stortinget": 3}
    runs = ps.runs()
    assert runs["stortinget"]["ok"] and not runs["calendar"]["ok"] and "TAVILY_API_KEY" in runs["calendar"]["detail"]
    found = {i["id"]: i for i in ps.items(SAKER, SOK)}
    q = found["stortinget:written_question-1"]
    assert q["projects"] == ["Sørlige Nordsjø II"] and q["person"] == "Kari Nordmann (H)"
    assert q["date"] == "2026-09-30" and q["status"].startswith("Answered") and "qid=1" in q["url"]
    assert found["stortinget:case-9"]["projects"] == [] and found["stortinget:case-9"]["status"] == "Dealt with"
    assert found["stortinget:hearing-5"]["projects"] == ["METCentre / Karmøy"]
    assert "stortinget:written_question-2" not in found  # names nothing we follow
    assert [i["id"] for i in ps.items(SAKER, SOK, projects=["METCentre / Karmøy"])] == ["stortinget:hearing-5"]


def test_calendar_articles_are_read_once_and_kept(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    searches, prompts = [], []
    article = {"url": "https://www.regjeringen.no/no/aktuelt/utdrag-fra-energiminister-kalender-for-veke-38/id1/",
               "title": "Utdrag frå energiminister Terje Aaslands kalender for veke 38",
               "raw_content": "Måndag 14. september: Møte med Equinor om Utsira Nord. " * 5}
    monkeypatch.setattr(ps, "_tavily_search", lambda q: searches.append(q) or [article, {"url": "https://x.no", "title": "Other"}])

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            prompts.append(text)
            return {"entries": [{"date": "2026-09-14", "time": "10:00", "title": "Møte med Equinor om Utsira Nord", "place": "Oslo"},
                                {"date": "bad", "title": "dropped"}]}

    import owis.core.llm.client as client
    monkeypatch.setattr(client, "AIClient", FakeAI)
    first = ps.calendar_items()
    assert [(i["day"], i["title"], i["status"]) for i in first] == [("2026-09-14", "Møte med Equinor om Utsira Nord", "10:00")]
    assert ps.calendar_items() == first and len(prompts) == 1  # the article is not read again


def test_big_picture_numbers_public_records_after_the_news(monkeypatch):
    ctx = {"projects": ["Sørlige Nordsjø II"], "news": [{"id": 1, "title": "N", "url": "u", "source": "S", "published": "d"}],
           "cases": [], "public": [{"id": "stortinget:q", "title": "Q", "url": "q", "kind_label": "Written question",
                                    "date": "2026-09-20", "status": "", "person": "", "body": ""}]}
    numbered = big_picture._numbered(ctx)
    assert [n["title"] for n in numbered] == ["N", "Q"] and numbered[1]["source"] == "Written question"
