# Plan: felles kildekonfigurasjon og innhenting

Avtalt 3. oktober 2026. Vi gjennomfører fire PR-er i rekkefølge, én om gangen.
Hvert trinn implementeres, testes og kontrolleres i appen før neste trinn starter.
Hver PR skal fungere selvstendig og bevare eksisterende nyhetsflyt.

**Status:** Punkt 1 er implementert og validert i [utkast-PR #8](https://github.com/MadsArild77/OWIS/pull/8). Punkt 2–4 er ikke startet.
**Neste oppgave:** Gjennomgå PR 1, deretter punkt 2 – felles innhentingsmotor.

Oppdater denne filen etter hvert trinn med PR-lenke, validering, gjenstående
begrensninger og neste oppgave. Eksisterende morgenrapport og politikkvisning
er et utgangspunkt; de betyr ikke at arbeidet nedenfor er ferdig.

## 1. Datamodell og konfigurasjon

- [x] Felles kilderegister for nyheter, regelverk og kalendere.
- [x] EU og hvert enkelt land som separate jurisdiksjoner. Norden og Europa
  er visningsgrupper. EU-land kan være tilgjengelige fra start, med aktivering
  per land. Land uten aktive kilder merkes «Ikke overvåket».
- [x] Organisasjoner under jurisdiksjonen: departementer, parlamenter,
  komiteer og myndigheter. Prioritering knyttes primært til organisasjon/rolle,
  med mulighet for personoverstyring.
- [x] Kilder med navn, URL, innholdstype, hentemåte, temaer, kontrollintervall
  og aktiv/pause. Skill innholdstype (nyheter, regelverk, høring, kalender)
  fra hentemåte (RSS/Atom, nettsideliste, enkeltside, ICS, API).
- [x] Prioritering: følg alle, følg ved tematreff eller av.
- [x] Settings med legg til, rediger, pause og test kilde; tekniske valg under
  Avansert. Test skal vise faktisk uttrekk eller tydelig manglende støtte.
  Full støtte for nye hentemåter kommer i senere trinn, ikke som falske testtreff.
- [x] Deaktivering bevarer historikk; konfigurasjon kan eksporteres/importeres.
- [x] Migrer eksisterende nyhetskilder uten å overskrive brukerens valg.

Ferdig når brukeren kan opprette Norge → Stortinget → Energi- og miljøkomiteen
→ kilde, teste støttet uttrekk og lagre oppsettet.

PR: [#8 – datamodell og konfigurasjon](https://github.com/MadsArild77/OWIS/pull/8), utkast på `codex/source-configuration`.

Validering: 166 tester består (23 nye konfigurasjonstester), JavaScript-syntaks
og diff kontrollert. Nettlesertest med isolert database: opprettelse av
Norge → Stortinget → Energi- og miljøkomiteen → kilde, faktisk HTML-uttrekk,
lagring/omlasting og pause/gjenopptak av jurisdiksjon.

Begrensninger: kalender-/regelverksadaptere, kontrollintervaller og tema-/
personfiltrering er fortsatt punkt 2–3. Morgenrapporten kobles til i punkt 4.
HTML-testen viser generiske lenker, ikke strukturerte kalenderhendelser.
Se [SOURCE_CONFIGURATION.md](SOURCE_CONFIGURATION.md) for drift og migrering.

## 2. Felles innhentingsmotor

- [ ] Felles modul for nettverkshenting, endringskontroll, logging og kildehelse.
- [ ] Behold HTTPX og feedparser. Evaluer Trafilatura mot representative
  nyhetsartikler, høringssider og kalendere før uttrekket erstattes.
- [ ] RSS/Atom, nettsidelister og enkeltsider først. ICS/API-adaptere der
  kildene tilbyr det. Nettleserbasert henting bare for kilder som trenger det.
- [ ] Betingede forespørsler med ETag/Last-Modified, og innholdssjekksum av
  relevant innhold. Bevar datoer, tabeller, dokumentnumre og lenker.
- [ ] Dokumentidentitet via kilde-ID/normalisert URL; samme URL med nytt
  innhold gir ny versjon. Bevar kildehenvisninger ved overlapp mellom utgivere.
- [ ] Lagre versjoner og forskjeller; gjenbruk analyse av uendret innhold.
  Registrer hvilken uttrekks- og analyseversjon som ble brukt.
- [ ] Behold siste gode versjon ved feil, blokkering eller mistenkelig tomt uttrekk.
- [ ] Kildebestemte grenser og stoppregler for paginering: dato, maksimal
  dybde og flere sider uten nye/endrede saker. Ikke stopp ved første kjente treff.
- [ ] Kontroller overvåkede enkeltsaker selv om oversiktssiden er uendret.
  Periodiske bredere kontroller skal fange opp eldre endringer og omorganisering.
- [ ] Begrens belastning per nettsted; respekter tidsgrenser og kontrollintervall.

Ferdig når en endret frist på samme URL oppdages, mens menyendringer ikke
utløser ny analyse. Verifiser uendret respons, nye saker, endret innhold og feil.

PR: ikke opprettet. Validering: ikke utført.

## 3. Norge-adaptere og prioritering

- [ ] Pilot med én eksisterende nyhetsfeed og én nyhetsnettside.
- [ ] Regjeringens kalender: dato/tid, tidssone, departement, person, sted,
  kilde og endringer. Forsvinning fra oversikten er ikke alene en avlysning.
- [ ] Regjeringens høringer: frister, dokumenter og statusendringer.
- [ ] Stortingets energi- og miljøkomité: saker, høringer, dokumenter,
  innstillinger og kobling til planlagt behandling i Stortinget.
- [ ] Undersøk strukturerte grensesnitt før scraping. Dokumenter faktisk
  dekning og begrensninger per adapter.
- [ ] Skill og koble dokumenter, saker og kalenderhendelser.
- [ ] Regelverk med jurisdiksjon, dokumentreferanse, status og kildebelagte
  datoer. EU-saker kobles til nasjonale oppfølginger med egne statuser og frister.
  EØS-innlemmelse og norsk gjennomføring registreres separat.
- [ ] Usikre sakskoblinger merkes som forslag. Møter er ikke vedtak.
- [ ] Forklar hvorfor en hendelse er valgt, eksempelvis organisasjon eller tematreff.

Foreslått startoppsett, redigerbart av brukeren:

| Organisasjon | Prioritering |
|---|---|
| Energi- og miljøkomiteen | Alle publiserte møter, høringer og saker |
| Næringskomiteen, finanskomiteen, transport- og kommunikasjonskomiteen | Tematreff |
| Energidepartementet, Nærings- og fiskeridepartementet, Klima- og miljødepartementet | Alle publiserte hendelser |
| Statsministerens kontor, Finansdepartementet, Samferdselsdepartementet, Utenriksdepartementet | Tematreff |
| Øvrige organisasjoner | Av som standard, kan aktiveres |

Temaer: energi, havvind, nett, maritim næring, industri, investeringer og
relevant EU/EØS-politikk. Skill mellom hva vi følger og hva morgenrapporten
fremhever. Statssekretærer og andre enkeltpersoner skal kunne overstyres.

Ferdig når piloten viser nye saker, endrede frister/hendelser og kildefeil
korrekt, og en sak kan følges gjennom flere dokumenter og behandlingssteg.

PR: ikke opprettet. Validering: ikke utført.

## 4. Morgenrapport og drift

- [ ] Siste døgn: nye saker og oppdagede endringer; publiseringstid vises separat.
- [ ] I dag og neste 90 dager: frister og kalenderhendelser etter hendelsesdato.
- [ ] På radaren: relevante saker uten avklart dato.
- [ ] Vis dekning, kildefeil, forsinkelser og jurisdiksjoner som ikke overvåkes.
- [ ] Første innlasting etablerer et grunnlag og fyller ikke rapporten med
  gamle dokumenter merket som nye oppdateringer.
- [ ] Test med isolerte data og deretter et begrenset reelt kildeutvalg.
- [ ] Flytt eksisterende kilder gradvis over til den felles motoren.
- [ ] Kontroller faktiske rapporter før kl. 06-kjøringen aktiveres i driftsmiljøet.
  Bruk Europe/Oslo, vedvarende lagring og vern mot dobbeltkjøring ved omstart.

Ferdig når rapportens endringer kan spores til originalkilder, dekningen er
synlig og omstart ikke gir dobbeltkjøring.

PR: ikke opprettet. Validering: ikke utført.

## Senere utvidelser

- Flere land og EU-adaptere etter at Norge-piloten fungerer, med hvert land
  som egen jurisdiksjon. Kalenderkilder finnes blant annet i Sverige, Finland
  og EU-rådet; tilgjengelige feed-/API-formater må undersøkes per kilde.
- Lydgenerering/NotebookLM vurderes etter at kildegrunnlag og rapport fungerer.

## Referanser

- [Eksisterende morgenrapport](MORNING_REPORT.md)
- [Trafilatura](https://github.com/adbar/trafilatura)
- [Regjeringens kalender](https://www.regjeringen.no/no/aktuelt/kalender/id1330/)
- [Stortingets kalender](https://stortinget.no/no/Hva-skjer-pa-Stortinget/)
