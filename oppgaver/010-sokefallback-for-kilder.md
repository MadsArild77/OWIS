# 010 – Søke-fallback for kilder som ikke kan hentes

> Uavhengig av 009. Bygger på innhentingen i `collectors/` og helsestatusen i `fetch_process.py`.

## Mål
Når en kilde feiler (rød) eller gir 0 saker, henter appen likevel kildens ferske saker via Bing News sitt RSS-søk på domenet. Mads ser sakene på nyhetssiden som før, med kildens eget navn, og ser i kildelisten at fallback er brukt.

## Hvorfor
Flere viktige kilder kan ikke hentes direkte, fordi de blokkerer automatiske lesere, ikke har RSS eller har en forside med gamle saker: Reuters (HTTP 401), Energy Voice (HTTP 403), Rivieramm (ingen RSS, forsiden viser saker fra 2020) og tidvis Clean Technica. Claude testet dette 19. november 2026 med vanlig User-Agent:

- `https://www.bing.com/news/search?q=site%3arivieramm.com+offshore+wind&qft=sortbydate%3d%221%22&format=rss` ga 11 saker fra 16.–18. november, blant annet «Commission approves state support for Dutch offshore windfarms».
- Samme søk for `reuters.com` ga 12 saker fra 9.–18. november, blant annet «Vestas boss calls for tougher EU rules on Chinese software in wind sector».
- Bing legger den ekte artikkeladressen i parameteren `url=` i lenken. Det gjør at sammenslåing og fulltekst fungerer som for andre saker.
- Google News ble vurdert og valgt bort: lenkene er kodet (`news.google.com/rss/articles/CBMi…`) og kan ikke følges uten nettleser.

## Ferdig når
- [ ] Ny modul `owis/modules/news/collectors/search_fallback.py` med `fetch_fallback_items(source, now) -> tuple[list[dict], str | None]`:
  - Bygger adressen `https://www.bing.com/news/search?q=<spørring>&qft=sortbydate%3d%221%22&format=rss`. Spørringen er `site:<domene>` pluss kildens søkeord (se under), URL-kodet. Domenet hentes fra `homepage`, ellers fra `url`, uten `www.`.
  - Én forespørsel per kilde per henting. Bruk `get_with_retry` og samme `USER_AGENT` og timeout som `rss_fetcher._parse_feed`. Ingen falsk nettleser-User-Agent.
  - Leser feeden med `feedparser`. For hver sak: den ekte adressen hentes fra `url=` i lenken (`parse_qs`). Mangler den, brukes lenken som den er. Saker der adressen ikke ligger på kildens domene (eller et underdomene av det), hoppes over.
  - Hver sak går gjennom `is_probable_news_item` og lages med samme felter som i `rss_fetcher` (`source_name` = kildens navn, `title_raw`, `summary_raw` = Bings utdrag, `content_raw` = utdraget, `published_at` fra `pubDate`, `content_hash`, `image_url` tom, `fetched_at`).
  - Høyst 15 saker per kilde.
  - Returnerer `(saker, feilmelding)`. Kaster aldri unntak videre.
