# 008 – Opportunities i samme design som News og eInnsyn

> Gjøres etter 007, som henter kildene og lager `/api/opportunities/sources`.

## Mål
`/opportunities` ser ut og virker som News og eInnsyn: samme sidemeny og toppfelt, filtre som knapper, en liste og et lesepanel. Mads ser åpne havvindanbud fra hele verden, sortert etter frist. Han kan lagre dem og skjule det som ikke er relevant.

## Hvorfor
Dagens side (`owis/apps/web/opportunities.html`) er den gamle «DealEngine Bridge». Den har et kjøreskjema med tekstfelt for kilder og profiler, tre kortrutenett og Notion-knapper, og ligner ikke resten av appen. Etter 007 kommer anbud fra seks kilder i mange land, og da trengs filtrering og frister.

## Ferdig når
- [ ] Siden bruker samme ramme som `/einnsyn`: samme sidemeny med samme lenker (Opportunities aktiv), toppfelt, temabryter og samme CSS-klasser. Følg `einnsyn.html`, som kopierte rammen fra News.
- [ ] Sidemenyen har en ny gruppe **«Tenders»** under «Opportunities» med visningene **Open** (antall), **Closing soon** (frist innen 14 dager, antall), **New this week**, **Saved** og **Hidden**.
- [ ] **Toppfeltet** har søk (`/`), knappen **«Fetch tenders»** (starter dagens hent-og-behandle-jobb med standardinnstillinger og viser framdrift som Fetch på News) og temabryteren.
- [ ] **Filtre under toppfeltet**, som knapper/nedtrekk i samme stil som emnefilteret på News:
  - Profil: én knapp per profil fra `profiles.yaml` (**Offshore wind market**, **Marine Survey & Geoscience**, **Strategy & Advisory** …), flervalg.
  - Region: **All regions**, **Norway**, **Nordics**, **UK**, **Europe**, **Americas**, **Asia-Pacific**, **Middle East & Africa**, ut fra landkoden.
  - Kilde: nedtrekk med kildenavnene fra 007.
  - Fit: **High**, **Medium**, **Low** (fra `strategic_fit`).
  - Filtrene står i adressen (`?profile=…&region=…`), slik at visningen kan deles, som på eInnsyn.
- [ ] **Listen:** én rad per anbud. Venstre: tittel, deretter en grå linje `oppdragsgiver · land · kilde · publisert`. Høyre: fristmerke og fit-merke. «Open» og «Closing soon» sorteres etter frist (nærmeste først; uten frist sist). «New this week» sorteres etter publisering.
- [ ] **Fristmerket:** `Closes today`, `Closes in 3 days`, `Closes 14 Nov` (over 7 dager), `No deadline`. Innen 7 dager med varselfargen temaet allerede har. Utløpte anbud vises ikke i Open/Closing soon/New, men finnes i Saved hvis de er lagret.
- [ ] **Lesepanelet** åpnes fra høyre som på News: tittel, merker (kilde, land, fit, profil), **Deadline** og **Estimated value** (hvis kjent), oppdragsgiver, sammendrag, «Why it matters», treff på nøkkelord og tjenester, CPV-koder, og knappen **«Open original notice»** (ny fane).
- [ ] **Handlinger i panelet:** **Save** / **Saved**, **Not relevant** (skjuler anbudet og legger det i Hidden; kan angres med **Restore**) og **Copy info** (tittel, oppdragsgiver, land, frist, verdi, lenke og sammendrag som ren tekst, som Copy info på News).
- [ ] Hurtigtaster som på News: `/` søk, `j`/`k` neste/forrige, `Esc` lukk panelet, `s` lagre.
- [ ] **Settings → Opportunities** (ny fane ved siden av News og Regulatory i Settings på `/news`, eller en egen seksjon nederst på `/opportunities` – velg det som passer best med eksisterende kode og begrunn det i svar-filen) viser kildestatus fra `/api/opportunities/sources`, profilene (lesbart, ikke redigerbart) og avanserte valg fra det gamle skjemaet: dager tilbake, kilder og profiler for en manuell kjøring. Notion-eksporten beholdes der, uendret, under overskriften **«Notion export»**.
- [ ] Lagret/skjult lagres i databasen (ny tabell eller kolonne), ikke i nettleseren. API: `POST /api/opportunities/item/{id}/state` med `saved` / `hidden` / `none`.
- [ ] Listen henter fra et nytt endepunkt `GET /api/opportunities/list` med filtrene over, `view`, `q` og `limit` (standard 100), og et felt med antall per visning til sidemenyen.
- [ ] Tom liste: «No open tenders match these filters.» Uten noen data: «No tenders fetched yet. Use Fetch tenders.»
- [ ] Lyst og mørkt tema, kontrast som resten av appen, og ingen sidelengs rulling på mobilbredde.
- [ ] Nettlesersjekk med testdata: alle visninger, filtre, søk, lesepanel, lagre/skjule/angre, Copy info, Fetch tenders, tema og mobil. Skriv hva som ble sjekket i svar-filen.
- [ ] `pytest owis/tests -q` er grønn, med tester for `/list` (filtre, visninger, frist-sortering, utløpte skjult) og `/state`.

## Design (bestemt av Claude – ikke endre)
- All tekst i appen på engelsk, nøyaktig som i punktene over.
- Ingen nye farger eller fonter. Fit-merket bruker de samme merkefargene som emne-/kildemerker på News (High sterkest).
- Landkode → region: `NOR` → Norway; `SWE`, `DNK`, `FIN`, `ISL` → Nordics; `GBR` → UK; øvrige europeiske land og EU-institusjoner → Europe; Nord- og Sør-Amerika → Americas; Asia og Oseania → Asia-Pacific; Midtøsten og Afrika → Middle East & Africa. Ukjent land → kun under All regions.
- Verdi vises med valuta og avrundet: `GBP 12.5m`, `NOK 300k`.

## Filer som kan endres
- `owis/apps/web/opportunities.html` (skrives om)
- `owis/modules/opportunities/presentation/api.py` og `storage/repository.py`
- `owis/apps/web/news.html` eller riktig `news-*.js` (bare hvis du legger Opportunities-fanen i Settings der)
- `owis/tests/test_opportunity_*.py`
- `PROJECT_STATUS.md`, `DECISIONS.md` (oppdater D-posten fra 007)

## Ikke rør
- `theme.css`, `theme.js`, `einnsyn.html` og selve nyhetssiden utover en eventuell Settings-fane.
- Hentere og poenglogikk fra 007.
- Notion-eksporten (bare flytt knappene, ikke endre oppførselen).

## Tips
- `einnsyn.html` er det beste forbildet for ramme, filterknapper i adressen og lesepanel.
- Feltene per anbud kommer fra `process_raw_item` i `processing/pipeline.py` (`deadline`, `strategic_fit`, `profile_name`, `matched_services`, `why_it_matters` …).

## Utenfor oppgaven
- Å trekke ut felles CSS for News, eInnsyn og Opportunities i én fil. Det blir et eget kort.
- Varsler og e-post om nye anbud.
- Kobling mellom anbud og nyhetssaker.
