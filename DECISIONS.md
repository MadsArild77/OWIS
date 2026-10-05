# OWIS – beslutningslogg

[Til dokumentasjonsoversikten](DOCUMENTATION.md)

Samlet 4. oktober 2026 fra avtalene i utviklingssamtalen, implementeringsplanen
og gjennomførte endringer. «Vedtatt» betyr valgt retning; implementeringsstatus
står separat. Listen dekker dokumenterte valg, ikke udokumenterte historiske samtaler.

## D01 – Én inngang til dokumentasjon og beslutninger

**Vedtatt 4. oktober 2026. Implementert i dokumentasjonen.**
All dokumentasjon skal kunne finnes fra [DOCUMENTATION.md](DOCUMENTATION.md).
Denne loggen bevarer begrunnelser og omvalg; [prosjektstatus](PROJECT_STATUS.md)
og [planen](IMPLEMENTATION_PLAN.md) viser fremdriften. Git gir endringshistorikk.
Bakgrunn: spredte dokumenter og utdaterte statuslinjer gjorde det vanskelig å
vite hva som var gjeldende. Eksisterende filstier beholdes for å bevare lenker.

## D02 – Gjennomfør fire utviklingstrinn i rekkefølge

**Vedtatt 3. oktober 2026. Trinn 1 ferdig; trinn 2–4 gjenstår.**
Rekkefølgen er konfigurasjon → felles innhentingsmotor → Norge-adaptere og
prioritering → morgenrapport og drift. Hvert trinn skal fungere selvstendig,
testes og kontrolleres før neste. Se [ferdigkriteriene](IMPLEMENTATION_PLAN.md).

## D03 – EU og hvert land er egne jurisdiksjoner

**Vedtatt. Konfigurasjonsmodellen er implementert i PR #8.**
EU skal ikke erstatte nasjonale jurisdiksjoner: regelverk og gjennomføring kan
være ulike. Norden og Europa er visningsgrupper. EU og 27 medlemsland, Norge,
Island og Storbritannia er tilgjengelige fra start; flere kan legges til.
At et land finnes i listen betyr ikke at det overvåkes.
Se [kildekonfigurasjon](SOURCE_CONFIGURATION.md).

## D04 – Felles register med organisasjoner og flere kilder

