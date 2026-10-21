import json
from datetime import date

import httpx

from owis.core.storage.db import get_conn
from owis.modules.einnsyn import feedback, project_view, public_sources
from owis.tests.test_einnsyn_project_view import TODAY, _data, _store_public


def _clear():
    feedback._ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM einnsyn_feedback")


def test_interpret_restates_and_stores_nothing(monkeypatch):
    _clear()
    seen = []

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            seen.append(json.loads(text))
            return {"interpretation": "Jeg oppfatter at du mener at Ventyr trakk søknaden i august.",
                    "correction": "Ventyr withdrew the application in August 2026.", "action": "correction", "unclear": ""}

    monkeypatch.setattr(feedback, "AIClient", FakeAI)
    out = feedback.interpret({"target_type": "helicopter", "label": "SN II", "context": "..."}, "Ventyr trakk søknaden i august")
    assert out["interpretation"].startswith("Jeg oppfatter") and out["action"] == "correction"
    assert seen[0]["reader_says"] == "Ventyr trakk søknaden i august"
    assert feedback.for_scopes([("project", "Sørlige Nordsjø II")]) == []


def test_not_relevant_drops_an_item_from_the_project_and_corrections_reach_the_prompt(monkeypatch):
    _clear()
    _store_public()
    m = project_view.material(_data(), project="Sørlige Nordsjø II", today=TODAY)
    item = next(e for e in project_view.timeline(m) if e["kind"] == "written_question")
    feedback.save("project", "Sørlige Nordsjø II", item["kind"], item["id"], "not_relevant", target_label=item["title"])
    feedback.save("project", "Sørlige Nordsjø II", "helicopter", "helicopter", "correction", "trakk søknaden",
                  "Ventyr withdrew the application in August 2026.")
    feedback.save("project", "Utsira Nord", "helicopter", "helicopter", "correction", "x", "Only about Utsira Nord.")
    m2 = project_view.material(_data(), project="Sørlige Nordsjø II", today=TODAY)
    assert item["id"] not in {e["id"] for e in project_view.timeline(m2)}
    payload = project_view._payload(m2, TODAY)
    assert payload["reader_corrections"] == ["Ventyr withdrew the application in August 2026."]
    assert project_view.signature(payload) != project_view.signature(project_view._payload(m, TODAY))
    # the Utsira Nord project is not affected; corrections for «everything» reach both
    other = project_view.material(_data(), project="Utsira Nord", today=TODAY)
    assert project_view._payload(other, TODAY)["reader_corrections"] == ["Only about Utsira Nord."]
    feedback.save("all", "", "helicopter", "", "correction", "y", "Equinor is not involved in SN II.")
    assert "Equinor is not involved in SN II." in project_view._payload(
        project_view.material(_data(), project="Utsira Nord", today=TODAY), TODAY)["reader_corrections"]


def test_removing_a_correction_brings_the_item_back():
    _clear()
    _store_public()
    m = project_view.material(_data(), project="Sørlige Nordsjø II", today=TODAY)
    item = next(e for e in project_view.timeline(m) if e["kind"] == "journal_post")
    saved = feedback.save("project", "Sørlige Nordsjø II", item["kind"], item["id"], "not_relevant")
    assert item["id"] not in {e["id"] for e in project_view.timeline(project_view.material(_data(), project="Sørlige Nordsjø II", today=TODAY))}
    feedback.remove(saved["id"])
    assert item["id"] in {e["id"] for e in project_view.timeline(project_view.material(_data(), project="Sørlige Nordsjø II", today=TODAY))}


def test_case_account_signature_follows_its_corrections():
    _clear()
    from owis.modules.einnsyn import case_accounts
    case = {"ref": "iri-1", "journal_posts": [{"id": "jp_1"}]}
    before = case_accounts.signature(case)
    feedback.save("case", "iri-1", "account", "account", "correction", "x", "The applicant is Ventyr SN II AS.")
    assert case_accounts.signature(case) != before


def test_answers_to_storting_questions_are_read_once(monkeypatch):
    monkeypatch.setattr(public_sources.time, "sleep", lambda s: None)
    _store_public()
    calls = []

    def handler(request):
        calls.append(request.url.params.get("NSporsmalId"))
        return httpx.Response(200, json={"sporsmal": "Når får SN2 konsesjon?", "begrunnelse": "Fordi.",
                                         "svar": "Konsesjonen behandles av NVE.<br/><br/>Vedtak ventes i 2027."})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert public_sources.fetch_answers(client) == 1  # only the answered question
    assert public_sources.fetch_answers(client) == 0 and calls == ["1"]
    item = next(i for i in public_sources.items([], []) if i["id"] == "stortinget:written_question-1")
    assert item["answer"] == "Konsesjonen behandles av NVE.\n\nVedtak ventes i 2027." and item["reasoning"] == "Fordi."
