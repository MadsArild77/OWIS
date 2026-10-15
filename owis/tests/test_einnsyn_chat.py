import json

from fastapi.testclient import TestClient

from owis.modules.einnsyn import case_chat

CASE = {
    "ref": "iri-1", "title": "Ventyr SN II AS - Konsesjonsbehandling av nettilknytning", "case_number": "2024/8749",
    "agency": "NVE", "account": None, "related_news": [],
    "journal_posts": [
        {"id": "jp_2", "number": 2, "date": "2026-09-30", "direction": "outgoing", "title": "Oppsummering av møte med Ventyr",
         "from": "", "to": "Ventyr SN II AS", "documents": [{"title": "Møtereferat", "role": "main", "url": "u-meeting"}]},
        {"id": "jp_1", "number": 1, "date": "2026-08-01", "direction": "incoming", "title": "Søknad om konsesjon",
         "from": "Ventyr SN II AS", "to": "", "documents": [{"title": "Søknad", "role": "main", "url": "u-application"},
                                                            {"title": "Kart", "role": "attachment", "url": "u-map"}]},
    ],
}


class FakeTexts:
    def __init__(self):
        self.read = []

    def text(self, url):
        self.read.append(url)
        return f"text of {url}"


def test_picks_documents_matching_the_question_first():
    picked = case_chat.pick_documents(CASE, "Hva står i søknaden om konsesjon?", [])
    assert [d["url"] for d in picked][:2] == ["u-application", "u-map"]
    latest = case_chat.pick_documents(CASE, "What happened?", [])
    assert latest[0]["url"] == "u-meeting"  # no shared words: main documents, newest first
    newest = case_chat.pick_documents(CASE, "Hva står i de siste åpne dokumentene om søknaden?", [])
    assert newest[0]["url"] == "u-meeting"  # «siste» puts the newest first even when words match older ones


def test_answer_cites_documents_and_remembers_the_conversation(monkeypatch):
    prompts = []

    class FakeAI:
        enabled = True

        def _post_json_prompt(self, prompt, text, **kw):
            prompts.append(json.loads(text))
            return {"answer": "Ventyr søkte om konsesjon [1].", "cited": [1]}

    monkeypatch.setattr(case_chat, "AIClient", FakeAI)
    texts = FakeTexts()
    first = case_chat.answer(CASE, "Hva står i søknaden?", texts)
    assert first["sources"][0]["url"] == "u-application" and texts.read[0] == "u-application"
    assert prompts[0]["documents"][0]["text"] == "text of u-application"
    case_chat.answer(CASE, "Og deretter?", texts)
    assert [m["content"] for m in prompts[1]["conversation"]] == ["Hva står i søknaden?", "Ventyr søkte om konsesjon [1]."]
    stored = case_chat.conversation("iri-1")
    assert [m["role"] for m in stored] == ["user", "assistant", "user", "assistant"]
    assert stored[1]["sources"][0]["url"] == "u-application"
    case_chat.forget("iri-1")
    assert case_chat.conversation("iri-1") == []


def test_document_text_is_read_once_and_kept(monkeypatch):
    texts = case_chat.DocumentTexts()
    calls = []
    monkeypatch.setattr(texts, "_extract", lambda url: calls.append(url) or "pdf text")
    assert texts.text("u1") == "pdf text"
    fresh = case_chat.DocumentTexts()  # e.g. after a restart: comes from the database
    monkeypatch.setattr(fresh, "_extract", lambda url: calls.append(url) or "again")
    assert fresh.text("u1") == "pdf text" and calls == ["u1"]


def test_chat_history_endpoints():
    from owis.apps.api.main import app
    case_chat.remember("iri-9", "user", "Spørsmål")
    client = TestClient(app)
    url = "https://einnsyn.no/saksmappe?id=iri-9"
    assert [m["content"] for m in client.get("/api/einnsyn/case/chat", params={"ref": url}).json()["messages"]] == ["Spørsmål"]
    client.delete("/api/einnsyn/case/chat", params={"ref": url})
    assert client.get("/api/einnsyn/case/chat", params={"ref": url}).json()["messages"] == []
