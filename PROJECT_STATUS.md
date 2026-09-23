# OWIS – status 23. september 2026

## Arbeidssted

- Lokal mappe: `C:\Users\madsa\Documents\Codex\OWIS`.
- Repo: https://github.com/MadsArild77/OWIS
- Arbeidsgren: `work/resume-owis`, basert på `7069c638` fra 12. mai 2026.
- Den gamle arbeidskopien i `C:\Users\madsa\OneDrive\OpenAI` er beholdt. Git-sporet arbeid, inkludert upublisert arkivering, er bevart i denne arbeidsgrenen.
- Integritetskontrollerte SQLite-backuper av `owi.db`, `e2e_test.db` og `master_e2e.db` ligger i `owis/data`. Disse og testdata er ignorert av Git.
- Andre prosjekter og eksportfiler i OpenAI-mappen er beholdt der.

## Verifisert nyhetsflyt

- De gamle RSS-adressene til Recharge og WindEurope svarte 404. WindEurope er korrigert til `/feed/`, OffshoreWIND.biz er lagt til, og den ødelagte Recharge-kilden er deaktivert.
- 60 feed-elementer hentet fra to kilder; 5 eldre enn 30 dager filtrert bort; **55 artikler lagret og behandlet uten feil** i `work/live-validation.db`.
- Andre innhenting: **0 nye artikler og 0 behandlingsfeil**.
- Signalformat og kilde-URL kontrollert for alle 55. Én originalartikkel fra hver kilde svarte HTTP 200.
- Hoveddatabasen fra originalen er tom. Testdataene ligger separat og er kopiert til `work/preview.db` for visning.
- Nyhetsliste og artikkeldetaljer med kildehenvisning er kontrollert i nettleseren.
- **38 automatiserte tester består**. Fire deprecation-advarsler kommer fra feedparser under Python 3.13.
- Avhengighetskontroll og oppstartskontroll består.

## Rettelser

- RSS-henting har timeout, HTTP-feilkontroll og kontroll av feedformat. Feilrapportering skiller nå ødelagte kilder fra vellykket innhenting.
- Fulltekst fra feed bevares. Korte RSS-utdrag avvises ikke som om de var skrapede nettsider.
- HTML, script og stilinnhold fjernes før oppsummering. Aktørforkortelser matches som egne ord, og overskriften inngår i regelbasert tagging.
- Arkivering bevarer manuelle vurderinger, sammenslåinger, læringshistorikk og parvurderinger. Arkiverte URL-er hentes ikke inn igjen. Datoer sammenlignes som tidspunkt, og databasefeil ruller arkiveringen tilbake.
- SQLite-forbindelser lukkes eksplisitt etter transaksjoner.
- PowerShell-oppstart bruker prosjektets virtuelle miljø og korrekt arbeidsmappe, uten konflikt med den reserverte `$Host`-variabelen.
- Metadatafeltenes bakgrunn er tilpasset mørkt tema for lesbar kontrast.

## Forhåndsvisning og videre arbeid

Forhåndsvisning: http://127.0.0.1:8765/news. Den bruker `work/preview.db`, med AI og Notion-eksport deaktivert. Logger og launcher-PID ligger i `work`. Prosessen stopper ved omstart; se README for vanlig oppstart.

Oppsummeringer i testen er tekstutdrag. Tagging, prioritering og «why it matters» er regelbasert og krever fortsatt faglig kalibrering. Enkelte feeder gir bare korte utdrag. AI-kvalitet er ikke testet.

Neste steg er å kalibrere relevans og scoring, og deretter implementere News/LinkedIn-eksport til Notion med valgt måldatabase. Opportunities har allerede egen Notion-eksport, men News har ikke den spesifiserte eksportjobben. News v1 er derfor ikke erklært ferdig.

Ingen publisert app eller automatisk innhenting er aktivert av denne gjennomgangen. NorthernBlue-portalen har fortsatt OWIS som `building` / `planned`. Prosjektmappen er klar for åpning i Codex; registrering i sidepanelet er ikke utført.
