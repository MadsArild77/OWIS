from owis.modules.news.processing.domain_classifier import classify_domain_bucket


def test_classify_domain_bucket_offshore_rule():
    bucket, confidence = classify_domain_bucket(
        title="Norway launches offshore wind lease round",
        summary="Floating wind project and turbine installation updates",
        themes="policy,projects",
    )
    assert bucket == "offshore_wind"
    assert confidence >= 0.8


def test_classify_domain_bucket_other_energy_rule():
    bucket, confidence = classify_domain_bucket(
        title="Oil and gas drilling expansion announced",
        summary="Upstream petroleum production increases next year",
        themes="energy",
    )
    assert bucket == "other_energy"
    assert confidence >= 0.66
