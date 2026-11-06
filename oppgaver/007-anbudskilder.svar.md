# Svar på 007 – anbudskilder

Implementert på `codex/007-anbudskilder`. Grenen ble beholdt som avtalt.
Ingen push, sammenslåing eller kjøring mot produksjonsdata er gjort.

## Hva som er gjort

- Rettet Doffin og Verdensbanken til de åpne adressene i kortet.
- Lagt til Find a Tender, Contracts Finder og CanadaBuys, med normalisering og
  behandling gjennom eksisterende profiler. UK-kildene deler `ocid` som identitet.
- Lagt til OWIS-profilen «Offshore wind market», alle oppgitte søkeord og negative
  ord, tom kvalifikatorliste og kategori «Offshore Wind». OWIS er med i standarden
  sammen med AGR/MAV. Eksisterende profiler med kvalifikatorer virker fortsatt.
- Frist fra kilden går foran tekstens første dato. Fristens opprinnelse, anslått
  verdi og valuta lagres. Databasemigrasjonen er gjentakbar og endrer ikke gamle data.
- Lagret kjøringsstatus per kilde og laget `GET /api/opportunities/sources` med de
  seks avtalte visningsnavnene og statustekstene.
- FRA/POL er lagt til sekundærmarkedene; DEU/NLD var der allerede. GBR er fortsatt
  primærmarked. Poengberegningen er ellers uendret.
- Oppdatert konfigurasjonseksempelet, Opportunities-dokumentasjonen, statuslinjen
  og D28 i beslutningsloggen.

## Hvordan Mads kan se det

Etter lokal oppstart kan `http://127.0.0.1:8000/api/opportunities/sources` åpnes.
Før første kjøring står alle som `Not run yet`. En kjøring gjennom den eksisterende
Opportunities-funksjonen oppdaterer tidspunkt og antall, eller viser `Failed: ...`.
Nye treff vises på den eksisterende Opportunities-siden når de passer en aktiv profil.
Nytt grensesnitt for kildeinformasjon, verdi og fristens opprinnelse kommer i kort 008;
HTML, tema og Notion-eksport er ikke endret.

Hvis miljøet allerede setter `OWI_OPP_ENABLED_SOURCES` eller
`OWI_OPP_ACTIVE_PROFILES`, må de eksisterende verdiene få de nye kildene/OWIS lagt
inn. Miljøvariabler overstyrer kode-standardene. Jeg har ikke åpnet eller endret
noen hemmelig konfigurasjon; bare den sporede malen `owis/.env.example` er oppdatert.

## Kontroll av offentlige svar og parametre

Små, offentlige oppslag ble gjort 5. november 2026 uten nøkler. Eksempelfilene i
`owis/tests/fixtures/opportunity_*` er utdrag av disse svarene. Kontaktpersoner,
kontaktinformasjon og fritekst som kunne inneholde dette er utelatt fra fixtures.
Tester som trenger spesielle kombinasjoner endrer kopier i minnet, ikke kildedata.

**Verdensbanken:** `GET https://search.worldbank.org/api/v2/procnotices` med
`format=json`, `rows=100`, `os`, `qterm`, `srt=noticedate`, `order=desc`.
`q` og `strdate` ble kontrollert og viste seg å bli ignorert. Sortering ble
kontrollert både stigende og synkende. Henteren følger `total`/offset og stopper
når de datosorterte svarene passerer startdatoen. Dato kontrolleres også lokalt.
Felt: `bid_description`, `project_name`, `contact_organization`, `noticedate`,
`submission_date`, `submission_deadline_date` og `project_ctry_name`.
Lenken går til `/en/projects-operations/procurement-detail/<id>`.
Ingen strukturert anslått verdi/valuta ble funnet i svarene; de settes til tomt,
og beløp fra prosjektbudsjett eller fritekst brukes ikke som anbudsverdi.

**Doffin:** `POST https://api.doffin.no/webclient/api/v2/search-api/search` med
`page`, `numHitsPerPage=100`, `sortBy=PUBLICATION_DATE_DESC` og `facets`:

```json
{
  "publicationDate": {"from": "YYYY-MM-DD", "to": null},
  "type": {"checkedItems": ["COMPETITION", "ANNOUNCEMENT_OF_COMPETITION", "PRE_ANNOUNCEMENT"]}
}
```

