# Svar på 004 – innhenting av politikkilder

## Gjort

- Egen innhentingsjobb for aktive RSS/Atom- og HTML-listekilder med politikkinnhold, uten `news`.
  Jobben bruker samme klokkeslett og eksisterende av/på-bryter som nyhetene, men egen tråd og
  egne databasekrav mot dobbeltkjøring. Nyhetsjobbens tidsgrense er uendret.
- Egen tabell `policy_items`, normaliserte URL-er, kildeintervall, temaarv, 30-dagersgrense ved
  første vellykkede henting og oppgradering av innholdstype ved overlapp.
- Kjøringslogg med tidspunkt, resultat, antall lest/lagret/filtrert og feil.
- «From monitored sources» med daggrupper, regioner, typeknapper, «Show more» og kildestatus.
- Morgenrapportens AI-grunnlag og lagrede rapport inkluderer inntil 40 nye poster fra siste døgn,
  med `all`-kilder først. Visningen viser inntil ti lenker under «New from monitored sources».
- Statusdokumentene er oppdatert, og beslutning D29 beskriver oppførselen.

## Slik ser Mads det

1. Importer kildefilen i **Settings → Regulatory → Import** dersom dette ikke allerede er gjort.
2. La appen kjøre med planlagt innhenting aktivert. Politikkjobben bruker `OWI_FETCH_HOURS` og
   respekterer hver kildes intervall, også ved feil.
3. Åpne **Policy & regulation → From monitored sources**. Prøv regionvelgeren og typeknappene.
   Åpne **Source status** for hentetidspunkt, sist lagret og eventuelle feil.
4. Neste morgenrapport tar med nye poster. Eksisterende lagrede rapporter endres ikke.

## Små valg og begrensninger

- «Show more» åpner neste side med inntil 100 poster, slik at høyst 100 vises samtidig.
- Første vellykkede henting brukes som grense for førstegangsfilteret. En nettfeil skal ikke
  gjøre at en senere vellykket henting importerer hele historikken.
- Uten arvet `all` eller temaord som treffer, lagres ingen poster. Kilder med `inherit` uten
  organisasjon får dermed ingen utilsiktet import av alt innhold.
- «Sist lagret» betyr siste kjøring som opprettet en ny post. En duplikatoppgradering endrer
  bare innholdstypen, ikke opprinnelig kilde eller `first_seen_at`.
- Ingen nettlesersjekk er utført. JavaScript-syntaks er kontrollert; utseende og klikkflyt må
  fortsatt prøves i nettleser. Ingen ekte kildeinnhenting, produksjonsdata eller betalte kall
  er brukt. HTTP-testene bruker simulerte svar, ikke nettverk.
- API-kilder, importfil, registerkode, eksisterende søkebasert politikk og eInnsyn/Storting
  er ikke endret. Ingen kildefeil i importfilen er undersøkt eller konstatert her.

## Tester

- Relevante tester: **32 bestod** (nye politikkildetester og eksisterende morgenrapporttester).
- Hele testsettet: **319 bestod** på 580,24 sekunder (9 minutter og 40 sekunder).
  Kjørt med `C:/Users/madsa/Documents/Codex/OWIS/.venv/Scripts/python.exe -m pytest owis/tests -q --basetemp .pytest-tmp`.
  272 varsler om utdaterte bibliotekgrensesnitt; ingen testfeil.
- JavaScript-syntaks og `git diff --check`: OK.
