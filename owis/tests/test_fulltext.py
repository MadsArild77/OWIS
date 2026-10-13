import time

import pytest

from owis.core.storage import db
from owis.modules.news.collectors.filters import is_probable_article_url
from owis.modules.news.processing import fulltext
from owis.modules.news.processing.editorial import topics_for


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "fulltext.db"))
    monkeypatch.setenv("TAVILY_API_KEY", "test")
    db.init_db()


def test_learns_to_skip_a_method_that_keeps_failing(monkeypatch):
    calls = []
    def blocked(url):
        calls.append(url)
        return "blocked", "", url
    monkeypatch.setattr(fulltext, "extract", lambda url: ("open", "Full article. " * 100))
    for _ in range(3):
        assert fulltext.fetch_fulltext("Renews", "https://renews.example/a", blocked)[0] == "open"
    assert len(calls) == 3
    never = lambda: 0.99
    monkeypatch.setattr(fulltext.random, "random", never)
    fulltext.fetch_fulltext("Renews", "https://renews.example/b", blocked)
    assert len(calls) == 3                      # direct is skipped now, Tavily is used straight away
    monkeypatch.setattr(fulltext.random, "random", lambda: 0.01)
    fulltext.fetch_fulltext("Renews", "https://renews.example/c", blocked)
    assert len(calls) == 4                      # one in ten still retries direct
    assert fulltext.summary()[0]["strategy"] == "extract"


def test_paywalled_sources_are_marked_closed_and_skip_tavily(monkeypatch):
    extracts = []
    monkeypatch.setattr(fulltext, "extract", lambda url: extracts.append(url) or ("thin", ""))
    teaser = lambda url: ("unknown", "", url)
    for i in range(3):
        fulltext.fetch_fulltext("Recharge", f"https://recharge.example/{i}", teaser)
    monkeypatch.setattr(fulltext.random, "random", lambda: 0.99)
    assert fulltext.fetch_fulltext("Recharge", "https://recharge.example/x", teaser)[0] == "unknown"
    assert len(extracts) == 3
    assert fulltext.summary()[0]["strategy"] == "closed"
    restricted = lambda url: ("restricted", "", url)
    fulltext.fetch_fulltext("Europower", "https://europower.example/1", restricted)
    assert len(extracts) == 3                   # a confirmed paywall is not sent to Tavily


def test_budget_stop_is_not_held_against_the_source(monkeypatch):
    from owis.modules.news.processing.search_budget import SearchBudgetExceeded
    def over(url):
        raise SearchBudgetExceeded("used up")
    monkeypatch.setattr(fulltext, "extract", over)
    fulltext.fetch_fulltext("Renews", "https://renews.example/a", lambda url: ("blocked", "", url))
    assert fulltext.summary()[0]["extract_attempts"] is None


def test_counts_are_halved_so_recent_results_weigh_more():
    for _ in range(fulltext.HALVE_AT):
        fulltext.record("Source", "direct", "open", True)
    row = fulltext.summary()[0]
    assert row["direct_attempts"] == fulltext.HALVE_AT // 2 and row["direct_successes"] == fulltext.HALVE_AT // 2


def test_article_body_drops_menus_links_and_images():
    markdown = ("[Close Menu](#) ![logo](https://x/logo.png)\n# Headline\n"
                "Share [LinkedIn](https://www.linkedin.com/shareArticle?mini=true&url=https%3A%2F%2Fexample.org%2Fa-long-link)\n"
                + "The Norwegian government has improved terms for developers in its support package for the floating wind site. " * 2 + "\n"
                "* [Related story with a long title that is only a link in the sidebar of the page](https://x/y)\n")
    body = fulltext._article_body(markdown)
    assert body.startswith("The Norwegian government") and "Share" not in body and "Related" not in body


@pytest.mark.parametrize("url,expected", [
    ("https://energyglobal.com/other-renewables/", False),
    ("https://energyglobal.com/energy-storage/", False),
    ("https://energyglobal.com/magazine/energy-global/", False),
    ("https://example.com/privacy-policy/", False),
    ("https://energyglobal.com/wind/13102026/kongsberg-maritime-secures-contract-with-integrated-wind-solutions/", True),
    ("https://www.renews.biz/offshore-wind/norway-improves-floating-subsidy-package/", True),
])
def test_section_pages_are_not_articles(url, expected):
    assert is_probable_article_url(url) is expected


def test_shelf_electrification_and_ccs_count_as_relevant():
    assert topics_for("Ingen landstrøm til Aker BPs CO2-lager på sokkelen")
    assert topics_for("Orbital wins EU approval for tidal array")
