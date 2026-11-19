# Svar på 009 – Passordkrav på Railway og databasen ved samtidige skrivinger

## Gjort
- Have your say hentes nå 25 saker om gangen i stedet for 100, slik at EU svarer innen
  tidsgrensen. De andre API-ene henter fortsatt 100 om gangen.
- `check_hosted_access()` erstatter advarselen ved oppstart. På Railway uten
  `OWI_ACCESS_PASSWORD` stopper oppstarten med: «Railway requires OWI_ACCESS_PASSWORD
  before starting OWIS». `OWI_ALLOW_OPEN_ACCESS=true` åpner bevisst og logger advarselen
  som før. Lokalt (uten `RAILWAY_ENVIRONMENT_ID`) er appen uendret.
- `get_conn()` venter nå opptil 30 sekunder på lås (før: fem). `init_db()` slår på
  WAL-modus, som lagres i databasefilen.
- Statusfilen er rettet: kort 002–008 står nå som flettet til main, innlogging som aktiv,
  og Opportunities har merknad om at anbud bare hentes ved Fetch tenders.
  D29–D32 er rettet på samme måte, og D33 er lagt til.

## Slik kan Mads se det
Ingenting endres i appen så lenge passordet er satt. Etter utrulling ligger to nye
filer ved siden av databasen på volumet: `owi.db-wal` og `owi.db-shm`. De hører til
databasen og skal ikke slettes mens appen kjører.

## Usikkert eller ikke gjort
- Ikke rullet ut eller kontrollert på Railway. Fjernes passordet i et miljø, feiler neste
  utrulling helsesjekken, og Railway beholder forrige versjon.
- Testmiljøet owis-review var åpent uten innlogging og kjørte en gammel versjon. Mads sletter det.
- Den eksisterende testen for manglende volum setter nå et passord, slik at den
  fortsatt tester volumkontrollen og ikke stopper på passordkontrollen først.

## Testresultat
377 bestått på Python 3.13 (18,7 s) og 3.11 (21,7 s). Seks nye tester: Have your say ber om små sider, oppstart nektes
uten passord, passord eller bevisst åpning slipper gjennom, WAL og ventetid er satt,
lesing blokkeres ikke av en åpen skriving, og sikkerhetskopien tar med nylige skrivinger.

## Kontroll av produksjon 20. november 2026

Lest i nettleser og via API på owis-web-production (bare lesing, ingen innhenting startet):

- **Nyheter og morgenrapport:** virker. Morgenrapporten kom før kl. 07 på 27 av 30 dager
  (6. og 7. november var forsinket). 100–220 nye artikler på hverdager. 37 % av artiklene
  er havvind eller beslektet. 14 kilder har vært stille i sju dager, blant dem én med
  navnet `"` som ser ut som en feilregistrering.
- **Søkekvote:** 615 av 1000 brukt 19. november; den automatiske fordelingen holder.
- **Politikk (kort 004–006):** 91 kilder, 624 saker, siste henting 19. november. 32 kilder er
  pauset med vilje (blant dem NVE, Statnett og Havtil, som krever JavaScript). Grovt anslått
  gjelder bare én av fem av de siste sakene vind, nett, hydrogen eller CCS. Temaene «energi»
  og «energie» slipper inn blant annet danske avgiftslover, og Riksdagens næringsutskott står
  for 40 av de siste 100 sakene.
- **Have your say (kort 005):** hadde feilet 23 ganger på rad på grunn av tidsavbrudd, så ingen
  frister var registrert. EU svarer på 14 s for 100 saker og 4 s for 25. Rettet i 009
  (`HYS_PAGE_SIZE = 25`). Kommisjonens pressemeldinger feiler også på tidsavbrudd
  (38 ganger); ikke rettet.
- **Opportunities (kort 007–008):** siden, filtrene og lesepanelet virker i nettleseren, uten
  JavaScript-feil. Siste behandling av anbud var 6. november: anbud hentes bare ved
  Fetch tenders. Bare TED, UK Find a Tender og Verdensbanken har gitt treff. Flere
  MAV-treff er urelevante (merkevarestrategi, brannvesen, HR-tjenester).
