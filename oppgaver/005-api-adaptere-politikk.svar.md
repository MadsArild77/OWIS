# Svar på 005 – API-adaptere for politikkildene

## Gjort

- Lagt til adaptere for Have your say, Folketinget og Tweede Kamer, valgt etter vert og EU-endepunkt.
- Alle bruker registerets adresse og leser høyst 500 poster. Folketinget og Tweede Kamer stopper
  ved 30 dager og bruker temafilteret fra 004. EU leser videre gjennom gamle poster og beholder åpne perioder.
- Lagt til automatisk migrering av `policy_items.deadline`. EU-henting oppdaterer frist, type og
  publiseringsdato på eksisterende rader, slik at lukkede konsultasjoner ikke blir stående som åpne.
- Åpne konsultasjoner vises selv om startdatoen er eldre enn 30 dager. Listen viser «Deadline 14 Nov»,
  med årstall ved annet år og temaets varselfarge innen sju dager. Consultations sorterer nærmeste åpne frist først.
- Morgenrapportens datagrunnlag inkluderer `deadline` og prioriterer konsultasjoner med frist innen 14 dager.
- Kildetesten viser inntil fem poster. Stortinget hoppes over med D25-forklaring; ukjente API-er logges som feil.
- Oppdatert kildedokumentasjon, prosjektstatus og beslutning D31.

## Slik kan Mads se endringen

Etter vanlig planlagt henting av aktive, importerte kilder: åpne **Policy & regulation → From monitored sources**.
Velg **Consultations** for fristsortering. I **Settings → Regulatory** kan kildetesten vise API-postene.
En ny morgenrapport får med fristene. Denne kjøringen har ikke importert kilder eller hentet til produksjonsdatabasen.

## Valg og begrensninger

- Folketingets grunnsvar har `periodeid`, men ikke samlingskoden som kreves i en sikker ft.dk-adresse.
  Da brukes API-postens adresse. Hvis svaret inkluderer samlingskode og saksnummer, lages ft.dk-lenken.
- Datoer med tidssone normaliseres til UTC. Datoer uten tidssone behandles som UTC; API-svarene fra EU
  og Folketinget oppgir ikke offset. Fristetiketten bruker datoen i UTC, så den viste sluttdatoen beholdes.
- Ekte svar fra de tre offentlige API-ene ble lest 6. november 2026. Fixtures er avgrensede utdrag
  av disse svarene uten personopplysninger. Alle tester erstatter nettverk med lokale svar.
- Ingen nye avhengigheter, AI-kall, produksjonsinnhenting eller endring av kilderegisteret.
- Ingen nettlesersjekk er utført. Fristvisningen er kontrollert ved å kjøre den faktiske JavaScript-funksjonen
  med fast klokke: normal dato, annet år, varselfarge, senere frist og manglende frist.

## Tester

- 20 relevante tester bestod (`test_policy_api_adapters.py` og `test_policy_collector.py`).
- JavaScript-syntaks og fem kontroller av fristvisningen bestod.
- Hele testsettet bestod: **348 passed**, 272 avviklingsvarsler, på 8 minutter og 4 sekunder.
  Kjørt én gang med `C:/Users/madsa/Documents/Codex/OWIS/.venv/Scripts/python.exe -m pytest owis/tests -q --basetemp .pytest-tmp`.
- `git diff --check` bestod. Ingen push eller sammenslåing er utført.
