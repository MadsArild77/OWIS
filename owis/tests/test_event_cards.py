from types import SimpleNamespace

from owis.core.storage import db
from owis.modules.news.matching.semantic import article_text, embedding_text
from owis.modules.news.processing import event_cards


def test_photo_captions_are_not_used_as_evidence():
    assert event_cards.is_caption_only("Offshore wind is a key pillar of UK clean power. Photo: Cadeler")
    assert not event_cards.is_caption_only("Ørsted and Nuveen have inaugurated the 913 MW Borkum Riffgrund 3.")
    assert event_cards.evidence_text("Greenpeace threatens Crown Estate", "Pillar. Photo: Cadeler") == "Greenpeace threatens Crown Estate\n"


def test_cards_are_made_once_and_used_for_matching(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "cards.db"))
    db.init_db()
    calls = []
    fake = SimpleNamespace(enabled=True, _post_json_prompt=lambda **kw: calls.append(kw) or {
        "what_happened": "Ørsted and Nuveen inaugurated Borkum Riffgrund 3", "event_type": "project_milestone",
        "project": "Borkum Riffgrund 3", "companies": ["Ørsted", "Nuveen"], "location": "Germany", "capacity": "913 MW"})
    monkeypatch.setattr(event_cards, "AIClient", lambda: fake)
    items = [{"id": 1, "title": "Ørsted åpner stor tysk havvindpark", "cleaned_text": "Borkum Riffgrund 3 ..."}]
    assert event_cards.ensure_cards(items) == 1 and event_cards.ensure_cards(items) == 0 and len(calls) == 1
    event_cards.attach_cards(items)
    assert "Project: Borkum Riffgrund 3" in items[0]["event_text"] and "Capacity: 913 MW" in items[0]["event_text"]
    assert embedding_text(items[0]).endswith(items[0]["event_text"])
    assert "Event card:" in article_text(items[0])