CPV-søket legger til `cpvCodesId: {"checkedItems": [...]}` og sender ikke
`searchString`. Egne ordsøk bruker `searchString` for kvalifikatorer og profilord,
inkludert havvindordene. Et bredt søk uten `searchString` ble også undersøkt.
Doffins egen offentlige JavaScript-kode bekreftet parameterstrukturen, og faktiske
svar bekreftet datofiltreringen og de aktive typefiltrene.
`type`/`allTypes`, `publicationDate`/`issueDate`, `deadline` og
`estimatedValue.amount`/`estimatedValue.currencyCode` brukes. De undersøkte
`hits` har ikke CPV per notis: søkets CPV-fasetter er aggregater og legges derfor
ikke på hvert treff. `cpvCodes` beholdes dersom kilden leverer det på treffet.
Lenker bruker alltid `https://doffin.no/notices/<id>`.
Type og dato sjekkes også lokalt. Avsluttede/kansellerte/tildelte treff tas ikke inn.
Ved Doffins grense for tilgjengelige treff rapporteres feil, ikke en komplett henting.

**TED:** ber nå om `deadline-receipt-tender-date-lot`, `deadline-receipt-request`,
`estimated-value-proc` og `estimated-value-cur-proc` i tillegg til eksisterende felt.
Feltene ble kontrollert i ekte svar. TEDs `FT ~ "offshore wind"`/`havvindpark` ble
også kontrollert; OWIS-ordene inngår som alternativ til CPV-søket. FRA/POL inngår
nå i landene som hentes. Ved flere delkontraktfrister brukes den tidligste som
varselpunkt. Prosedyreverdien brukes; delkontraktverdier summeres ikke vilkårlig.

**UK:** begge OCDS-endepunktene i kortet brukes. Find a Tender får
`updatedFrom`/`updatedTo` (sekundpresisjon) og Contracts Finder får
`publishedFrom`/`publishedTo`. `limit=100`, deretter følges `links.next` til slutt.
Henteren leser alle stadier og velger siste release per `ocid` før statusfilteret;
dermed vinner en nyere avslutning over en eldre aktiv release i samme svarsett.
Bare `tender.status=active/planned`, eller planleggingsmeldinger uten status, tas
inn. Samme `ocid` på tvers av kildene lagres én gang (FTS prioriteres ved overlapp).
Ingen sammenslåing på titler eller omtrentlige treff.
Dokumentasjon: [Find a Tender](https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages)
og [Contracts Finder](https://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Published-Notice-OCDS-Search).

**CanadaBuys:** den oppgitte åpne CSV-en leses som UTF-8 med eventuell BOM.
Engelske kolonner brukes: `title-titre-eng`,
`tenderDescription-descriptionAppelOffres-eng`,
`contractingEntityName-nomEntitContractante-eng` og `noticeURL-URLavis-eng`.
Identitet: `referenceNumber-numeroReference`. Publisering:
`publicationDate-datePublication`. Frist:
`tenderClosingDate-appelOffresDateCloture`. Bare `Open` og datoer i vinduet tas med.
CSV-en har ikke strukturert verdi/valuta eller CPV; disse fylles ikke med gjetninger.

## Valg og begrensninger

- UK/Canada bruker starten av siste **vellykkede** kjøring som neste startpunkt,
  så tiden innhentingen tok ikke blir et hull. Første gang brukes antall dager
  fra innstillingen. Et eksplisitt `days_back` gir et nytt manuelt tilbakeblikk.
- Canada har dato uten klokkeslett og inkluderer hele startdagen. Duplikater
  stoppes av lagringen. Feil flytter ikke startpunktet.
- `fetched` teller kilderader før filtrering, også overlapp mellom søk. `new`
  teller nye rårader. `filtered` teller dato/type/profil-avvisning og duplikater.
  En ny rårad som profilen avviser, inngår i både `new` og `filtered`.
- Kjente landnavn fra Verdensbanken mappes til landkoder. Ukjente navn får tom
  kode fremfor en oppdiktet landkode.
- Ingen faktisk produksjonsinnhenting, AI, betalt søk eller Notion-eksport er kjørt.
- Nettlesersjekk er ikke kjørt. API-et er kontrollert med isolert FastAPI-testklient;
  ingen oppstart av appen mot private data var nødvendig. Kortet endrer ikke UI.

## Tester

- Første målrettede kjøring: 29 bestått.
- Utvidet målrettet kjøring: 34 bestått. én avhengighetsadvarsel fra Starlette/AnyIO.
- Hele testsettet: 310 passed (kjørt av Claude, siden Codex-kvoten tok slutt rett før commit).
- Testene bruker fixtures og mockede HTTP-svar, ikke nett. Migrasjon, lagring,
  API-status, feilhåndtering, sideinndeling, UK-duplikater, kildefrist og begge
  kvalifikatorregler er dekket.
