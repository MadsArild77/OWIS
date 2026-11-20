# Svar på 010 – Ny morgenrapport, strammere filtre og daglig anbudshenting

## Gjort
- **AI-input:** `brief_input()` legger politikk, hendelser og tidligere dager først og nyhetene sist, med
  kortere sammendrag, innenfor 60 000 tegn. Blir det for langt, faller de lavest rangerte nyhetene ut.
  Klientens øvre grense er hevet fra 24 000 til 60 000 tegn (kallene setter fortsatt sin egen grense;
  eInnsyns prosjektvisning ber om 30 000 og får nå det). Morgenrapporten venter inntil 90 sekunder på svar.
- **Format:** AI-en svarer med `headline`, `in_brief`, `sections` (norway, europe, supply_chain, policy),
  `watch` og trender. Hver sak har «So what», og politikksaker lenker til kilden. `deadlines` (frister de neste
  14 dagene) og `new_tenders` (nye anbud siste døgn) bygges fra dataene. Visningen er ny for rapporter som har
  `deadlines`; eldre rapporter vises som før. Alle saker, politikkutsikten, overvåkede kilder og dekning er
  sammenfoldet nederst. Kopier-knappen følger det nye formatet.
- **Advarsler:** én linje per type i stedet for én per søkegruppe.
- **Politikksøket** kjøres mandager (`OWI_POLICY_SEARCH_WEEKDAYS=0`), globale par roteres etter ISO-uke.
- **Politikktemaer:** `policy_sources.json` er oppdatert (68 organisasjoner). Produksjonen endres først når
  `oppgaver/010-politikktemaer-import.json` importeres i Settings → Regulatory → Import. Fila inneholder bare
  organisasjonene. `oppgaver/010-politikktemaer-tilbake.json` setter dem tilbake.
- **MAV-profilen** krever havvindord i teksten og utelukker HR, nettsider, programvare, avfall, catering og turisme.
- **Anbud** hentes og behandles kl. 04:30 Oslo-tid (`owis/modules/opportunities/processing/schedule.py`), én gang
  per dag med krav i databasen. Før hentingen tas anbud som ikke lenger passer profilene ut av lista (unntatt lagrede).

- **COWI-profil** (D35): ingeniør- og rådgivningsanbud innen havvind, nett, havn og miljø/konsesjon i Norden og
  Nordsjøen. Profiler kan nå begrenses til land med `countries`.

## Slik kan Mads se det
Etter utrulling: neste morgenrapport (06:00) har det nye formatet, eller trykk Generate / refresh. Opportunities
oppdateres hver morgen etter 04:30, og de urelevante MAV-treffene forsvinner ved første kjøring. Politikklista
blir kortere når importfila er lastet inn.

## Usikkert eller ikke gjort
- Ikke rullet ut. Det nye formatet er sett i lokal Chrome med testdata (skrivebord, mobil og mørkt tema), ikke med
  en ekte AI-respons; kvaliteten på «So what» må vurderes på de første rapportene.
- Politikktemaene er ikke importert i produksjon. Jeg fikk ikke sammenlignet produksjonens oppsett med fila
  (forbindelsen til Edge falt ut). Har Mads endret disse organisasjonene i Settings, overskriver importen det.
- Simuleringen av temaene brukte et grovt ordsøk for «relevant»; tallene (624 → 226, 25 % → 66 %) er anslag.

## Testresultat
405 bestått på Python 3.13 og 3.11. Nye tester: AI-input med full størrelse og kutt, sammenslåtte advarsler,
seksjoner og politikklenker, frister og nye anbud, ukentlig søk og rotasjon, MAV mot fem ekte feiltreff og to
riktige treff, opprydding som beholder lagrede anbud, daglig kjøring etter 04:30, og COWI-profilen mot fem riktige og fem gale anbud.
