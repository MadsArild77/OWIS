# Politikk- og regelverkskilder

[Til dokumentasjonsoversikten](DOCUMENTATION.md) · [Kildekonfigurasjon](SOURCE_CONFIGURATION.md)

Satt opp 3. november 2026. Kildene ligger i [`owis/core/sources/policy_sources.json`](owis/core/sources/policy_sources.json)
og importeres i **Settings → Regulatory → Import**.

## Status

- **78 organisasjoner og 89 kilder i 30 land og EU.** 60 kilder er aktive. De 29 pausede kildene er viktige, men kan ikke leses uten egen adapter (se under).
- **14 nye jurisdiksjoner utenfor Europa** følger med i filen: Japan, Sør-Korea, Taiwan, Australia, Filippinene, Vietnam, India, USA,
  Brasil, Colombia, Tyrkia, Saudi-Arabia, Oman og De forente arabiske emirater. De har gruppene `Asia-Pacific`, `Americas` og `Middle East`.
- **Testet 3. november 2026** med appens egen kildetest (`owis/core/sources/probe.py`) fra en vanlig nettlinje i Norge. Alle aktive kilder ga innhold.
  Railway kan få andre svar. Regjeringen.no har tidligere stoppet oppslag fra Railway (D25).
- **Importen er prøvd** to ganger etter hverandre i en tom testdatabase. Den lager ikke duplikater, fordi den slår sammen på stabil ID.
- **Ingen av kildene har innholdstypen `news`.** Derfor havner de ikke i nyhetsstrømmen. Før [oppgave 004](oppgaver/004-innhenting-politikkilder.md)
  er gjort, lagres de bare i registeret og kan testes der.
- Kildene følger **alt** når organisasjonen er sentral for havvind (for eksempel Energidepartementet, DG ENER, DESNZ, BSH, BOEM og Litauens
  energidepartement), og ellers **bare tematreff**. Temaordene står på organisasjonen på landets eget språk og arves av kildene.

## Kilder per område

| Område | Aktive kilder | Hentemåte |
|---|---|---|
| **Norge** | Energidepartementet: nyheter (med ministerens ukekalender), kalender, høringer, dokumenter, lover og regler · KLD og NFD: høringer · EØS-notater · Stortinget: lovvedtak, innstillinger, komitéhøringer, Europautvalget, spørsmål til energiministeren, saker (API) · Norsk Lovtidend | RSS, API |
| **EU** | DG ENER · Have your say (API) · Kommisjonen · Rådet · ACER · ENTSO-E · EUR-Lex | RSS, API |
| **Nordsjøen** | UK: DESNZ (nyheter, konsultasjoner, policy), Ofgem, The Crown Estate, NESO, lovforslag · DK: Høringsportalen, Folketinget (API) · DE: BMWE, Bundesnetzagentur, BSH, Bundestag · NL: Internetconsultatie, Tweede Kamer (API) | Atom, RSS, HTML-liste, API |
| **Østersjøen** | SE: regjeringens pressemeldinger, näringsutskottet, Svenska kraftnät (2), Havs- och vattenmyndigheten · FI: Eduskunta (API) · PL: URE, PSE, Sejm (API) · EE: Kliimaministeerium, Riigikogu · LV: Ekonomikas ministrija, Saeima · LT: Energetikos ministerija | RSS, HTML-liste, API |
| **Flytende havvind, Sør-Europa** | FR: departementets pressemeldinger og nyheter, CRE · ES: MITECO, CNMC · PT: DGEG · IT: Gazzetta Ufficiale | RSS, HTML-liste |
| **Globalt** | USA: Federal Register for BOEM · Vietnam: MOIT | RSS, HTML-liste |

Seks kilder er API-er: Stortinget, Have your say, Folketinget, Tweede Kamer, Eduskunta og Sejm. Appens kildetest viser «unsupported» for API-er.
Det er riktig, for adapterne kommer i [oppgave 005](oppgaver/005-api-adaptere-politikk.md). Eduskunta og Sejm er ikke med i 005 ennå.

## Pauset, med begrunnelse

| Kilde | Hvorfor |
|---|---|
| NVE, Statnett, Havtil, KEFM, Energistyrelsen, Energimyndigheten, Fingrid, KGG (NL) | Nyhetslistene lastes med JavaScript, og ingen RSS ble funnet. |
| Europaparlamentet (ITRE) | Svarer 403 på automatiske oppslag. |
| Finland: valtioneuvosto.fi, TEM, Energiavirasto, lausuntopalvelu.fi | Svarer 403. |
| Metsähallitus, Polens klimadepartement, Portugals regjering | Ingen RSS og ingen lesbar nyhetsliste. |
| Éoliennes en mer (FR), HEREMA og YPEN (GR), MASE (IT) | Viktige for flytende havvind, men svarer 403 eller viser bare menylenker. |
| Japan (METI), Sør-Korea, Taiwan, Australia, Brasil, India, Filippinene, Colombia, Tyrkia, Saudi-Arabia, Oman, De forente arabiske emirater | Svarer 403, lastes med JavaScript, får tidsavbrudd eller nås ikke fra Norge. |

De pausede markedene skal dekkes av den søkebaserte politikkdelen. Den søker på offisielle domener per region
([oppgave 006](oppgaver/006-sokebasert-politikk-globalt.md)). EU-vedtak dekkes av Rådet og EUR-Lex.

## Ting å vite

- **Overlapp:** Energidepartementets «dokumenter» inneholder også høringene, og Stortingets spørsmål til energiministeren
  hentes allerede av Storting-fanen (D25). Samme URL skal bare lagres én gang.
- **Brede kilder** (EUR-Lex, Kommisjonen, Rådet, lovforslag i UK, Høringsportalen, CNMC, Gazzetta Ufficiale, Sveriges regjering) gir mange
  saker per dag. Bare tematreff skal lagres fra dem.
- **Lang historikk:** Svenska kraftnät og URE har tusenvis av poster i feeden. Grensen på 30 dager ved første henting er viktig.
- **Valgperioder i adressene:** Stortinget (`2025-2026`) og Sejm (`term10`). Adapterne bør regne dem ut selv.
- **Departementsnavn endres.** Regjeringen.no-feedene bruker departementets nummer (`owner=750` = Energidepartementet).
  Ved regjeringsskifte må nummeret kontrolleres.
- **Ikke med ennå:** Irland, Belgia, Kina, Canada, Chile, Sør-Afrika og Marokko. De kan legges til på samme måte.
