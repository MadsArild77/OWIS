# OWIS

Dedicated development copy of https://github.com/MadsArild77/OWIS.

This workspace preserves the tracked local work found in `C:\Users\madsa\OneDrive\OpenAI` on 2026-09-23, based on commit `7069c638bdf17fb95d03fef3cfccdfdcfa6ba403`. The original workspace remains intact. Work continues on branch `work/resume-owis`.

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

See `PROJECT_STATUS.md` for the verified baseline and next steps, `owis/README.md` for configuration, and the two root specification documents for product scope.

The app reads environment variables; it does not automatically load `.env`. AI and Notion export default to disabled. Database copies are ignored by Git.

See `MATCHING.md` for OpenAI setup, cross-language matching and the opt-in live evaluation.
