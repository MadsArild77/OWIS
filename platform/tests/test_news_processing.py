from platform.modules.news.processing import pipeline


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