- [ ] `rss_fetcher.fetch_rss_items_with_report` og `scrape_fetcher.fetch_scrape_items_with_report`: når en kilde ender med feil **eller** 0 saker, og fallback er slått på, kalles `fetch_fallback_items`. Gir den saker, legges de til, og rapportraden får `items` = antall fallback-saker, `fallback: "bing_news"`, `status: "ok"` og den opprinnelige feilen i `detail`, for eksempel `"Primary fetch failed (http_403); used Bing News fallback"`. Gir den ingen saker, beholdes den opprinnelige raden uendret.
- [ ] Helsestatus i `fetch_process.py`: en rad med `fallback` får alltid **yellow**, med årsaken `search_fallback`. En kilde som henter normalt, påvirkes ikke.
- [ ] Ny valgfri innstilling per kilde, `fallback_query` (tekst). Tom betyr standard: `offshore wind`. Verdien `-` betyr bare `site:<domene>`, uten søkeord. Lagres som de andre feltene i `update_source`.
- [ ] I «Edit source» i Settings: nytt felt med etiketten **Fallback search** og hjelpeteksten: «Used when the source cannot be fetched. Leave empty for "offshore wind". Enter - to search the whole site.»
- [ ] I kildelisten: kolonnen Health viser gul prikk som i dag. I Error log/source history vises fallback-hentinger som `fetch · Fallback: Bing News · Treff: N`.
- [ ] Ny miljøvariabel `OWI_NEWS_SEARCH_FALLBACK` i `settings.py`, standard `false`, og oppført i `owis/.env.example` med en kort kommentar. Når den er `false`, skjer ingenting nytt.
- [ ] Fallback bruker **ikke** søkebudsjettet (Tavily/Brave, D17). Bing News RSS er gratis og telles ikke.
- [ ] Tester i `owis/tests/test_search_fallback.py` (all nettverkstrafikk mockes):
  - Bing-RSS med tre saker: den ekte adressen hentes fra `url=`. En sak fra et annet domene hoppes over.
  - En RSS-kilde som får HTTP 403 med fallback på: sakene kommer med kildens navn, og rapportraden har `fallback` og status `ok`.
  - Samme kilde med fallback av: oppførselen er som før (feil, 0 saker, ingen Bing-forespørsel).
  - En kilde som henter normalt: ingen Bing-forespørsel.
  - `fallback_query` tom gir `site:x.com offshore wind`, og `-` gir bare `site:x.com`.
  - Helsestatus blir yellow med årsaken `search_fallback`.
- [ ] `pytest owis/tests -q` er grønn.
- [ ] `DECISIONS.md` (ny D) og `PROJECT_STATUS.md` er oppdatert. `SOURCE_CONFIGURATION.md` forklarer Fallback search.

## Design (bestemt av Claude – ikke endre)
- Bare Bing News RSS. Ikke Google News, og ikke Tavily/Brave til dette.
- Fallback brukes bare for kilder som er slått på (`enabled` og `_collection_enabled`). Kilder som er slått av, røres ikke.
- Ingen omgåelse av sperrer: vanlig User-Agent, og vi henter ikke kildens egne sider oftere enn i dag. Fulltekst for fallback-saker går gjennom den vanlige løypen i `content.py`. Blokkerer kilden, blir saken stående med utdrag og kan få åpent alternativ som før.
- Tekster i appen på engelsk og ordrett som over.

## Filer som kan endres
- `owis/modules/news/collectors/search_fallback.py` (ny)
- `owis/modules/news/collectors/rss_fetcher.py`, `owis/modules/news/collectors/scrape_fetcher.py` (bare kallet til fallback og rapportraden)
- `owis/modules/news/processing/fetch_process.py` (bare helsefargen)
- `owis/modules/news/registry/source_discovery.py` (bare `fallback_query` i `update_source`)
- `owis/modules/news/presentation/api.py` (bare hvis `fallback_query` må inn i modellen for oppdatering)
- `owis/apps/web/news-settings.js`, `owis/apps/web/news.html` (bare det nye feltet i Edit source)
- `owis/core/config/settings.py`, `owis/.env.example`
- `owis/tests/test_search_fallback.py` (ny)
- `DECISIONS.md`, `PROJECT_STATUS.md`, `SOURCE_CONFIGURATION.md`

## Ikke rør
- `content.py`, `search_budget.py`, `signal.py`.
- Politikkdelen (`governance.py`, `policy_sources.json`).
- `theme.css` og utseendet ellers.
- Ingen nye avhengigheter (`feedparser` og `httpx` finnes fra før).

## Tips
- `_parse_feed` i `rss_fetcher.py` viser hvordan en feed hentes og leses. `_normalized_published_at` kan brukes for datoen.
- `source_events.record_attempts` lagrer rapportradene. `detail` brukes allerede som melding når `error` mangler.
- Datofilteret i `fetch_process.py` (`days_back`) fjerner gamle Bing-treff. Det trengs ikke et eget filter.

## Utenfor oppgaven
- Fallback for politikkilder.
- Fordeling av research-søk etter viktighet (kommer i eget kort).
- Automatisk bytte av kildetype eller adresse.
