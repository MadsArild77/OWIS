# Politikk- og regelverkskilder

[Til dokumentasjonsoversikten](DOCUMENTATION.md) · [Kildekonfigurasjon](SOURCE_CONFIGURATION.md)

Satt opp 3. november 2026 for Norge, EU, Storbritannia, Danmark, Tyskland og Nederland.
Kildene ligger i [`owis/core/sources/policy_sources.json`](owis/core/sources/policy_sources.json)
og importeres i **Settings → Regulatory → Import**.

## Status

- **34 organisasjoner og 44 kilder.** 37 er aktive. De 7 pausede kildene er nyttige, men kan ikke leses uten egen adapter (se under).
- **Testet 3. november 2026** med appens egen kildetest (`owis/core/sources/probe.py`), fra en vanlig nettlinje i Norge. Alle 37 aktive kilder ga innhold.
  Railway kan få andre svar. Regjeringen.no har tidligere stoppet oppslag fra Railway med Cloudflare (D25).
- **Importen er prøvd** i en tom testdatabase. Den kan kjøres flere ganger uten å lage duplikater, fordi den slår sammen på stabil ID.
- **Ingen av kildene har innholdstypen `news`.** Derfor havner de ikke i nyhetsstrømmen. Før [oppgave 004](oppgaver/004-innhenting-politikkilder.md)
  er gjort, lagres de bare i registeret og kan testes der. Ingenting hentes automatisk.
- Kildene følger **alt** når organisasjonen er sentral for havvind (Energidepartementet, energi- og miljøkomiteen, DG ENER,
  DESNZ, BSH, KEFM, KGG), og ellers **bare tematreff**. Temaordene står på organisasjonen og arves av kildene.

## Kilder per område

| Område | Aktive kilder | Hentemåte |
|---|---|---|
| **Norge** | Energidepartementet: nyheter (med ministerens ukekalender), kalender, høringer, dokumenter, lover og regler · KLD og NFD: høringer · EØS-notater · Stortinget: lovvedtak, innstillinger, komitéhøringer, Europautvalget, skriftlige spørsmål til energiministeren, saker (API) · Norsk Lovtidend avd. I | RSS (regjeringen.no filtrert på departement og dokumenttype, stortinget.no, lovdata.no), API (data.stortinget.no) |
| **EU** | DG ENER: nyheter · Have your say: energiinitiativer og konsultasjoner (API) · Kommisjonens pressemeldinger · Rådets pressemeldinger · ACER · ENTSO-E · EUR-Lex (Official Journal) | RSS, API |
| **Storbritannia** | DESNZ: nyheter, konsultasjoner, policy-dokumenter · Ofgem · The Crown Estate · NESO · lovforslag i parlamentet | Atom (gov.uk), RSS, HTML-liste |
| **Danmark** | Høringsportalen · Folketinget: saker (API) | Atom, API (oda.ft.dk) |
| **Tyskland** | BMWE: pressemeldinger · Bundesnetzagentur · BSH (havvindarealer) · Bundestag: hib Wirtschaft und Energie | RSS |
| **Nederland** | Internetconsultatie · Tweede Kamer: saker (API) | HTML-liste, API (OData) |

Fire kilder er API-er: Stortinget, Have your say, Folketinget og Tweede Kamer. Appens kildetest viser
«unsupported» for API-er. Det er riktig, for adapterne kommer i [oppgave 005](oppgaver/005-api-adaptere-politikk.md).

## Pauset, med begrunnelse

| Kilde | Hvorfor |
|---|---|
| NVE, Statnett, Havtil | Nyhetslistene bygges med JavaScript, og ingen RSS ble funnet. |
| Europaparlamentet, ITRE | europarl.europa.eu svarer 403 på automatiske oppslag. |
| KEFM, Energistyrelsen | JavaScript-lister. RSS-en til Energistyrelsen var tom. |
| Klimaat en Groene Groei (NL) | JavaScript-liste, og RSS-adressen ble ikke funnet. |

Sakene her dekkes delvis av andre kilder: departementenes egne feeder, Rådet og EUR-Lex for EU-vedtak,
og høringsportalene.

## Ting å vite

- **Overlapp:** Energidepartementets «dokumenter» inneholder også høringene, og Stortingets spørsmål til energiministeren
  hentes allerede av Storting-fanen (D25). Samme URL skal bare lagres én gang.
- **Brede kilder** (EUR-Lex, Kommisjonens og Rådets pressemeldinger, lovforslag i UK, Høringsportalen) gir mange saker per dag.
  Bare tematreff skal lagres fra dem.
- **Stortingssesjonen** står i API-adressen (`2025-2026`). Adapteren bør regne den ut selv.
- **Departementsnavn endres.** Regjeringen.no-feedene bruker departementets nummer (`owner=750` = Energidepartementet).
  Ved regjeringsskifte må nummeret kontrolleres.
