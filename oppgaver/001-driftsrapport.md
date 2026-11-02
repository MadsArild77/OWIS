# 001 – Driftsrapport: virker OWIS i produksjon?

## Mål
Mads kan åpne én side i appen og se om innhenting, morgenrapport, fulltekst, poengsum og automatisk sammenslåing faktisk fungerer de siste 30 dagene – uten å lese logger. Den samme rapporten kan kjøres mot en kopi av databasen fra kommandolinjen.

## Hvorfor
D13–D22 er innført i rask rekkefølge, og flere av dem sier «må kontrolleres på produksjonsdata». Ingenting av det er målt etter 14. oktober. Før vi bygger mer vil vi vite: kom morgenrapporten hver dag, har D21 økt andelen fulltekst, skiller poengsummen fortsatt, og hvor mange saker slås sammen automatisk (D14/D20). Svarene avgjør de neste kortene.

## Ferdig når
- [ ] `GET` `.../ops-report?days=30` under nyhets-API-et (samme prefiks som `/morning-report`) gir JSON med tallene under. Endepunktet krever innlogging som resten av API-et.
- [ ] Settings → News har et nytt kort **«System health»** nederst som viser rapporten som tabeller, med knappen **«Refresh»**.
- [ ] `python -m owis.scripts.ops_report --db <sti> --days 30` skriver samme rapport som lesbar tekst (Markdown) til skjermen.
- [ ] Ingen AI-kall, ingen søk, ingen nettverk – bare lesing fra databasen.
- [ ] `pytest owis/tests -q` er grønn, med ny test som bygger en liten database med kjente rader og sjekker hvert tall.

## Design (bestemt av Claude – ikke endre)
Rapporten har disse seksjonene, i denne rekkefølgen. Overskrifter ordrett:

1. **Morning reports** – én rad per dag i perioden: dato, status (`completed` / `failed` / `missing`), ferdig kl. (Europe/Oslo, `HH:MM`), antall saker i rapporten, om AI-sammendraget ble laget (`AI` / `Fallback`). Dager uten rad er `missing`. Øverst: «X of Y days delivered by 07:00».
2. **Fetching** – per dag: antall nye artikler lagret. Under: kilder som ikke har levert en artikkel på 7 dager, med navn og siste artikkeldato.
3. **Full text** – per uke (mandag–søndag): antall artikler, andel med fulltekst, andel med bare ingress, andel bak betalingsmur. Bruk samme skille mellom fulltekst og ingress som D21-koden allerede bruker; finn det, ikke lag en ny regel. Deretter en tabell per kilde for hele perioden, sortert etter lavest fulltekstandel.
4. **Scores** – fordeling av poengsum for artikler i perioden i bøttene `0–39`, `40–55`, `56–69`, `70–84`, `85–100`, både for alle og for «Offshore wind & related». Pluss andel offshore wind av alle.
5. **Merging** – antall automatiske sammenslåinger, automatiske oppfølgingskoblinger og saker Mads har delt opp igjen i perioden. Under: de 50 siste automatiske sammenslåingene med de to titlene, kildene, AI-sikkerhet og dato, slik at Mads kan stikkprøve dem.
6. **Search budget** – brukt / grense denne måneden (gjenbruk det Source advisor viser).

Tom periode eller tomme tabeller viser «No data in this period.», ikke feil. Tall med prosent vises med hele prosent.

Kan noe ikke regnes ut fra databasen (f.eks. at automatiske og manuelle sammenslåinger ikke kan skilles), vis «Not recorded» for det tallet og forklar hvorfor i svar-filen. Ikke legg til ny lagring for å få det til i denne oppgaven.

## Filer som kan endres
- `owis/modules/news/processing/ops_report.py` (ny – all logikk her)
- `owis/scripts/ops_report.py` (ny – kommandolinje)
- `owis/modules/news/presentation/api.py` (bare et tynt endepunkt som kaller modulen)
- `owis/apps/web/news.html` (bare det nye kortet i Settings → News og koden som tegner det)
- `owis/tests/test_ops_report.py` (ny)
- `PROJECT_STATUS.md` (kort linje om at driftsrapporten finnes)

## Ikke rør
- Poengsum, matching, morgenrapport og innhenting – denne oppgaven bare leser.
- `theme.css` og utseendet ellers.

## Tips
- Morgenrapportene ligger i tabellen `news_morning_reports` (`status`, `completed_at`, `result_json` med `brief.ai` og `news_total`).
- Søkebudsjettet: `owis/modules/news/processing/search_budget.py`.
- Sammenslåinger og koblinger: se `news_collection_overrides`, `news_match_review_pairs` og `news_story_links`, og hvordan `_run_match_review` i `api.py` skriver dem.
- Fulltekst: `owis/modules/news/processing/fulltext.py` og `news_content_basis`.
- Kildeliste og helse: `news_source_registry`, `source_fetch_health`.

## Utenfor oppgaven
- Varsler, e-post eller grafer.
- Å endre terskler eller poengmodell ut fra tallene – det gjør vi i et eget kort når Mads har sett rapporten.
