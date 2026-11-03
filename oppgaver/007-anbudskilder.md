# 007 – Anbudskilder: TED, Doffin, Verdensbanken, Storbritannia og Canada

> Uavhengig av de andre kortene. Gjøres før 008 (nytt grensesnitt), som viser det dette kortet henter.

## Mål
Opportunities henter havvindrelevante anbud fra TED (EU/EØS), Doffin (Norge), Verdensbanken, Find a Tender og Contracts Finder (Storbritannia) og CanadaBuys. Hver kilde har synlig status, så Mads ser om den virker.

## Hvorfor
Claude testet anbudskildene 3. november 2026:
- **TED** (`api.ted.europa.eu/v3/notices/search`) virker uten nøkkel.
- **Verdensbanken** virker ikke i dag. Adressen i koden (`/api/v2/procurementnotices`) gir 404. Riktig adresse er `https://search.worldbank.org/api/v2/procnotices` (svarer med `procnotices`-liste og `total`).
- **Doffin:** den offentlige API-en i koden (`betaapi.doffin.no/public/v2/search`) svarer nå `401 missing subscription key`. Søket som doffin.no selv bruker, krever ingen nøkkel og er avklart for lesing: `POST https://api.doffin.no/webclient/api/v2/search-api/search` med JSON `{"numHitsPerPage": 3, "page": 1, "searchString": "havvind", "sortBy": "RELEVANCE", "facets": {}}`. Testet 3. november: svarer `numHitsTotal` og `hits[]` med `id`, `buyer[]`, `heading`, `description` m.m.
- **Find a Tender** (`https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages`) og **Contracts Finder** (`https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search`) er åpne OCDS-API-er. Storbritannia er ikke i TED etter Brexit (D23).
- **CanadaBuys** publiserer åpne anbud som CSV: `https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv`.
- Ikke med: SAM.gov (USA) krever API-nøkkel, ADB svarer med Cloudflare, AusTender har bare tildelte kontrakter, og UNGM har ikke åpent API.

## Ferdig når
- [ ] **Verdensbanken** bruker `/api/v2/procnotices` med de parametrene endepunktet faktisk støtter (undersøk et ekte svar), og gir treff igjen.
- [ ] **Doffin** bruker søket på `https://api.doffin.no/webclient/api/v2/search-api/search` (POST, JSON, ingen nøkkel) i stedet for `betaapi.doffin.no`. Undersøk et ekte svar og et søk uten `searchString` for å finne felt for kunngjøringstype, publiseringsdato, frist og CPV, og hvordan man filtrerer på dato og type. Behold dagens filter på relevante typer (`RELEVANT_DOFFIN_TYPES`). Lenke til kunngjøringen: `https://doffin.no/notices/<id>`. Beskriv i svar-filen hvilke parametre du bruker.
- [ ] **Find a Tender** og **Contracts Finder:** nye hentere som leser OCDS-releases siden forrige kjøring (første gang: `OPPORTUNITIES_DAYS_BACK`). Bare åpne konkurranser (`tender`-del med status `active` / `planned`, og planlagte/forhåndsmeldte). Felter: id (`ocid`), tittel, beskrivelse, oppdragsgiver, land `GBR`, CPV-koder, frist (`tender.tenderPeriod.endDate`), anslått verdi og valuta, lenke til kunngjøringen. Samme notis i begge kilder (samme `ocid`) lagres én gang.
- [ ] **CanadaBuys:** henter CSV-filen, tar bare rader publisert siden forrige kjøring (første gang `OPPORTUNITIES_DAYS_BACK`), engelske felt, land `CAN`.
- [ ] Alle nye kilder går gjennom eksisterende normalisering, `process_raw_item` og profiler. De er med i `OWI_OPP_ENABLED_SOURCES` som `UK_FTS`, `UK_CF` og `CANADABUYS` (standard: `TED,DOFFIN,WORLDBANK,UK_FTS,UK_CF,CANADABUYS`).
- [ ] **Ny profil** i `profiles.yaml`: `company: OWIS`, `name: Offshore wind market`, kategori `Offshore Wind`. Den fanger alle havvindanbud for markedsinnsikt. Nøkkelord: `offshore wind`, `floating wind`, `wind farm`, `havvind`, `havvindpark`, `éolien en mer`, `éolien flottant`, `Windenergie auf See`, `Offshore-Windpark`, `eólica marina`, `havmølle`, `havsbaserad vindkraft`, `offshore substation`, `export cable`, `inter-array cable`, `seabed lease`. Negative: `onshore`, `land-based`, `school`, `hospital`. Kvalifikatorer kan stå tomme hvis loaderen tillater det; ellers `offshore`, `wind`.
- [ ] **Kildestatus:** hver kjøring per kilde lagres (tid, ok/feil, antall hentet, nye, filtrert bort). `GET /api/opportunities/sources` returnerer siste status per kilde.
- [ ] `PRIMARY_MARKETS` i `pipeline.py` får `FRA`, `POL`, `DEU` og `NLD` som sekundære hvis de ikke står der, og `GBR` beholdes som primær. Ingen andre endringer i poenglogikken.
- [ ] `pytest owis/tests -q` er grønn. Nye tester bruker lagrede eksempelsvar (fixtures hentet én gang, uten personopplysninger): Verdensbanken (ny adresse), Doffin (nytt søk), Find a Tender, Contracts Finder, CanadaBuys, og duplikat-`ocid` på tvers av UK-kildene.
- [ ] `owis/.env.example`, `owis/README.md` (Opportunities-delen) og `PROJECT_STATUS.md` er oppdatert. Ny D-post i `DECISIONS.md`: Opportunities samles i OWIS, med disse kildene.

## Design (bestemt av Claude – ikke endre)
- Statusteksten per kilde er en av: `OK`, `Failed: <kort grunn>`, `Not run yet`.
- Kildenavn som vises: `TED (EU/EEA)`, `Doffin (Norway)`, `World Bank`, `Find a Tender (UK)`, `Contracts Finder (UK)`, `CanadaBuys (Canada)`.

## Filer som kan endres
- `owis/modules/opportunities/collectors/` (rett og legg til hentere; nye filer er greit)
- `owis/modules/opportunities/processing/pipeline.py` (bare markedslisten)
- `owis/modules/opportunities/registry/profiles.yaml` (ny profil)
- `owis/modules/opportunities/storage/repository.py` og der tabellene opprettes (kjøringslogg)
- `owis/modules/opportunities/presentation/api.py` (nytt `/sources`-endepunkt; jobben kaller de nye henterne)
- `owis/core/config/settings.py`, `owis/.env.example`
- `owis/tests/test_opportunity_*.py` og `owis/tests/fixtures/opportunity_*.json|csv`
- `owis/README.md`, `PROJECT_STATUS.md`, `DECISIONS.md`

## Ikke rør
- `opportunities.html` (nytt grensesnitt kommer i 008).
- Notion-eksporten for Opportunities (`owis/core/notion/opportunities_export.py`) – den beholdes som den er.
- Nyhetsmodulen.

## Tips
- Henterne ligger i `dealengine_fetchers.py`; `fetch_dealengine_style_notices_with_report` samler dem og gir en rapport per kilde som kan gjenbrukes til statusen.
- OCDS: hver release har `ocid`, `tender`, `buyer`, `parties`. Find a Tender bruker `cursor`/`links.next` for neste side.

## Utenfor oppgaven
- SAM.gov, ADB, EBRD, AusTender og UNGM.
- AI-oppsummering eller ny poengmodell.
