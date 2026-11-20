# Morgenrapport og politikk/regelverk

[Til dokumentasjonsoversikten](DOCUMENTATION.md)

## Visning

`/news` har fanene **Morning report** og **Policy & regulation**. Rapporten kan
genereres manuelt, gjenåpnes fra de siste 30 rapportdagene og kopieres som tekst
med kilder. Politikkfanen bruker nyeste rapport og har regionfilter.

Rapporten inneholder, fra rapportene etter 20. november 2026 (D34):

- **Dagens viktigste** på én linje og **i korte trekk** med tre punkter.
- Saker gruppert i **Norway & North Sea**, **Europe & markets**, **Supply chain & contracts**
  og **Policy & regulation**, høyst åtte til sammen. Hver sak har hva som skjedde, hva det betyr
  («So what») og kilder. Politikksaker fra overvåkede kilder lenkes direkte.
- **Trender** fra de siste sju dagene når flere saker på ulike dager støtter dem.
- **Deadlines & events · next 14 days:** konsultasjonsfrister fra overvåkede kilder, daterte
  hendelser fra politikksøket og anbudsfrister fra Opportunities. Hentes fra dataene, ikke skrevet av AI.
- **New tenders · last 24 hours:** anbud som ble koblet til en profil siden forrige rapport.
- **Watch next:** inntil tre konkrete neste steg.
- Sammenfoldet nederst: alle saker siste døgn (inntil 30, etter relevans), politikkutsikten
  (i dag, neste 90 dager og på radaren, bare når den har innhold), nye poster fra overvåkede
  kilder og dekning og advarsler. Advarslene fra politikksøket er slått sammen til én linje per type.

Eldre rapporter vises i det gamle formatet. AI-en får politikk, hendelser og tidligere dager først
og nyhetene sist, innenfor 60 000 tegn; blir det for langt, faller de lavest rangerte sakene ut.
Før D34 ble alt etter 24 000 tegn kuttet, slik at politikk og trender sjelden kom med.
Uten AI vises de høyest rangerte sakene uten skrevet sammendrag. Siste døgn betyr publiseringstid i
`[start − 24 timer, start)`; artikler uten tidssone eller med bare en dato utelates med synlig dekningstall.
Ingen treff er ikke det samme som ingen hendelser.

Faglig avgrensning: energi/havvind, maritim næring og nett/elektrifisering.
Norge og EU prioriteres før Norden og øvrige europeiske land. Det er et målrettet
kildesøk, ikke en komplett lovdatabase eller full dekning av hvert europeisk land.
Kildegruppene vedlikeholdes i `owis/modules/news/processing/governance.py` og vises
i rapporten. De omfatter myndigheter og parlamenter i Norge og EU, Sverige,
Danmark, Finland, Island, Storbritannia, Tyskland, Nederland, Frankrike, Belgia,
Irland, Polen, Spania, Italia, Portugal, Sveits, Østerrike, Tsjekkia og Baltikum.

Politikksøket kjøres bare mandager (`OWI_POLICY_SEARCH_WEEKDAYS`, standard `0`). De andre dagene
kontrolleres bare kjente kilder fra forrige rapport, uten søk. Ved ukentlig søk roteres de globale
parene etter ISO-uke, ved daglig søk etter dagnummer.

Seks ekstra søkegrupper dekker flytende havvind i Sør-Europa, Norden, Baltikum,
Asia-Pacific, Americas og Middle East. De følger faste par: Sør-Europa/Norden,
Baltikum/Asia-Pacific og Americas/Middle East. Dagnummer i året modulo 3 velger
henholdsvis par 0, 1 eller 2. Rotasjonen beregnes på nytt ved årsskiftet.
De åtte opprinnelige gruppene søkes hver dag, før dagens ekstra par.
Grupper uten tur og uten kjente kilder vises som `not_scheduled`, uten advarsel.

## Automatisk kjøring kl. 06

Sett `OWI_MORNING_REPORT_ENABLED=true` i OWIS-serverens miljø og start serveren
på nytt. Standard er `false`; implementeringen alene aktiverer ingen betalt
innhenting. Serveren må være oppe og ha vedvarende database/volum.

Den innebygde bakgrunnstråden sjekker hvert minutt og starter én rapport per dato
kl. 06:00 **Europe/Oslo**, med automatisk sommer-/vintertid. Ved oppstart senere
samme dag kjøres dagens rapport. Tidligere tapte dager etterfylles ikke.
Rapporten blir tilgjengelig etter at innhenting og analyse er ferdig.

Rapporten henter ingenting selv. Den bruker nyhetene den vanlige innhentingen
har lagret kl. 05, 08, 12, 15, 18 og 21 (`OWI_FETCH_HOURS`).
Rapporten venter til en pågående innhenting er ferdig, slik at 05-hentingen er
med. Er siste innhenting eldre enn seks timer, står det i rapporten.

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

Nyhetsdelen leser bare fra databasen. Ubehandlede artikler, kildefeil fra siste
innhenting og ukjente datoer merkes i rapporten. Ingen arkivering utløses av
morgenjobben.

Politikkdelen krever eksisterende AI-oppsett og `TAVILY_API_KEY` eller
`BRAVE_SEARCH_API_KEY`. Uten disse lagres nyhetsrapporten med beskjed om at
politikkdelen ikke er undersøkt. Inntil ti søk brukes per rapport, i tillegg til
vanlig nyhetsbehandling: åtte eksisterende og to ekstra. Ved én daglig rapport
blir økningen 60 søk på 30 dager (56–62 avhengig av månedslengde), innen D17.
Inntil to kjente kommende kilder per gruppe undersøkes på nytt, også utenom
gruppens søkedag, uten søkeforbruk. Hver søkt gruppe leser høyst fem kilder;
de fire gruppene uten tur kan lese to hver. Det gir høyst 58 kildeforsøk og
14 AI-ekstraksjoner per rapport. Stramt søkebudsjett kan redusere dekningen.
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
