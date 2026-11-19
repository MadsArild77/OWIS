# Svar på 009 – Passordkrav på Railway og databasen ved samtidige skrivinger

## Gjort
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
- Kontroll av kort 004–008 mot ekte kilder er ikke gjort: dette arbeidsmiljøet når ikke
  kildene. Det må gjøres i owis-review eller lokalt.
- Den eksisterende testen for manglende volum setter nå et passord, slik at den
  fortsatt tester volumkontrollen og ikke stopper på passordkontrollen først.

## Testresultat
376 bestått på Python 3.13 (18,6 s) og 3.11 (21,7 s). Fem nye tester: oppstart nektes
uten passord, passord eller bevisst åpning slipper gjennom, WAL og ventetid er satt,
lesing blokkeres ikke av en åpen skriving, og sikkerhetskopien tar med nylige skrivinger.
