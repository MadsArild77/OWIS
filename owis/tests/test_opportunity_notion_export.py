from owis.core.notion.opportunities_export import OpportunitiesNotionExporter


def test_build_properties_includes_core_fields():
    exporter = OpportunitiesNotionExporter(api_key="x", database_id="db")

    db_props = {
        "Name": {"type": "title"},
        "Source": {"type": "select"},
        "TED Publication Number": {"type": "rich_text"},
        "Source Link": {"type": "url"},
        "Strategic Fit": {"type": "select"},
        "Competition Level": {"type": "select"},
        "Project Type": {"type": "multi_select"},
        "Signal Score": {"type": "number"},
        "Confidence": {"type": "number"},
    }

    item = {
        "title": "Offshore survey tender",
        "source_name": "DOFFIN",
        "source_url": "https://doffin.no/notices/1",
        "notice_id": "DOFFIN-1",
        "profile_name": "AGR",
        "strategic_fit": "Strong",
        "competition_level": "Low",
        "opportunity_family": "procurement_tenders",
        "signal_score": 84,
        "confidence": 0.78,
    }

    props = exporter._build_properties(
        item=item,
        db_props=db_props,
        dedup_field="TED Publication Number",
        dedup_key="DOFFIN-1:AGR",
    )

    assert "Name" in props
    assert props["Name"]["title"][0]["text"]["content"] == "Offshore survey tender"
    assert props["TED Publication Number"]["rich_text"][0]["text"]["content"] == "DOFFIN-1:AGR"
    assert props["Source"]["select"]["name"] == "DOFFIN"
    assert props["Signal Score"]["number"] == 84.0


def test_normalize_date_supports_iso_and_date_only():
    exporter = OpportunitiesNotionExporter(api_key="x", database_id="db")

    assert exporter._normalize_date("2026-03-08") == "2026-03-08"
    assert exporter._normalize_date("2026-03-08T12:30:00Z") == "2026-03-08"
    assert exporter._normalize_date("invalid") is None