**Vedtatt. Register og editor implementert; flere innsamlingsadaptere gjenstår.**
Kilder knyttes til jurisdiksjoner og eventuelt departementer, parlamenter,
komiteer eller myndigheter i et hierarki. Innholdstype (nyhet, regelverk,
høring, kalender) skilles fra hentemåte (RSS, HTML, ICS, API).
Legg til, rediger, pause, test og import/eksport støttes. Pause bevarer historikk.
Eksisterende nyhetskilder migreres med brukerens valg og eldre innstillinger bevart.
Se [PR #8](https://github.com/MadsArild77/OWIS/pull/8).

## D05 – Prioriter roller og organisasjoner, med personoverstyring

**Vedtatt. Innstillinger lagres; tema- og personfiltrering er planlagt i trinn 3.**
Følg alle, følg ved tematreff eller av velges per organisasjon; enkeltpersoner
kan overstyres. Vi skal ikke følge alle statsråder likt. Regjeringens kalender
og Stortingets energi- og miljøkomité prioriteres i Norge-piloten.
Detaljert startoppsett for øvrige departementer og komiteer er fortsatt et
forslag i [trinn 3](IMPLEMENTATION_PLAN.md), ikke aktiv overvåking.

## D06 – Felles innhenting for nyheter og regulatoriske kilder

**Vedtatt retning. Ikke implementert som felles motor ennå.**
Motoren skal oppdage både nye saker og endringer på samme URL, bruke betingede
HTTP-forespørsler og sjekksum av relevant innhold, og bevare versjoner og siste
gode resultat. Paginering skal ikke stoppe ved første kjente treff. Strukturerte
API-er og feeder undersøkes før scraping. Se [trinn 2](IMPLEMENTATION_PLAN.md).
HTTPX og feedparser beholdes i planen; Trafilatura skal evalueres før valg.
Gjenbruk av Scrapy eller andre GitHub-prosjekter er ikke en vedtatt migrering.

## D07 – Morgenrapport: siste døgn og det som kommer

**Vedtatt. Grunnrapport implementert; integrasjon med den nye motoren gjenstår.**
Rapporten skal dekke siste 24 timer, i dag, fremover (90 dager i løsningen) og
saker uten avklart dato. Politikk, lover og regler prioriteres for Norge og EU,
med øvrige nordiske og europeiske land i omfanget. Egen politikk-/regelverksvisning
skal gjøre dette tilgjengelig. Dekning og usikkerhet må vises.
Kl. 06 Europe/Oslo er støttet som valgfri kjøring; aktiv drift må verifiseres
separat. Dagens nyhetsdel bruker publiseringstid; endringsbasert rapportering
kommer i trinn 4. Se [morgenrapporten](MORNING_REPORT.md).

## D08 – Kopier kildegrunnlag og finn igjen researchede saker

**Vedtatt og implementert i nyhetsvisningen.**
«Copy info» gir materiale med kildegrunnlag som kan tas videre til en LLM og
brukes til å skrive en post. Saker med lagret research har egen visning.
Research og vurdering av LinkedIn-potensial er underlag, ikke automatisk publisering.
Se [redaksjonell flyt](EDITORIAL.md).

## D09 – Separate News- og Regulatory-faner i Settings

**Vedtatt og implementert 3. oktober 2026, commit `600619b` på main.**
News viser eksisterende kildeverktøy og innhenting og åpnes som standard.
Regulatory viser jurisdiksjoner, organisasjoner og den felles kildeeditoren.
Registeret er fortsatt delt og kan også inneholde nyhetskilder. Bakgrunn:
nyhetsinnstillingene ble vanskelige å finne i en lukket seksjon under konfigurasjonen.

## D10 – Innlogging med felles passord, Railway som eneste driftsplattform

**Vedtatt 5. oktober 2026. Implementert i kode; må aktiveres i Railway.**
Appen og alle API-er krever innlogging når `OWI_ACCESS_PASSWORD` er satt.
`/health` er åpen for Railways helsesjekk. Uten variabelen er appen åpen som før,
slik at utrullingen ikke låser noen ute, men Railway-loggen viser en advarsel.
Bakgrunn: testmiljøet på Railway svarte uten innlogging, slik at hvem som helst
med lenken kunne endre kilder og starte betalte AI-kall. Den ubrukte Render-
konfigurasjonen (`render.yaml`) er fjernet; Railway er eneste driftsplattform.
Oppstartskopier av databasen begrenses til de 14 nyeste. Testene kjøres på
Python 3.11 (Docker/Railway) og 3.13 (lokal utvikling).

## D11 – Lesbart grensesnitt med lyst og mørkt tema

**Vedtatt og implementert 5. oktober 2026.**
News og Opportunities bruker et felles tema (`owis/apps/web/theme.css`) med
lyst og mørkt fargesett. Lyst er standard; mørkt følger systeminnstillingen,
og en bryter øverst til høyre lagrer valget i nettleseren. Teksten er større,
all tekst har kontrast på minst 4,5:1, og glass- og glødeeffekter er fjernet.
Interne merkelapper som `general_news` og «top score» vises som lesbar tekst.
Grensesnittet beholdes på engelsk. Bakgrunn: liten, svak tekst på mørk
bakgrunn og rester av et eldre lyst tema ga dårlig lesbarhet.

## D12 – Nytt grensesnitt for nyhetssiden etter mønster fra lesetjenester

**Vedtatt og implementert 5. oktober 2026. Erstatter oppsettet i D11; temaene beholdes.**
Nyhetssiden er bygget om etter mønster fra nyhetslesere som Feedly, Inoreader
og Ground News: sidemeny med seksjoner og antall saker, søk, emnefilter som
knapper, saker gruppert per dag med kilde, tid, antall kilder og bilde, og en
leserute som åpnes fra høyre slik at listen forblir synlig. Hurtigtaster:
`/` søk, `j`/`k` neste/forrige og `Esc` lukk. Innstillinger er delt i kort
(hente nyheter, legge til kilder, kildeliste, redigering, vedlikehold).
Eksisterende funksjoner og API-er er uendret. Bakgrunn: brukeren ønsket en
moderne og brukervennlig løsning uten hensyn til det tidligere designet.

## Åpne forslag og avklaringer

- **Lyd/NotebookLM:** vurderes senere; ingen automatisk Google-overføring eller
  lydgenerering er valgt eller implementert.
- **Flere land:** konkrete kalendere, API-er og dekningsgrad undersøkes per land
  etter Norge-piloten. Ingen garanti om komplett europeisk dekning.
- **Uttrekksbibliotek:** evaluer Trafilatura mot representative sider i trinn 2.
- **Railway-miljøer:** Railway-prosjektene har autogenererte navn. Hvilket som
  er OWIS produksjon og testmiljø bør navngis og dokumenteres. «Vent på CI» før
  utrulling bør slås på i Railway, og databasekopier bør lagres utenfor volumet.
- **Produksjon:** kode på main bekrefter ikke aktiv rapportplanlegging, kildeoppsett
  eller at siste versjon er rullet ut. Dette må kontrolleres i driftsmiljøet.

## Nye beslutninger

Legg til neste D-nummer med dato, vedtatt/forslag/erstattet, selve valget,
begrunnelse, implementeringsstatus og kilde/PR. Ved omvalg beholdes den gamle
beslutningen med lenke til den nye.
