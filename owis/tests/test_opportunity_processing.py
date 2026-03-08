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