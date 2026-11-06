# Svar på 008 – Opportunities i nytt design

## Gjort
- Skrevet om Opportunities med rammen, menylenkene, temabryteren og
  komponentklassene fra eInnsyn. Tenders har Open, Closing soon, New this week,
  Saved og Hidden, med antall som følger filtrene.
- Lagt til profilknapper med flervalg, region, kilde, fit og søk i adressen.
  Listen viser oppdragsgiver, land, kilde, publisering, frist og fit.
- Lagt til lesepanel med detaljer, avrundet verdi, original lenke, Save,
  Not relevant/Restore og Copy info. Hurtigtastene er /, j, k, Esc og s.
- Lagt til GET `/api/opportunities/list`, GET `/api/opportunities/profiles`
  og POST `/api/opportunities/item/{id}/state`. Tilstanden lagres i en egen
  SQLite-tabell knyttet til råanbudet, slik at den tåler ny behandling.
- Flyttet de eksisterende Notion-knappene til Settings nederst på siden.
  Eksportfunksjonen og eksportendepunktet har samme oppførsel som før.
  Settings viser også kildestatus, lesbare profiler og manuell kjøring.
- Oppdatert D28 og prosjektstatus. Ingen hentere, poenglogikk, felles temafiler
  eller nyhetsside er endret. Ingen produksjonsinnhenting eller eksport er kjørt.

## Valg innenfor kortet
- Settings ligger nederst på Opportunities. Det holder avanserte valg og
  Notion-eksport sammen med anbudene uten å endre nyhetssiden.
- High og Low er visningsnavn for eksisterende Strong og Weak.
- New this week betyr de siste sju kalenderdagene, inkludert i dag, i UTC.
  Open inkluderer dagens frist, Closing soon inkluderer dag 14.
- Lagret og skjult er gjensidig utelukkende, i tråd med API-ets tre tilstander.
  Restore setter none; en tidligere lagring gjenopprettes ikke automatisk.
- Fetch tenders bruker standardinnstillingene. Manuell kjøring bruker feltene
  i Settings. Under kjøring vises en ubestemt fremdriftsindikator; ved avslutning
  vises antall og kilderapport. Det eksisterende synkrone endepunktet leverer
  ikke løpende prosent eller delresultater per kilde.

## Slik kan Mads se det
Åpne `/opportunities`. Velg visning og filtre, åpne et anbud og prøv Save,
Not relevant og Restore. Kopier adressen for å gjenbruke filtrene. Settings
ligger under listen og har en snarvei ved filtrene. Fetch tenders starter en
ekte innhenting når den brukes i appen.

## Kontroll og begrensninger
- 18 nye automatiske tester bestått: filtre og flervalg, visninger, fristsortering,
  utløpte anbud, antall før limit, lagret/skjult/Restore, ugyldige forespørsler,
  regioner, profilregister og ukesgrense.
- Hele testsettet: **337 bestått**, 272 advarsler om foreldede grensesnitt,
  på 563,89 sekunder. Kjørt med den angitte Python-tolken og
  `-m pytest owis/tests -q --basetemp .pytest-tmp`.
- JavaScript-syntaksen er kontrollert, HTML-en er lest med parser uten
  dupliserte element-ID-er, og `git diff --check` er uten feil.
- Nettlesersjekk med testdata er **ikke utført**. Visninger, filtre, søk,
  lesepanel, lagre/skjule/angre, Copy info, Fetch tenders, tema og mobil er
  derfor ikke visuelt eller interaktivt verifisert i nettleser. En lokal
  testserver med syntetiske data og simulert Fetch ble startet, men verktøyet
  svarte «The browser access host is unavailable» da testsiden skulle åpnes.
  API-testene erstatter ikke denne sjekken.
- Mobilregler og temafarger følger eksisterende komponenter, men kontrast og
  fravær av sidelengs rulling må bekreftes i nettleser.
