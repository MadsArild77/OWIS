# 005 – API-adaptere for politikkildene: Have your say, Folketinget og Tweede Kamer

> Gjøres etter 004. Bygger på samme tabell og visning.

## Mål
De tre API-kildene i registeret hentes inn og vises i «From monitored sources» som de andre politikkildene. EU-konsultasjoner viser når fristen for tilbakemelding går ut.

## Hvorfor
EU-kommisjonens konsultasjoner (Have your say) er de viktigste EU-fristene for havvind og nett, og Folketinget og Tweede Kamer har ingen brukbar RSS. De har åpne JSON-API-er som er testet og virker, se [POLICY_SOURCES.md](../POLICY_SOURCES.md).

## Ferdig når
- [ ] Kilder med `method: api` hentes av en adapter valgt etter vertsnavnet i URL-en:
  - `ec.europa.eu` + `brpapi/searchInitiatives` → **Have your say**
  - `oda.ft.dk` → **Folketinget**
  - `gegevensmagazijn.tweedekamer.nl` → **Tweede Kamer**
  - `data.stortinget.no` → **ingen henting**. Storting-fanen (D25) henter allerede dette. Kjøringsloggen viser «Collected by the Storting tab (D25)».
  - Ukjent API-vert gir en tydelig feil i kjøringsloggen («No adapter for this API»), ikke krasj.
- [ ] **Have your say:** én post per initiativ. Tittel = initiativets korte tittel, lenke = initiativets offentlige side på `ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/<id>`, type `consultation` når en tilbakemeldingsperiode er åpen, ellers `regulation`. Fristen (slutt på åpen periode) lagres i en ny kolonne `deadline` i `policy_items`.
- [ ] **Folketinget:** saker (`Sag`) oppdatert siste 30 dager. Tittel = `titel`, dato = `opdateringsdato`, lenke til saken på ft.dk der API-et gir nok til det, ellers til API-posten. Temafilteret fra 004 brukes.
- [ ] **Tweede Kamer:** saker (`Zaak`) endret siste 30 dager. Tittel = `Onderwerp` (eventuelt `Titel`), dato = `GewijzigdOp`. Temafilteret fra 004 brukes.
- [ ] Hver adapter blar i sidene til den når 30 dager tilbake, men høyst 500 poster per kjøring.
- [ ] I «From monitored sources» vises fristen på raden som **«Deadline 14 Nov»**. Når fristen er innen 7 dager, vises den med samme varselfarge som temaet bruker ellers. Typeknappen **Consultations** sorterer åpne konsultasjoner etter frist, nærmeste først.
- [ ] Morgenrapportens `monitored_policy` tar med `deadline`, og konsultasjoner med frist innen 14 dager kommer først.
- [ ] Appens kildetest (`probe.preview`) viser de fem første postene for disse API-ene i stedet for «unsupported».
- [ ] `pytest owis/tests -q` er grønn. Testene bruker lagrede eksempelsvar fra hvert API som fixtures (hentet én gang manuelt, uten personopplysninger), aldri nettverk.
- [ ] `POLICY_SOURCES.md` og `PROJECT_STATUS.md` er oppdatert.

## Design (bestemt av Claude – ikke endre)
- Datoformat i listen: `14 Nov` i inneværende år, ellers `14 Nov 2027`.
- Ingen AI-kall. Ingen ny visning utover fristen og sorteringen over.
- Kildens URL i registeret er utgangspunktet. Adapteren kan legge til side- og datoparametre, men ikke bytte endepunkt.

## Filer som kan endres
- `owis/modules/policy/` (adaptere og lagring fra 004)
- `owis/core/sources/probe.py` (forhåndsvisning for API-adapterne)
- `owis/modules/news/processing/morning.py` (bare `deadline` og sorteringen)
- Visningen av «From monitored sources» (der 004 la den)
- `owis/tests/test_policy_api_adapters.py` og `owis/tests/fixtures/policy_*.json` (nye)
- `POLICY_SOURCES.md`, `PROJECT_STATUS.md`

## Ikke rør
- `owis/core/sources/policy_sources.json` og `models.py`.
- `owis/modules/einnsyn/` (Storting-fanen fortsetter som før).

## Tips
- Have your say: svaret har `initiativeResultDtoPage.content[]` med blant annet `id`, `shortTitle`, `initiativeStatus` og tilbakemeldingsperioder. Undersøk et ekte svar før du velger felt.
- Folketinget og Tweede Kamer er OData: `$top`, `$skip`, `$orderby` og `$filter` på dato fungerer.

## Utenfor oppgaven
- Å slå sammen Storting-fanen (D25) og denne innhentingen.
- Kobling av konsultasjoner til nyhetssaker.
