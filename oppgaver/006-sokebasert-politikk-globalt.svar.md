# Svar på 006 – Søkebasert politikk globalt

## Gjort

- Lagt til de seks kildegruppene og søkeordene fra kortet, etter de åtte eksisterende.
- De nye gruppene roterer i faste par etter dagnummer i året modulo 3:
  0 = Sør-Europa/Norden, 1 = Baltikum/Asia-Pacific, 2 = Americas/Middle East.
  De åtte eksisterende gruppene søkes først hver dag.
- Kjente kommende kilder fra forrige rapport kontrolleres også utenom søkedagen,
  med eksisterende grense på to per gruppe og uten søkeforbruk. Uten kjente kilder
  får gruppen `not_scheduled`, uten advarsel.
- Prompten presiserer at jurisdiksjonene i valgt region skal dekkes. Regelen om
  EU-rett og norsk gjennomføring og øvrig validering er beholdt.
- Oppdatert sortering, dekningsmerknad, MORNING_REPORT.md, POLICY_SOURCES.md,
  D32 i DECISIONS.md og PROJECT_STATUS.md.
- Regionvelgeren hadde allerede Asia-Pacific, Americas og Middle East fra tidligere kort.

## Slik ser Mads det

Etter at koden er tatt i bruk og en ny morgenrapport er laget med vanlig søke- og
AI-oppsett, viser **Morning report** den utvidede dekningsmerknaden og status for
alle kildegruppene. Nye funn får regionen Asia-Pacific, Americas eller Middle East
og vises etter de europeiske regionene. Regionvalgene finnes under **Policy & regulation**.
Tre rapportdager trengs for at alle seks nye grupper skal få hver sin søkedag.

## Søkeforbruk og valg

Mocket kjøring bekrefter **10 søk per rapport: 8 eksisterende + 2 ekstra**.
Ved én rapport daglig betyr det **60 ekstra på 30 dager**, eller 56–62 for en
kalendermåned. Ekstra manuelle rapportkjøringer gir også inntil to ekstra søk hver.
Uten oppsett eller med oppbrukt budsjett blir faktisk forbruk lavere. Alle søk
bruker fortsatt `purpose='policy'` og eksisterende D17-grenser.

Dagnummer er 1-basert, slik datoens dagnummer normalt er; 1. januar velger derfor
par 1. Ved årsskifte følger rotasjonen det nye årets dagnummer, som kortets
modulo-regel tilsier. Eksisterende kildegrenser, URL-deduplisering og håndtering
av manglende fulltekst er beholdt.

## Kontroll og begrensninger

- Nye tester bruker mocket søk, nettsidetekst og AI. De dekker alle tre nye regioner,
  avvisning av falskt domene, faste par, søkerekkefølge, skuddår/årsskifte,
  `not_scheduled` uten advarsel, gjenkontroll uten søk, sortering og dekningsmerknad.
- Første enkelttestkjøring avdekket feil dato i tre nye tester; datoene ble rettet,
  og alle tre bestod ved ny kjøring. De øvrige 31 enkelttestene bestod første gang.
- Hele testsettet: 359 passed (kjørt av Claude, siden Codex-kvoten tok slutt rett før commit).
- Nettlesersjekk er ikke utført. Kortet krever ingen egen nettlesersjekk, og
  regionvalgene er kontrollert i eksisterende HTML. Ingen grensesnittfiler er endret.
- Ingen ekte søk, betalte AI-kall, produksjonsinnhenting eller endring av kilderegisteret.
  Søkebasert dekning avhenger fortsatt av treff og lesbar tekst hos kildene.
