# Svar på oppgave 003

## Gjort

- Flyttet jobber og kildeframdrift til `processing/jobs.py`, samlinger og saker til `processing/collections.py`, matching til `processing/match_review.py`, oppgaver etter innhenting til `processing/after_fetch.py` og artikkel-, relevans- og domenehjelpere til `processing/item_view.py`.
- Lagt innhentingsløpet og arkivering i egne `processing/fetch_process.py` og `processing/retention.py`. Dette er også ren flytting fra API-filen.
- Redusert `presentation/api.py` fra 1 658 til 449 linjer. Forespørselsmodellene, rutene, enkel validering, oversetting av feil og korte kall til behandling og lagring står igjen.
- Planleggeren bruker nå jobbmodulen direkte. Tester bruker de nye import- og mock-stiene; ingen testforventninger er endret. `main.py` beholder importen av API-ruteren, som fortsatt hører hjemme der.
- Beholdt URL-er, svarfelter, terskler, databasemodell og avhengigheter.

## Små tekniske valg

API-et sender den eksisterende forespørselsmodellen til jobbkjøreren som `request_factory`. Valideringen skjer fortsatt i bakgrunnsjobben, og modellen trenger ikke flyttes eller importeres fra behandlingslaget. Interne kall bruker ferdig angitte verdier. Jobbkjøreren laster behandlingsfunksjonene når jobben starter, etter at jobbtilstanden er opprettet.

Funksjonsnavnene er beholdt, også innledende understrek. Behandlingsfunksjoner som mottar en forespørsel bruker `Any` som type, slik at de ikke trenger å importere Pydantic-modellene fra API-et.

Ingen ny produktbeslutning eller endret brukeroppførsel er innført, så `DECISIONS.md` og `PROJECT_STATUS.md` er ikke endret.

## Slik kan Mads kontrollere det

Åpne `/news` som vanlig, se nyhetslisten og åpne en sak. Visningen skal være som før. Endringen er intern og gir ingen nye knapper eller nytt utseende.

Ingen nettlesersjekk er kjørt; kortet krever ingen slik sjekk. Ingen ekte innhenting eller eksport er startet.

## Kontroll og tester

- 36 målrettede tester besto.
- OpenAPI-beskrivelsen før og etter er identisk for alle 48 stier, inkludert forespørselsmodeller og dokumentasjon.
- Sammenligning av funksjonsinnhold bekrefter ren flytting, med nødvendige tilpasninger av modellopprettelse og jobbstart.
- Separat kontroll med mockede jobbfunksjoner bekrefter standardverdier, valideringsfeil og planlagt innhenting uten å starte ekte innhenting.
- Hele testsettet: 319 passed (kjørt av Claude, siden Codex-kvoten tok slutt rett før commit).
