# AGENTS.md – OWIS

Regler for kodeagenter (Codex) som jobber i dette prosjektet. Les hele filen før du starter.

## Roller

- **Claude** bestemmer retning, design, datamodell og tekster i appen, og skriver oppgavekortene i `oppgaver/`.
- **Codex** gjør oppgaven slik kortet beskriver: skriver koden, kjører testene og lagrer endringene på egen gren.
- **Mads** eier appen, tester og godkjenner. Mads er ikke utvikler – skriv oppsummeringer enkelt og på norsk.

Står det noe i kortet som er uklart, eller krever oppgaven en designbeslutning kortet ikke dekker: stopp og skriv spørsmålet i `oppgaver/NNN-....svar.md` i stedet for å gjette.

## Arbeidsflyt per oppgave

1. Les oppgavekortet (`oppgaver/NNN-navn.md`) og bare filene det peker på, pluss det du trenger for å forstå dem.
2. Lag gren fra `main`: `codex/NNN-kort-navn`.
3. Gjør endringen. Hold deg innenfor «Filer som kan endres». Rør aldri det som står under «Ikke rør».
4. Kjør `.\.venv\Scripts\python.exe -m pytest owis/tests -q` til alt er grønt. Legg til eller oppdater tester når oppførsel endres.
5. Commit på grenen (se stil under). Aldri commit direkte på `main`, aldri `git push`, aldri slå sammen selv.
6. Skriv `oppgaver/NNN-navn.svar.md`: hva som er gjort, hvordan Mads kan se det i appen, hva som ikke ble gjort eller er usikkert, og testresultatet.
7. Fører oppgaven til en ny beslutning eller endret oppførsel: legg til eller oppdater punkt i `DECISIONS.md` (neste D-nummer) og statuslinjen i `PROJECT_STATUS.md`.

## Prosjektet

- Python 3.11 (Railway/Docker) og 3.13 (lokalt), FastAPI, SQLite. Start lokalt: `powershell -ExecutionPolicy Bypass -File owis/scripts/preview.ps1` → http://127.0.0.1:8000/news.
- `owis/apps/api/main.py` starter appen, innlogging og planlagte jobber. `owis/apps/web/` er grensesnittet (ren HTML/JS, ingen rammeverk, ingen byggesteg), servert under `/static`.
- Nyheter: `owis/modules/news/` – `collectors/` (RSS/skraping), `processing/` (poengsum, saker, matching, morgenrapport, politikk), `storage/`, `presentation/api.py` (API-et).
- Opportunities: `owis/modules/opportunities/` (TED, Doffin, Verdensbanken). Ikke endre uten at kortet sier det.
- Drift: Railway (`railway.json`, `Dockerfile`), database på Railway-volumet. Beslutninger står i `DECISIONS.md`, status i `PROJECT_STATUS.md`.

## Faste regler

- **Engelsk** i all tekst brukeren ser i appen (D11). Dokumentasjon (`*.md`) og svar-filer på **norsk**. Kodekommentarer på engelsk, korte, som i koden rundt.
- **Ikke endre utseende eller tema** (`theme.css`, farger, fonter, oppsett) med mindre kortet sier det.
- **Ingen nye avhengigheter** i `owis/requirements.txt` uten at kortet sier det.
- **Ingen nettverkskall i testene.** Mock OpenAI, Notion, Tavily/Brave og nettsider. Ikke kjør innhenting, AI eller Notion-eksport med ekte nøkler.
- **Data og hemmeligheter:** `owis/data/`, `work/`, `.env` og filer i prosjektroten som ikke er sporet av Git (f.eks. `owis.txt`, `handover_sources.txt`, `career-team/`) er private. Ikke les dem, ikke legg dem i commits. Bruk aldri `git add .` eller `git add -A` – legg til filene du har endret, én og én.
- Nye innstillinger leses fra miljøvariabler i `owis/core/config/settings.py`, med trygg standard (av), og føres opp i `owis/.env.example`.
- Skriv kode som ligner koden rundt: samme navngiving, samme stil, ingen store omskrivinger kortet ikke ber om.

## Commit-stil

Én linje på engelsk som sier hva brukeren merker, slik som de eksisterende:

```
Read publication times for scraped articles
```
