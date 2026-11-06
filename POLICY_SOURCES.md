# Politikk- og regelverkskilder

[Til dokumentasjonsoversikten](DOCUMENTATION.md) · [Kildekonfigurasjon](SOURCE_CONFIGURATION.md)

Satt opp 3. november 2026. Kildene ligger i [`owis/core/sources/policy_sources.json`](owis/core/sources/policy_sources.json)
og importeres i **Settings → Regulatory → Import**.

## Status

- **78 organisasjoner og 89 kilder i 30 land og EU.** 58 kilder er aktive. De 31 pausede kildene er viktige, men kan ikke leses uten egen adapter (se under).
- **14 nye jurisdiksjoner utenfor Europa** følger med i filen: Japan, Sør-Korea, Taiwan, Australia, Filippinene, Vietnam, India, USA,
  Brasil, Colombia, Tyrkia, Saudi-Arabia, Oman og De forente arabiske emirater. De har gruppene `Asia-Pacific`, `Americas` og `Middle East`.
- **Testet 3. november 2026** med appens egen kildetest (`owis/core/sources/probe.py`) fra en vanlig nettlinje i Norge. Alle aktive kilder ga innhold.
  Railway kan få andre svar. Regjeringen.no har tidligere stoppet oppslag fra Railway (D25).
- **Importen er prøvd** to ganger etter hverandre i en tom testdatabase. Den lager ikke duplikater, fordi den slår sammen på stabil ID.
- **Ingen av kildene har innholdstypen `news`.** Derfor havner de ikke i nyhetsstrømmen. Før [oppgave 004](oppgaver/004-innhenting-politikkilder.md)
  ble gjort, ble de bare lagret i registeret. RSS/Atom og HTML-lister hentes nå av en egen bakgrunnsjobb
  ved `OWI_FETCH_HOURS`, med kildeintervall, temafilter og pauseregler. Postene vises under
  **Policy & regulation → From monitored sources** og tas med i morgenrapporten. Kort 005 legger til API-adaptere for Have your say, Folketinget og Tweede Kamer.
- Kildene følger **alt** når organisasjonen er sentral for havvind (for eksempel Energidepartementet, DG ENER, DESNZ, BSH, BOEM og Litauens
  energidepartement), og ellers **bare tematreff**. Temaordene står på organisasjonen på landets eget språk og arves av kildene.

## Kilder per område

| Område | Aktive kilder | Hentemåte |
|---|---|---|
| **Norge** | Energidepartementet: nyheter (med ministerens ukekalender), kalender, høringer, dokumenter, lover og regler · KLD og NFD: høringer · EØS-notater · Stortinget: lovvedtak, innstillinger, komitéhøringer, Europautvalget, spørsmål til energiministeren, saker (API) · Norsk Lovtidend | RSS, API |
| **EU** | DG ENER · Have your say (API) · Kommisjonen · Rådet · ACER · ENTSO-E · EUR-Lex | RSS, API |
| **Nordsjøen** | UK: DESNZ (nyheter, konsultasjoner, policy), Ofgem, The Crown Estate, NESO, lovforslag · DK: Høringsportalen, Folketinget (API) · DE: BMWE, Bundesnetzagentur, BSH, Bundestag · NL: Internetconsultatie, Tweede Kamer (API) | Atom, RSS, HTML-liste, API |
| **Østersjøen** | SE: regjeringens pressemeldinger, näringsutskottet, Svenska kraftnät (2), Havs- och vattenmyndigheten · PL: URE, PSE · EE: Kliimaministeerium, Riigikogu · LV: Ekonomikas ministrija, Saeima · LT: Energetikos ministerija | RSS, HTML-liste, API |
| **Flytende havvind, Sør-Europa** | FR: departementets pressemeldinger og nyheter, CRE · ES: MITECO, CNMC · PT: DGEG · IT: Gazzetta Ufficiale | RSS, HTML-liste |
| **Globalt** | USA: Federal Register for BOEM · Vietnam: MOIT | RSS, HTML-liste |

Seks kilder er API-er: Stortinget, Have your say, Folketinget, Tweede Kamer, Eduskunta og Sejm.
Have your say, Folketinget og Tweede Kamer har adaptere og forhåndsvisning av inntil fem poster.
Stortinget hoppes over med «Collected by the Storting tab (D25)». Eduskunta (Finland) og Sejm (Polen) er pauset i importfilen til de får egen adapter;
API-er uten adapter gir «No adapter for this API» i kjøringsloggen.

Adapterne leser høyst 500 poster per kjøring fra registerets endepunkt. Folketinget og Tweede Kamer
leses i synkende endringsdato til 30-dagersgrensen, med vanlig temafilter. Folketingets svar mangler
normalt samlingskoden som trengs for en sikker ft.dk-lenke; da brukes API-postens adresse.
Have your say leser alle sider innen grensen, uten temafilter: åpne perioder beholdes uansett alder,
andre initiativer bare når nyeste periodedato er innen 30 dager. Frist og type oppdateres også på eksisterende poster.
Åpne konsultasjoner vises utover 30 dager, med frist og varselfarge innen sju dager. Consultations
sorterer etter nærmeste åpne frist; morgenrapporten prioriterer frister innen 14 dager og inkluderer `deadline`.
Eksempelsvar hentet 6. november 2026 er lagret som avgrensede utdrag uten personopplysninger i
`owis/tests/fixtures/policy_*.json`. Testene bruker bare lokale svar.

## Pauset, med begrunnelse

| Kilde | Hvorfor |
|---|---|
| NVE, Statnett, Havtil, KEFM, Energistyrelsen, Energimyndigheten, Fingrid, KGG (NL) | Nyhetslistene lastes med JavaScript, og ingen RSS ble funnet. |
| Europaparlamentet (ITRE) | Svarer 403 på automatiske oppslag. |
| Finland: valtioneuvosto.fi, TEM, Energiavirasto, lausuntopalvelu.fi | Svarer 403. |
| Metsähallitus, Polens klimadepartement, Portugals regjering | Ingen RSS og ingen lesbar nyhetsliste. |
| Éoliennes en mer (FR), HEREMA og YPEN (GR), MASE (IT) | Viktige for flytende havvind, men svarer 403 eller viser bare menylenker. |
| Japan (METI), Sør-Korea, Taiwan, Australia, Brasil, India, Filippinene, Colombia, Tyrkia, Saudi-Arabia, Oman, De forente arabiske emirater | Svarer 403, lastes med JavaScript, får tidsavbrudd eller nås ikke fra Norge. |

De pausede markedene inngår nå i den søkebaserte politikkdelen, avgrenset til de offisielle domenene
i `governance.py` ([oppgave 006](oppgaver/006-sokebasert-politikk-globalt.md)). EU-vedtak dekkes av Rådet og EUR-Lex.
De åtte opprinnelige søkegruppene kjøres daglig. Seks nye grupper roterer i faste par:
flytende havvind i Sør-Europa/Norden, Baltikum/Asia-Pacific og Americas/Middle East.
Dagnummer i året modulo 3 velger par 0, 1 eller 2. Det gir to ekstra søk per rapport,
60 på 30 dager ved daglig kjøring. Kjente kommende kilder fra forrige rapport kontrolleres
også utenom søkedagen uten søkeforbruk; uten slike kilder vises `not_scheduled` uten advarsel.
Dekningen avhenger av søketreff og lesbar tekst; blokkeringer er ikke løst med egne adaptere.
Registeret og de pausede kildenes status er uendret.

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
