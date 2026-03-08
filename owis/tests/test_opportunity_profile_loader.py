import yaml

from owis.modules.opportunities.registry import profile_loader


def test_load_profile_bundle_filters_active_profiles(tmp_path, monkeypatch):
    profile_path = tmp_path / "profiles.yaml"
    profile_path.write_text(
        yaml.safe_dump(
            {
                "profiles": [
                    {
                        "company": "AGR",
                        "name": "Marine",
                        "keywords": ["survey"],
                        "aliases": ["hydrographic"],
                        "qualifier": ["offshore"],
                        "negative_keywords": ["school"],
                        "cpv_codes": ["71354500", "00000000"],
                    },
                    {
                        "company": "MAV",
                        "name": "Advisory",
                        "keywords": ["strategy"],
                        "qualifier": ["wind"],
                        "cpv_codes": ["79411100"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(profile_loader, "OPPORTUNITIES_PROFILES_PATH", str(profile_path))

    bundle = profile_loader.load_profile_bundle(active_profiles=["AGR"])

    assert "AGR" in bundle["by_company"]
    assert "MAV" not in bundle["by_company"]
    assert "71354500" in bundle["all_cpv_codes"]
    assert "00000000" not in bundle["all_cpv_codes"]
    assert "hydrographic" in bundle["keywords_by_company"]["AGR"]