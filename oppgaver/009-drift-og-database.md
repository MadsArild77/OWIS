# 009 – Passordkrav på Railway og databasen ved samtidige skrivinger

> Utført direkte av Claude 19. november 2026 etter ønske fra Mads, ikke av Codex.

## Mål
Et Railway-miljø kan ikke starte uten passord, og bakgrunnsjobbene og nettsiden kan
skrive til databasen samtidig uten feilen «database is locked».

## Hvorfor
Innlogging er aktiv, men appen startet åpen hvis `OWI_ACCESS_PASSWORD` manglet, for
eksempel i et nytt miljø. Fire bakgrunnsjobber og nettsiden skriver til samme SQLite-fil
uten WAL og med fem sekunders ventetid på lås.

## Ferdig når
- [x] Oppstart på Railway uten `OWI_ACCESS_PASSWORD` stoppes med en tydelig feilmelding.
- [x] `OWI_ALLOW_OPEN_ACCESS=true` åpner bevisst, med advarsel i loggen. Lokalt er alt som før.
- [x] Databasen bruker WAL, og hver forbindelse venter opptil 30 sekunder på lås.
- [x] Sikkerhetskopien tar med nylige skrivinger.
- [x] `pytest owis/tests -q` er grønn på Python 3.11 og 3.13, med nye tester.

## Filer som kan endres
- `owis/apps/api/access.py`, `owis/apps/api/main.py`, `owis/core/storage/db.py`
- `owis/tests/test_access.py`, `owis/tests/test_storage.py`, `owis/tests/test_editorial.py`
- `owis/.env.example`, `owis/README.md`, `DECISIONS.md`, `PROJECT_STATUS.md`

## Utenfor oppgaven
Kontroll av kort 004–008 mot ekte kilder, felles innhentingsmotor (trinn 2) og
automatisk henting av anbud.
