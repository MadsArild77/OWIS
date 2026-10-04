# Morgenrapport og politikk/regelverk

[Til dokumentasjonsoversikten](DOCUMENTATION.md)

## Visning

`/news` har fanene **Morning report** og **Policy & regulation**. Rapporten kan
genereres manuelt, gjenåpnes fra de siste 30 rapportdagene og kopieres som tekst
med kilder. Politikkfanen bruker nyeste rapport og har regionfilter.

Rapporten inneholder:

- Siste 24 timer: publiseringstidspunkt i intervallet `[start − 24 timer, start)`.
  Artikler uten tidssone eller med bare en dato utelates med synlig dekningstall.
  Inntil 30 saker vises, rangert etter eksisterende relevansscore. Manuelle
  sammenslåinger grupperes; full automatisk hendelsesdeduplisering er ikke innført.
- I dag og neste 90 dager: kildestøttede politiske milepæler og frister.
- På radaren: relevante forslag og funn uten bekreftet dato, inkludert funn
  som bare bygger på søkeutdrag.
- Kildedekning og feil. Ingen treff er ikke det samme som ingen hendelser.

Faglig avgrensning: energi/havvind, maritim næring og nett/elektrifisering.
Norge og EU prioriteres før Norden og øvrige europeiske land. Det er et målrettet
kildesøk, ikke en komplett lovdatabase eller full dekning av hvert europeisk land.
Kildegruppene vedlikeholdes i `owis/modules/news/processing/governance.py` og vises
i rapporten. De omfatter myndigheter og parlamenter i Norge og EU, Sverige,
Danmark, Finland, Island, Storbritannia, Tyskland, Nederland, Frankrike, Belgia,
Irland, Polen, Spania, Italia, Portugal, Sveits, Østerrike, Tsjekkia og Baltikum.

## Automatisk kjøring kl. 06

Sett `OWI_MORNING_REPORT_ENABLED=true` i OWIS-serverens miljø og start serveren
på nytt. Standard er `false`; implementeringen alene aktiverer ingen betalt
innhenting. Serveren må være oppe og ha vedvarende database/volum.

Den innebygde bakgrunnstråden sjekker hvert minutt og starter én rapport per dato
kl. 06:00 **Europe/Oslo**, med automatisk sommer-/vintertid. Ved oppstart senere
samme dag kjøres dagens rapport. Tidligere tapte dager etterfylles ikke.
Rapporten blir tilgjengelig etter at innhenting og analyse er ferdig.

En databasebasert reservasjon hindrer samtidige kjøringer for samme dato på tvers
av prosesser. En reservasjon regnes som avbrutt etter to timer. Feilede kjøringer
gjentas ikke hvert minutt; manuell ny kjøring har fem minutters sperre.
Forrige lagrede resultat beholdes ved feil i en oppdatering.

Alternativt kan en ekstern jobbplanlegger med tidssonen Europe/Oslo kjøre:

```powershell
python -m owis.jobs.run_morning_report
```

Kjør med `--refresh` for å erstatte dagens rapport. Kommandoen venter på resultatet
og gir feilkode ved feil. Bruk samme konfigurasjon og database som webappen.

## Innhenting, forbruk og begrensninger

Nyhetsdelen bruker eksisterende RSS-/nettsidekilder og behandler høyst 100
ubehandlede artikler per kjøring. Kø, feil og ukjente datoer merkes i rapporten.
Ingen arkivering utløses av morgenjobben.

Politikkdelen krever eksisterende AI-oppsett og `TAVILY_API_KEY` eller
`BRAVE_SEARCH_API_KEY`. Uten disse lagres nyhetsrapporten med beskjed om at
politikkdelen ikke er undersøkt. Inntil åtte søk, 40 kildeforsøk og åtte
AI-ekstraksjoner brukes per rapport, i tillegg til vanlig nyhetsbehandling.
Inntil to kjente kommende kilder per gruppe undersøkes på nytt innen samme grense.
Dette er antallsgrenser, ikke en kostnadsgrense i kroner.

Bare tillatte myndighetsdomener godtas. Kildeutdrag og datoquote lagres. Funn må
ha et ordrett støttende utdrag; kalenderdatoen må også finnes som samme komplette
dato i sitatet og komme fra innlest sidetekst. Ustøttede påstander utelates;
søkeutdrag og datoformater som ikke kan valideres havner på radaren.

Forslag, høring, vedtak og ikrafttredelse holdes adskilt. Modellen instrueres om
at EU-rett ikke automatisk gjelder i Norge uten relevant EØS-/nasjonal prosess.
Dette er AI-ekstraksjon, ikke juridisk verifikasjon. Følg lenken til originalen
før en frist eller rettslig status legges til grunn. Endringer i kildene kan
komme etter rapportens tidspunkt.

## Lyd

Rapporten kan kopieres som kildegrunnlag til en LLM eller NotebookLM. Automatisk
lydproduksjon og overføring til Google er ikke implementert eller aktivert.

## API

- `GET /api/news/morning-report` — nyeste kjøring og lagret resultat.
- `GET /api/news/morning-report?report_date=YYYY-MM-DD` — bestemt rapportdag.
- `GET /api/news/morning-report/history` — siste 30 rapportdager.
- `POST /api/news/morning-report?refresh=true` — start eller oppdater dagens rapport.
