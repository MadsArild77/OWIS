# 003 – Flytt logikk ut av nyhets-API-et

> Gjøres etter at 001 er slått sammen, siden den også endrer `api.py`. Kan gjøres samtidig med 002 (ulike filer).

## Mål
`owis/modules/news/presentation/api.py` blir et tynt API-lag: forespørselsmodeller og endepunkter som kaller funksjoner i `processing/` og `storage/`. Ingen endring i hva API-et svarer.

## Hvorfor
Filen er på ~1 650 linjer og inneholder jobbkjøring, bygging av saker og samlinger, matching med automatisk sammenslåing, oppgaver etter innhenting og hjelpere for relevans. Jobber som kjøres av planleggeren (`run_*_after_fetch`) bor dermed i presentasjonslaget. Det gjør endringer risikable og tester vanskelige.

## Ferdig når
- [ ] Logikken er flyttet til moduler under `owis/modules/news/processing/` (eller `storage/` der det bare er databasekall), gruppert slik:
  - **jobber** (`_create_job`, `_run_job`, `_job_snapshot`, `_update_job` og kildeframdrift) → `processing/jobs.py`
  - **samlinger og saker** (`_build_collections`, `_synthesize_collection_master`, `_cased_collections`, nøkkel- og opptellingshjelpere) → `processing/collections.py`
  - **matching** (`_run_match_review`, `_auto_merge_threshold`) og `run_*_after_fetch` → `processing/match_review.py` og `processing/after_fetch.py`
  - **relevans- og domenehjelpere** (`_attach_*`, `_filter_domain`, `_relevance_status` m.fl.) → `processing/item_view.py`
- [ ] `api.py` inneholder bare Pydantic-modeller, endepunkter og korte kall videre. Målet er under 600 linjer; skriv i svar-filen hva som eventuelt står igjen og hvorfor.
- [ ] Alle steder som importerer fra `api.py` (planleggere, jobber, tester) importerer fra den nye modulen. Ingen sirkulære importer.
- [ ] Svarene fra alle endepunkter er uendret. Testene som finnes i dag består uten at forventningene endres – bare importstier kan justeres.
- [ ] `pytest owis/tests -q` er grønn.

## Design (bestemt av Claude – ikke endre)
- Ren flytting. Funksjonene beholder navn (fjern gjerne den innledende `_` når de blir offentlige i ny modul) og oppførsel.
- Ingen endring i URL-er, felt i svarene, terskler eller databaseskjema.
- Ingen nye avhengigheter.

## Filer som kan endres
- `owis/modules/news/presentation/api.py`
- Nye filer under `owis/modules/news/processing/`
- Filer som importerer fra `api.py`: `owis/apps/api/main.py`, `owis/modules/news/processing/fetch_scheduler.py` og testene `test_collection_recency.py`, `test_editorial.py`, `test_fetch_process.py`, `test_fetch_scheduler.py`, `test_news_matching.py`, `test_signal_scoring.py`, `test_story_research.py`, `test_threads.py` (bare importer og mock-stier)

## Ikke rør
- `owis/apps/web/` (grensesnittet).
- Poengsum, matching-prompter og terskler.
- `owis/modules/opportunities/`.

## Tips
- Start med å finne alle importer av `owis.modules.news.presentation.api` i resten av koden. Pass på `monkeypatch`/`patch`-stier i testene: når en funksjon flyttes, må mocken peke dit den nå slås opp.
- Flytt én gruppe om gangen og kjør testene mellom hver.

## Utenfor oppgaven
- Å skrive om eller forenkle logikken som flyttes.
- Å flytte Pydantic-modellene til `schemas.py`.
