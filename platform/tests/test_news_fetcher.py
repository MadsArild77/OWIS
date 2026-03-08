from types import SimpleNamespace

import yaml

from platform.modules.news.collectors import rss_fetcher


def test_fetch_rss_items_from_enabled_sources(tmp_path, monkeypatch):
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {
                        "name": "TestFeed",
                        "type": "rss",
                        "url": "https://example.com/feed",
                        "enabled": True,
                        "priority": "high",
                        "geography_tags": ["global"],
                    },
                    {
                        "name": "DisabledFeed",
                        "type": "rss",
                        "url": "https://example.com/disabled",
                        "enabled": False,
                        "priority": "low",
                        "geography_tags": ["global"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(rss_fetcher, "NEWS_SOURCES_PATH", str(sources_path))

    def fake_parse(url: str):
        assert url == "https://example.com/feed"
        return SimpleNamespace(
            entries=[
                {
                    "link": "https://example.com/a1",
                    "title": "Auction announced in Norway",
                    "summary": "A new offshore wind auction has been announced.",
                    "published": "2026-03-08T10:00:00Z",
                }
            ]
        )

    monkeypatch.setattr(rss_fetcher.feedparser, "parse", fake_parse)

    items = rss_fetcher.fetch_rss_items()

    assert len(items) == 1
    assert items[0]["source_name"] == "TestFeed"
    assert items[0]["article_url"] == "https://example.com/a1"
    assert items[0]["title_raw"] == "Auction announced in Norway"
    assert items[0]["content_hash"]

