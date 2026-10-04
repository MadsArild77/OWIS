# OWIS

**[Dokumentasjon og beslutninger – start her](DOCUMENTATION.md)**

[Prosjektstatus](PROJECT_STATUS.md) · [Beslutningslogg](DECISIONS.md) · [Implementeringsplan](IMPLEMENTATION_PLAN.md)

OWIS samler nyheter, research og politikk-/regelverksinformasjon.
Repo: https://github.com/MadsArild77/OWIS.

Trinn 1 (kildekonfigurasjon) og separate News-/Regulatory-faner er på `main`.
Neste planlagte trinn er felles innhentingsmotor. Se status og plan for begrensninger.

## Start locally (PowerShell)

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r owis/requirements.txt
powershell -ExecutionPolicy Bypass -File owis/scripts/preview.ps1
```

Open http://127.0.0.1:8000/news. Opportunities is at `/opportunities`.

Run existing tests:

```powershell
.\.venv\Scripts\python.exe -m pytest owis/tests -q
```

See [DOCUMENTATION.md](DOCUMENTATION.md) for all documentation, decisions and specifications.

The app reads environment variables; it does not automatically load `.env`. AI and Notion export default to disabled. Database copies are ignored by Git.

See `MATCHING.md` for OpenAI setup, cross-language matching and the opt-in live evaluation.
