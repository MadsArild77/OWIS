# 004 – Hent inn politikk- og regelverkskildene (RSS og HTML-lister)

> Kan gjøres når som helst. Kolliderer med 001 bare i `news.html`. Gjør du den etter 002 (oppdelingen), legg JavaScript i riktig `news-*.js`-fil.

## Mål
Kildene i Settings → Regulatory hentes faktisk inn. Under **Policy & regulation** ser Mads nye høringer, dokumenter, vedtak og kalenderhendelser fra Norge, EU, UK, Danmark, Tyskland og Nederland, filtrert på havvind og energi. Morgenrapporten tar med det som er nytt.

## Hvorfor
Registeret (trinn 1, D04) kan lagre kilder med innholdstypene `regulation`, `consultation` og `calendar`, men ingenting henter dem. Bare `news`-kilder går inn i nyhetsstrømmen. Claude har testet 44 kilder og laget en importfil, se [POLICY_SOURCES.md](../POLICY_SOURCES.md). Dette kortet gjør dem levende for RSS/Atom og HTML-lister. API-kildene kommer i 005.

## Ferdig når
- [ ] Ny modul henter alle kilder i registeret der `registry.effective(...)` er sant, `method` er `rss` eller `html_list`, og `content_types` inneholder minst én av `regulation`, `consultation`, `calendar` uten `news`.
- [ ] Hver kilde hentes høyst så ofte som `interval_minutes` sier. Innhentingen kjører i bakgrunnen ved de samme faste klokkeslettene som nyhetene (`OWI_FETCH_HOURS`), men som egen jobb. Den må ikke forsinke nyhetsinnhentingen eller tidsgrensen på 10 minutter (D21).
- [ ] Postene lagres i en ny tabell `policy_items`, én rad per normalisert URL (fjern `utm_*`-parametre og `#...`). Kolonner minst: `id`, `url` (unik), `title`, `summary`, `published_at`, `source_id`, `organisation_id`, `jurisdiction_id`, `content_type`, `first_seen_at`.
- [ ] **Temafilter:** følger kilden (eller nærmeste organisasjon oppover, når kilden har `inherit`) `all`, lagres alt. Ved `topics` lagres posten bare når tittel eller sammendrag inneholder et av temaordene, uten hensyn til store og små bokstaver. Temaordene er kildens egne, ellers nærmeste organisasjons. Poster som ikke treffer, lagres ikke.
- [ ] **Første henting** av en kilde tar bare poster publisert de siste 30 dagene. Kalenderposter og poster uten dato tas med.
- [ ] Hver kjøring per kilde logges: tidspunkt, ok/feil, antall poster lest, lagret og filtrert bort, og feilmelding.
- [ ] **Policy & regulation** får en ny seksjon øverst, **«From monitored sources»** (se Design).
- [ ] **Morgenrapporten** tar med poster fra `policy_items` med `first_seen_at` det siste døgnet (se Design).
- [ ] Registeret og nyhetsstrømmen er uendret. Ingen av disse postene havner blant nyhetene.
- [ ] `pytest owis/tests -q` er grønn, med nye tester (mocket httpx): RSS- og HTML-liste-henting, temafilter med arv fra organisasjon, `interval_minutes`, duplikat-URL fra to kilder, 30-dagersgrensen, pauset organisasjon som stopper kilden, og at en feilende kilde ikke stopper de andre.
- [ ] `POLICY_SOURCES.md` («Status»), `PROJECT_STATUS.md` og `DECISIONS.md` (ny D-post) er oppdatert.

