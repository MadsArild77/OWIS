from owis.core.storage import db
from owis.modules.news.collectors.scrape_fetcher import is_junk_link
from owis.modules.news.presentation.api import _filter_domain
from owis.modules.news.processing import rescore, signal, taxonomy


def test_offshore_wind_ranks_above_related_and_other_energy():
    offshore, focus, reasons = signal.score_signal(
        "Equinor awards export cable contract for 1.5 GW Norwegian offshore wind farm",
        "The contract covers the export cable and offshore substation for the project in the North Sea.",
        ["Norway"], ["Equinor", "NKT"], "Recharge", {"basis": "fulltext", "access": "open"})
    related, related_focus, _ = signal.score_signal(
        "Statnett plans new interconnector as power prices rise", "Grid capacity and power prices in southern Norway.",
        ["Norway"], ["Statnett"], "Europower", {"basis": "feed_excerpt"})
    other, other_focus, _ = signal.score_signal(
        "EV sales surged in September", "Electric vehicle sales and charging stations grew in the US.",
        ["USA"], [], "Clean Technica", {"basis": "feed_excerpt"})
    assert (focus.bucket, related_focus.bucket, other_focus.bucket) == ("offshore_wind", "adjacent_energy", "other_energy")
    assert offshore > related > other
    assert offshore >= 80 and other < 40
    assert reasons[:2] == ["Offshore wind", "Contract or order"] and "Norway" in reasons
    assert signal.is_linkedin_candidate(offshore, focus) and not signal.is_linkedin_candidate(other, other_focus)


def test_keywords_match_whole_words_only():
    assert signal.classify_focus("annual report on support measures").bucket == "other_energy"
    assert signal.classify_focus("new port for offshore wind installation").bucket == "offshore_wind"
    assert signal.classify_focus("Havvindprosjektet får støtte").bucket == "offshore_wind"


def test_taxonomy_merges_aliases():
    assert taxonomy.normalize_geographies(["global", "United Kingdom", "uk", "United States"]) == ["UK", "USA"]
    assert taxonomy.normalize_geographies(["global"]) == ["Global"]
    assert taxonomy.normalize_actors(["Orsted", "Ørsted", "Equinor ASA", "RWE AG"]) == ["Ørsted", "Equinor", "RWE"]
    assert taxonomy.normalize_themes(["Offshore Wind", "Renewable Energy"]) == ["offshore_wind", "renewables"]
    assert taxonomy.extract_actors("Shareholders met Ørsted; BP and NVE agreed") == ["Ørsted", "BP", "NVE"]


def test_norwegian_story_without_country_defaults_to_norway():
    assert taxonomy.geographies_for("Vindkraften tapte penger i fjor",
                                    "Det er ikke bra for kraftselskapene som skal investere og bygge mer.") == ["Norway"]
    assert taxonomy.geographies_for("Dutch tender opens", "Text mentioning Norway later", ["Netherlands"]) == ["Netherlands"]


def test_junk_links_are_detected():
    assert is_junk_link("", "[email\xa0protected]")
    assert is_junk_link("https://windeurope.org/cdn-cgi/l/email-protection", "Contact")
    assert is_junk_link("https://windeurope.org/2026/09", "September 2026")
    assert not is_junk_link("https://windeurope.org/news/a", "Danish tender result")


def test_core_filter_keeps_offshore_and_related():
    items = [{"domain_bucket": b} for b in ("offshore_wind", "adjacent_energy", "other_energy")]
    assert [x["domain_bucket"] for x in _filter_domain(items, "core")] == ["offshore_wind", "adjacent_energy"]


def test_rescore_updates_stored_items_once(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "rescore.db"))
    db.init_db()
    with db.get_conn() as c:
        raw = c.execute("""INSERT INTO news_raw_items(source_name, article_url, title_raw, summary_raw,
            content_raw, content_hash, published_at, fetched_at, status) VALUES('Recharge','https://x/a','t','s','c','h',
            '2026-10-01T00:00:00Z','2026-10-01T00:00:00Z','processed')""").lastrowid
        item = c.execute("""INSERT INTO news_processed_items(raw_item_id, title, cleaned_text, summary, theme_tags,
            geography_tags, actors, why_it_matters, signal_score, confidence, linkedin_angle, linkedin_candidate, processed_at)
            VALUES(?, 'Orsted wins offshore wind auction in Denmark', 'The Danish offshore wind tender was awarded.', 's',
            'Offshore Wind', 'global,Denmark', 'Orsted', 'w', 99, 0.7, 'a', 1, '2026-10-01T00:00:00Z')""", (raw,)).lastrowid
    assert rescore.rescore_existing() == 1
    assert rescore.rescore_existing() == 0
    with db.get_conn() as c:
        row = c.execute("SELECT * FROM news_processed_items WHERE id=?", (item,)).fetchone()
        domain = c.execute("SELECT domain_bucket FROM news_domain_classification WHERE processed_id=?", (item,)).fetchone()
    assert row["geography_tags"] == "Denmark" and row["actors"] == "Ørsted" and row["theme_tags"] == "offshore_wind"
    assert 70 <= row["signal_score"] < 99 and domain["domain_bucket"] == "offshore_wind"


def test_subscriber_marker_and_search_query():
    from owis.modules.news.collectors.scrape_fetcher import is_subscriber_title
    from owis.modules.news.processing.content import _search_query
    assert is_subscriber_title("Statkraft kutter i havvind (+)")
    assert not is_subscriber_title("Statkraft (+1 %) i dag")
    assert _search_query("[Paywalled] Statkraft kutter i havvind (+)") == "Statkraft kutter i havvind"


def test_paywall_does_not_push_story_down():
    args = ("Equinor awards offshore wind contract", "Short excerpt.", ["Norway"], ["Equinor"], "Europower")
    open_score = signal.score_signal(*args, {"basis": "fulltext"})[0]
    paywalled = signal.score_signal(*args, {"basis": "feed_excerpt", "access": "restricted"})[0]
    assert open_score - paywalled <= 4


def test_alternative_search_uses_configured_provider(monkeypatch):
    from owis.modules.news.processing import content, research
    from owis.modules.news.matching import service
    monkeypatch.setattr(service, "build_candidate_pairs", lambda rows, **kw: [])
    monkeypatch.setenv("TAVILY_API_KEY", "test")
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    queries, fetched = [], []
    monkeypatch.setattr(research, "search", lambda q: queries.append(q) or [{"url": "https://open.example/a", "title": "t"}])
    monkeypatch.setattr(content, "fetch_public", lambda url: fetched.append(url) or ("restricted", "", url))
    monkeypatch.setattr(content, "get_conn", _empty_conn)
    raw = {"id": 1, "title_raw": "Ørsted wins tender (+)", "article_url": "https://paywalled.example/a", "summary_raw": ""}
    assert content.alternative_sources(raw, ai=None) == []
    assert queries == ["Ørsted wins tender"] and fetched == ["https://open.example/a"]


class _EmptyRows:
    def execute(self, *a):
        return self

    def __iter__(self):
        return iter([])


from contextlib import contextmanager


@contextmanager
def _empty_conn():
    yield _EmptyRows()
