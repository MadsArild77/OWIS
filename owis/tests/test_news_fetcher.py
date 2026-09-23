from types import SimpleNamespace

from owis.modules.news.collectors import rss_fetcher


def test_fetch_rss_items_from_enabled_sources(monkeypatch):
    monkeypatch.setattr(
        rss_fetcher,
        "load_sources",
        lambda: [
            {
                "name": "TestFeed",
                "type": "rss",
                "url": "https://example.com/feed",
                "enabled": True,
            },
            {
                "name": "ScrapeOnly",
                "type": "scrape",
                "url": "https://example.com",
                "enabled": True,
            },
        ],
    )

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

    monkeypatch.setattr(rss_fetcher, "_parse_feed", fake_parse)

    items = rss_fetcher.fetch_rss_items()

    assert len(items) == 1
    assert items[0]["source_name"] == "TestFeed"
    assert items[0]["article_url"] == "https://example.com/a1"
    assert items[0]["title_raw"] == "Auction announced in Norway"
    assert items[0]["content_hash"]



def test_http_error_is_reported(monkeypatch):
    import httpx
    monkeypatch.setattr(rss_fetcher, "load_sources", lambda: [dict(name="Broken", type="rss", url="https://example.com/feed")])
    monkeypatch.setattr(rss_fetcher.httpx, "get", lambda *a, **kw: httpx.Response(404, request=httpx.Request("GET", a[0])))
    items, report = rss_fetcher.fetch_rss_items_with_report()
    assert items == []
    assert report[0]["status"] == "error"
    assert "404" in report[0]["error"]


def test_full_feed_content_is_preserved(monkeypatch):
    import httpx
    xml = b'<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>Wind</title><item><title>New offshore wind project in Norway</title><link>https://example.com/new-offshore-wind-project-norway</link><description>Short summary</description><content:encoded><![CDATA[<p>Complete offshore wind project description in Norway.</p>]]></content:encoded></item></channel></rss>'
    monkeypatch.setattr(rss_fetcher, "load_sources", lambda: [dict(name="Test", type="rss", url="https://example.com/feed")])
    monkeypatch.setattr(rss_fetcher.httpx, "get", lambda *a, **kw: httpx.Response(200, content=xml, request=httpx.Request("GET", a[0])))
    items, report = rss_fetcher.fetch_rss_items_with_report()
    assert report[0]["status"] == "ok"
    assert "Complete offshore" in items[0]["content_raw"]


def test_html_response_is_not_a_healthy_feed(monkeypatch):
    import httpx
    import pytest
    monkeypatch.setattr(rss_fetcher.httpx, "get", lambda *a, **kw: httpx.Response(200, text="<html>Login required</html>", request=httpx.Request("GET", a[0])))
    with pytest.raises(ValueError, match="RSS or Atom"):
        rss_fetcher._parse_feed("https://example.com/feed")