## Design (bestemt av Claude – ikke endre)
**Seksjonen «From monitored sources»** (øverst på Policy & regulation, over dagens innhold):
- Den eksisterende regionvelgeren filtrerer også denne listen, og får tre nye valg: **Asia-Pacific**, **Americas** og **Middle East**. Kart fra jurisdiksjon: `NO` → Norway, `EU` → EU, ellers etter jurisdiksjonens `groups` i registeret: `Nordics` → Nordics, `Asia-Pacific`/`Americas`/`Middle East` → samme navn, alt annet → Europe. (De nye valgene skal også virke for dagens søkebaserte politikkdel når kort 006 er gjort; til da viser de bare denne listen.)
- Knapper for innholdstype: **All**, **Consultations**, **Regulation**, **Calendar**.
- Postene grupperes per dag (`published_at`, ellers `first_seen_at`), nyeste først, de siste 30 dagene. Høyst 100 vises, med «Show more».
- Hver rad: tittel som lenke til originalen (åpnes i ny fane), deretter en grå linje med `organisasjon · land/EU · type · klokkeslett`. Høringer får merkelappen **Consultation**, kalenderposter **Calendar**.
- Tom liste: «No new items from monitored policy sources in this period.»
- Nederst en sammenfoldet del **«Source status»**: én linje per kilde med navn, sist hentet, sist lagret og eventuell feil i rødt. Kilder som har feilet tre ganger på rad, står øverst.
- Bruk eksisterende klasser og farger fra nyhetslisten og temaet. Ingen nye farger.

**Morgenrapporten:**
- Postene fra siste døgn sendes med i AI-kallet som `monitored_policy` (tittel, organisasjon, jurisdiksjon, type, dato). Høyst 40. Poster fra kilder som følger `all` sorteres først.
- Legg til én setning i prompten: brief-ens `policy`-punkter skal bruke disse postene når de er relevante for havvind, nett og kraftmarked.
- Rapporten får feltet `monitored_policy` med de samme postene. Rapportvisningen viser dem under politikkdelen med overskriften **«New from monitored sources»**, høyst 10, med lenke til Policy & regulation for resten.

**Henting:**
- RSS: bruk `feedparser` som i `probe.py`. Tittel, lenke, sammendrag (HTML fjernet, høyst 1 000 tegn) og publiseringstid.
- HTML-liste: bruk lenkene `probe.py` finner (med kildens `selector`). Tittel er lenketeksten. Ingen dato, så `published_at` er tom. Lenker med under 15 tegn tekst hoppes over.
- Samme User-Agent, tidsgrenser og URL-sjekker som `probe.fetch`. Ingen AI, ingen søk og ingen fulltekst i denne oppgaven.

## Filer som kan endres
- `owis/modules/policy/` (ny pakke: `collector.py`, `storage.py`, `api.py` eller tilsvarende)
- `owis/apps/api/main.py` (registrer router og bakgrunnsjobb)
- `owis/core/sources/probe.py` (bare hvis du trekker ut fetch-/parse-hjelpere til gjenbruk, uten å endre oppførselen)
- `owis/modules/news/processing/morning.py` (bare det som står under Design)
- `owis/apps/web/news.html` (eller `news-*.js`/`news.css` etter 002): bare den nye seksjonen og rapportlisten
- `owis/tests/test_policy_collector.py` (ny)
- `POLICY_SOURCES.md`, `PROJECT_STATUS.md`, `DECISIONS.md`

## Ikke rør
- `owis/core/sources/policy_sources.json` og `models.py`. Feil i en kilde rapporteres i svar-filen; Claude retter importfilen.
- Nyhetsinnhenting, poengsum, matching og `governance.py` (dagens søkebaserte politikkdel kjører videre som før).
- eInnsyn- og Storting-modulene (D24–D27).

## Tips
- `owis/core/sources/registry.py`: `snapshot()`, `effective()`. `owis/core/sources/probe.py`: `fetch()` og parsing i `preview()`.
- `owis/modules/news/processing/fetch_scheduler.py` viser hvordan faste klokkeslett og «claim» mot doble kjøringer gjøres.
- `owis/modules/einnsyn/public_sources.py` har et lignende mønster for egen tabell og kjøringslogg (`_ensure_tables`, `_record_run`).
- Mads importerer `policy_sources.json` selv i Settings → Regulatory → Import. Lokalt kan du teste med en kopi i en egen database.

## Utenfor oppgaven
- API-kildene (Stortinget, Have your say, Folketinget, Tweede Kamer): oppgave 005.
- AI-oppsummering, frister og datoer som leses ut av teksten, og kobling til nyhetssaker eller eInnsyn.
- Adaptere for de pausede JavaScript-sidene (NVE, Statnett, Havtil, KEFM, Energistyrelsen, KGG).
