from owis.modules.opportunities.processing import pipeline


def test_process_opportunity_classifies_and_extracts_deadline():
    raw = {
        "id": 1,
        "title_raw": "Offshore wind tender for subsea cable survey",
        "description_raw": "Marine survey procurement with submission deadline 2026-04-20.",
        "buyer_raw": "Norwegian Authority",
        "country_raw": "NOR",
        "notice_url": "https://example.com/notice",
        "source_name": "DOFFIN",
        "publication_date": "2026-03-08",
    }

    profile_bundle = {
        "by_company": {
            "AGR": [
                {
                    "name": "Marine Survey",
                    "keywords": ["survey", "subsea", "cable"],
                    "qualifier": ["offshore", "marine"],
                    "negative_keywords": ["school", "hospital"],
                }
            ]
        }
    }

    processed = pipeline.process_raw_item(raw, profile_bundle=profile_bundle, active_profiles=["AGR"])

    assert processed is not None
    assert processed["opportunity_family"] == "procurement_tenders"
    assert processed["mechanism_type"] == "tender"
    assert processed["deadline"] == "2026-04-20"
    assert processed["profile_name"] == "AGR"


def test_process_opportunity_rejects_negative_keyword():
    raw = {
        "id": 2,
        "title_raw": "Offshore maintenance notice",
        "description_raw": "Offshore school building maintenance program.",
        "buyer_raw": "Example Buyer",
        "country_raw": "NOR",
        "notice_url": "https://example.com/notice2",
        "source_name": "TED",
        "publication_date": "2026-03-08",
    }

    profile_bundle = {
        "by_company": {
            "AGR": [
                {
                    "name": "Marine Survey",
                    "keywords": ["maintenance"],
                    "qualifier": ["offshore"],
                    "negative_keywords": ["school"],
                }
            ]
        }
    }

    processed = pipeline.process_raw_item(raw, profile_bundle=profile_bundle, active_profiles=["AGR"])
    assert processed is None

def test_empty_qualifiers_match_havvindpark_and_keep_existing_qualifiers():
    from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
    bundle = load_profile_bundle(["OWIS", "AGR"])
    result = pipeline.classify_notice({"description": "havvindpark", "country": "NOR"}, bundle, ["OWIS"])
    assert result["profile_name"] == "OWIS"
    assert result["matched_qualifiers"] == []
    assert pipeline.classify_notice({"description": "geotechnical", "country": "NOR"}, bundle, ["AGR"]) is None
    assert pipeline.classify_notice({"description": "offshore geotechnical", "country": "NOR"}, bundle, ["AGR"]) is not None
    assert pipeline.classify_notice({"description": "onshore wind farm", "country": "NOR"}, bundle, ["OWIS"]) is None


def test_source_deadline_precedes_earlier_text_date_and_preserves_value():
    from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
    raw = {"id": 1, "title_raw": "havvindpark", "description_raw": "Published 2026-01-01. Meeting 2026-02-01.",
           "deadline_raw": "2026-12-18T11:00:00Z", "estimated_value": 1000000, "currency": "NOK"}
    bundle = load_profile_bundle(["OWIS"])
    item = pipeline.process_raw_item(raw, bundle, ["OWIS"])
    assert item["deadline"] == "2026-12-18"
    assert item["deadline_source"] == "source"
    assert item["estimated_value"] == 1000000
    assert item["currency"] == "NOK"
    raw.pop("deadline_raw")
    item = pipeline.process_raw_item(raw, bundle, ["OWIS"])
    assert item["deadline"] == "2026-01-01"
    assert item["deadline_source"] == "text"


def test_markets_preserve_primary_and_add_secondary():
    assert pipeline._country_score("GBR") == 10
    assert all(pipeline._country_score(country) == 5 for country in ["FRA", "POL", "DEU", "NLD"])


def test_empty_qualifier_profile_can_match_within_mixed_company():
    bundle = {"by_company": {"OWIS": [
        {"name": "Market", "keywords": ["havvindpark"], "qualifier": []},
        {"name": "Survey", "keywords": ["survey"], "qualifier": ["offshore"]},
    ]}}
    item = pipeline.classify_notice({"description": "havvindpark survey"}, bundle, ["OWIS"])
    assert item["matched_services"] == ["Market"]
