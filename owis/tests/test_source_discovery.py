import yaml

from owis.modules.news.registry import source_discovery


def test_parse_source_input_supports_name_dash_url_and_plain_url():
    text = "Recharge - rechargenews.com\nhttps://windeurope.org"
    parsed = source_discovery.parse_source_input(text)

    assert len(parsed) == 2
    assert parsed[0].name == "Recharge"
    assert parsed[0].homepage == "https://rechargenews.com"
    assert parsed[1].homepage == "https://windeurope.org"


def test_import_sources_uses_rss_then_scrape(tmp_path, monkeypatch):
    registry_path = tmp_path / "sources.yaml"
    registry_path.write_text(yaml.safe_dump({"sources": []}), encoding="utf-8")

    monkeypatch.setattr(source_discovery, "NEWS_SOURCES_PATH", str(registry_path))

    def fake_discover(url: str):
        if "rechargenews" in url:
            return "https://rechargenews.com/rss"
        return None

    monkeypatch.setattr(source_discovery, "discover_feed_url", fake_discover)

    added = source_discovery.import_sources_from_text(
        "Recharge - https://rechargenews.com\nWindEurope - https://windeurope.org"
    )

    assert len(added) == 2
    assert added[0]["type"] == "rss"
    assert added[0]["url"] == "https://rechargenews.com/rss"
    assert added[1]["type"] == "scrape"

