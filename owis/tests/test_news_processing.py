from owis.modules.news.processing import pipeline


def test_process_raw_item_uses_ai_payload(monkeypatch):
    def fake_enrich(self, text: str):
        return {
            "summary": "AI summary",
            "theme_tags": ["policy"],
            "geography_tags": ["Norway"],
            "actors": ["Equinor"],
            "why_it_matters": "AI says this matters.",
            "linkedin_angle": "AI angle",
            "confidence": 0.91,
        }

    monkeypatch.setattr(pipeline.AIClient, "enrich_news", fake_enrich)

    raw = {
        "id": 1,
        "title_raw": "New policy update",
        "summary_raw": "Some summary",
        "content_raw": "Detailed policy content from Norway involving Equinor.",
    }

    processed = pipeline.process_raw_item(raw)

    assert processed["summary"] == "AI summary"
    assert processed["theme_tags"] == "policy"
    assert processed["geography_tags"] == "Norway"
    assert processed["actors"] == "Equinor"
    assert processed["why_it_matters"] == "AI says this matters."
    assert processed["linkedin_angle"] == "AI angle"
    assert processed["confidence"] == 0.91


def test_process_raw_item_heuristics_add_specific_story_tags(monkeypatch):
    def fake_enrich(self, text: str):
        raise RuntimeError("ai unavailable")

    monkeypatch.setattr(pipeline.AIClient, "enrich_news", fake_enrich)

    raw = {
        "id": 2,
        "title_raw": "ESA clears Utsira Nord support model",
        "summary_raw": "Government and NVE move the Utsira Nord process forward.",
        "content_raw": (
            "The Norwegian government sent the Utsira Nord notification to ESA. "
            "Ventyr and other offshore wind players are watching the state aid decision closely."
        ),
    }

    processed = pipeline.process_raw_item(raw)

    assert "policy" in processed["theme_tags"]
    assert "utsira_nord" in processed["theme_tags"]
    assert "state_aid" in processed["theme_tags"]
    assert "Norway" in processed["geography_tags"]
    assert "ESA" in processed["actors"]
    assert "Ventyr" in processed["actors"]


def test_process_raw_item_tags_obvious_energy_policy_context(monkeypatch):
    def fake_enrich(self, text: str):
        raise RuntimeError("ai unavailable")

    monkeypatch.setattr(pipeline.AIClient, "enrich_news", fake_enrich)

    raw = {
        "id": 3,
        "title_raw": "Norgespris kan endre kraftmarkedet",
        "summary_raw": "Regjeringen varsler ny strømprisordning.",
        "content_raw": (
            "Norgespris og ny strømpris-politikk kan påvirke kraftmarkedet i Norge. "
            "Ordningen kan også endre investeringssignaler, kraftbalanse og rammevilkår for elektrifisering."
        ),
    }

    processed = pipeline.process_raw_item(raw)

    assert "norgespris" in processed["theme_tags"]
    assert "power_price_policy" in processed["theme_tags"]
    assert "electricity_market_design" in processed["theme_tags"]
    assert "energy_security" in processed["theme_tags"]
    assert "Norway" in processed["geography_tags"]

