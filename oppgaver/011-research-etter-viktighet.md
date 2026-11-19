# 011 – Research-søk fordeles etter hvor viktige sakene er

> Gjøres helst etter 009, siden prioriteringen bygger på poengsummen. Uavhengig av 010.

## Mål
De daglige søkene etter åpne versjoner av saker med bare utdrag eller betalingsmur går til de viktigste sakene, og fordeles utover dagen. Mads merker det ved at viktige saker fra Europower, Recharge og Energiwatch oftere får fulltekst via en åpen kilde, og at uviktige saker ikke bruker opp plassene.

## Hvorfor
I dag får hver sak med kort tekst (under 800 tegn) og relevans `relevant` eller `uncertain` én av 15 plasser per dag (`OWI_OPEN_SEARCHES_PER_DAY`, `_thin_search_allowed` i `content.py`). Plassene går til sakene i den rekkefølgen de blir behandlet, uansett poengsum. Systemhelsen 19. november 2026 viste:
- «Automatic searches today: 15 of 26» allerede om morgenen.
- Europower 98 % utdrag (88 % betalingsmur), Recharge 98 % utdrag, Chosun 927 saker med 100 % utdrag. Kilder med mange korte, uviktige saker konkurrerer om de samme plassene som viktige havvindsaker.
- Det er 6 planlagte hentinger per dag (`OWI_FETCH_HOURS=5,8,12,15,18,21`). Hentingen kl. 05 kan bruke opp alle plassene.

Hver plass koster mer enn et nettsøk: `alternative_sources` henter inntil tre sider og spør AI-en om sammenligning (`judge_pair`). Derfor skal antallet ikke økes, bare fordeles bedre.

## Ferdig når
- [ ] Ny funksjon `potential_score(raw) -> int` i `content.py`, flyttet ut fra `enrichment_eligible`. Den beregner poengsummen som om fulltekst fantes, og bruker høyeste av den og lagret `signal_score`. `enrichment_eligible` bruker den nye funksjonen og oppfører seg ellers som før.
- [ ] I `fetch_process.py` sorteres **nye** saker (`raws_new`) etter `potential_score`, høyest først, før behandlingen. Saker fra køen (`backlog_raws`) kommer etter, i samme rekkefølge som i dag. Viktige saker behandles da først, også når tidsgrensen (`OWI_FETCH_MAX_MINUTES`) stopper kjøringen.
- [ ] `thin_search` i `prepare` krever i tillegg at `potential_score(raw) >= OWI_OPEN_SEARCH_MIN_POTENTIAL` (standard `50`). Saker manuelt merket som interessante (`positive`) slipper alltid gjennom, som i dag.
- [ ] Nytt tak per henting: høyst `OWI_OPEN_SEARCHES_PER_RUN` (standard `3`) nye plasser for `thin_search` per kjøring av `_run_fetch_process`. Dagstaket på 15 gjelder fortsatt. Taket per kjøring gjelder ikke når Mads åpner en enkelt sak og ber om oppdatering (`item_view`, `refresh=True`).
  - Teller per kjøring: send med en enkel teller fra `fetch_process` til `prepare` (for eksempel et valgfritt argument `run_budget`). Ingen globale variabler.
- [ ] Saker som oppfyller den eksisterende regelen `eligible` (poeng ≥ `OWI_OPEN_SOURCE_MIN_SCORE` og treff på interesseområde) oppfører seg som i dag.
- [ ] Begge nye innstillinger leses i `settings.py` eller der `OWI_OPEN_SEARCHES_PER_DAY` leses i dag (bruk samme sted), med standardverdiene over. De føres opp i `owis/.env.example` rett under `OWI_OPEN_SEARCHES_PER_DAY`, med kommentarene:
  - `# Teaser stories below this potential score get no open-version search`
  - `# Open-version searches per fetch run, so later runs also get some`
- [ ] Tester (mocket AI, søk og nett), i `test_fetch_process.py` eller en ny `test_open_search_priority.py`:
  - Tre korte saker med potensial 80, 60 og 30 og plass til to: 80 og 60 får søk, 30 får ikke.
  - En sak med potensial 30 som er merket interessant, får søk.
  - Med `OWI_OPEN_SEARCHES_PER_RUN=3` og fem kvalifiserte saker: tre søk i første kjøring, og de neste i neste kjøring (innenfor dagstaket).
  - Nye saker behandles i synkende potensial-rekkefølge.
  - `enrichment_eligible` gir samme svar som før for en sak med kjent poengsum.
- [ ] `pytest owis/tests -q` er grønn.
- [ ] I svar-filen: skriv hvor mange saker som fikk søk i én testkjøring før og etter, hvis det lar seg vise med testdata.
- [ ] `DECISIONS.md` (ny D) og `PROJECT_STATUS.md` er oppdatert. `EDITORIAL.md` nevner prioriteringen kort.

## Design (bestemt av Claude – ikke endre)
- Samme dagstak (15) og samme månedsbudsjett for søk (D17). Ingen nye søk, bare bedre fordeling.
- Minstegrense 50 og 3 per kjøring er standard. Begge kan endres med miljøvariabler.
- Ingen endring i det brukeren ser i appen.

## Filer som kan endres
- `owis/modules/news/processing/content.py`
- `owis/modules/news/processing/fetch_process.py` (bare sorteringen og telleren)
- `owis/core/config/settings.py`, `owis/.env.example`
- `owis/tests/` (ny eller utvidet test)
- `DECISIONS.md`, `PROJECT_STATUS.md`, `EDITORIAL.md`

## Ikke rør
- `search_budget.py`, `signal.py`, `research.py`.
- `alternative_sources` utover det som trengs for å sende med telleren.
- Nettsiden (`owis/apps/web/`).

## Tips
- `enrichment_eligible` regner allerede ut `potential` på linjene rett før terskelen. Flytt den biten ut.
- Sorteringen kan gjøres med `sorted(raws_new, key=potential_score, reverse=True)`. Regn ut poengsummen én gang per sak og gjenbruk den, for eksempel i en ordbok med `raw['id']` som nøkkel.
- `news_open_search_attempts` har en sperre på én plass per sak per uke. Den skal beholdes.

## Utenfor oppgaven
- Å telle bare nettsøk og ikke sammenligningen med lagrede saker.
- Å øke dagstaket.
- Søke-fallback for kilder som feiler (kort 010).
