from owis.modules.news.collectors import scrape_fetcher


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")


class _FakeClient:
    def __init__(self, pages: dict[str, _FakeResponse], **kwargs):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str) -> _FakeResponse:
        if url not in self.pages:
            raise AssertionError(f"Unexpected URL {url}")
        return self.pages[url]


def test_fetch_scrape_items_uses_metadata_and_json_ld(monkeypatch):
    monkeypatch.setattr(
        scrape_fetcher,
        "load_source_registry",
        lambda: [
            {
                "name": "TestScrape",
                "type": "scrape",
                "homepage": "https://example.com",
                "enabled": True,
            }
        ],
    )
    monkeypatch.setattr(scrape_fetcher, "is_probable_article_url", lambda url: "article-1" in url)
    monkeypatch.setattr(scrape_fetcher, "is_probable_news_item", lambda **kwargs: True)

    pages = {
        "https://example.com": _FakeResponse(
            """
            <html><body>
              <a href="/article-1">Short anchor title</a>
            </body></html>
            """
        ),
        "https://example.com/article-1": _FakeResponse(
            """
            <html>
              <head>
                <meta property="og:title" content="Expanded Offshore Wind Title" />
                <meta property="og:description" content="A detailed offshore wind policy update." />
                <script type="application/ld+json">
                  {"headline":"Ignored fallback","datePublished":"2026-05-11T08:30:00+02:00"}
                </script>
              </head>
              <body>
                <article>
                  <p>This is a long enough paragraph to be treated as article content and not just navigation text for the parser.</p>
                  <p>This second paragraph adds more context about procurement, policy and market implications for offshore wind.</p>
                </article>
              </body>
            </html>
            """
        ),
    }
    monkeypatch.setattr(scrape_fetcher.httpx, "Client", lambda **kwargs: _FakeClient(pages, **kwargs))

    items = scrape_fetcher.fetch_scrape_items(limit_per_source=5)

    assert len(items) == 1
    assert items[0]["title_raw"] == "Expanded Offshore Wind Title"
    assert items[0]["summary_raw"] == "A detailed offshore wind policy update."
    assert items[0]["published_at"] == "2026-05-11T06:30:00+00:00"
    assert "procurement" in items[0]["content_raw"].lower()


def test_extract_article_metadata_uses_custom_published_fallback():
    html = """
    <html>
      <body>
        <div>Først publisert: 12.05.2026</div>
        <article>
          <p>This article body is sufficiently long to produce a fallback summary without standard metadata present anywhere else on the page.</p>
        </article>
      </body>
    </html>
    """

    metadata = scrape_fetcher._extract_article_metadata(
        html,
        "https://www.uib.no/nt/174013/staker-ut-kursen-norsk-havvindsatsing",
        anchor_title="Fallback title",
    )

    assert metadata["title"] == "Fallback title"
    assert metadata["published_at"] == "2026-05-12"
    assert "fallback summary" in str(metadata["description"]).lower()


def test_extract_paragraphs_skips_publisher_boilerplate():
    soup = scrape_fetcher.BeautifulSoup(
        """
        <html>
          <body>
            <article>
              <p>This article paragraph contains the relevant offshore wind content and should remain visible in previews.</p>
              <p>EnergiWatch arbeider etter Vær Varsom-plakatens regler for god presseskikk. Redaktørplakaten. Prøv EnergiWatch gratis eller få tilbud på et abonnement tilpasset deg eller din virksomhet. Copyright © EnergiWatch.</p>
            </article>
          </body>
        </html>
        """,
        "html.parser",
    )

    paragraphs = scrape_fetcher._extract_paragraphs(soup)

    assert len(paragraphs) == 1
    assert "offshore wind content" in paragraphs[0].lower()


def test_extract_paragraphs_skips_subscription_alert_boilerplate():
    soup = scrape_fetcher.BeautifulSoup(
        """
        <html>
          <body>
            <article>
              <p>Relevant article context about offshore wind permitting, timing and industrial consequences should remain visible.</p>
              <p>Varsler er en tjeneste for våre abonnenter. Vennligst logg inn eller opprett bruker for å kunne bruke varsler.</p>
            </article>
          </body>
        </html>
        """,
        "html.parser",
    )

    paragraphs = scrape_fetcher._extract_paragraphs(soup)

    assert len(paragraphs) == 1
    assert "offshore wind permitting" in paragraphs[0].lower()


def test_extract_paragraphs_skips_newsletter_job_and_debate_disclaimer_boilerplate():
    soup = scrape_fetcher.BeautifulSoup(
        """
        <html>
          <body>
            <article>
              <p>Relevant article context about floating wind auctions and supply-chain positioning should remain visible.</p>
              <p>Vær i forkant av utviklingen. Få informasjon om det siste fra bransjen med vårt nyhetsbrev. Jurist (rådgivar/seniorrådgivar) i seksjon for tilsyn med IT og betalingstenester Debattinnlegget er utelukkende et uttrykk for skribentens egen mening.</p>
            </article>
          </body>
        </html>
        """,
        "html.parser",
    )

    paragraphs = scrape_fetcher._extract_paragraphs(soup)

    assert len(paragraphs) == 1
    assert "floating wind auctions" in paragraphs[0].lower()
