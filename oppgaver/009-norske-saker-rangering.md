# 009 – Riktig rangering av norske energisaker

> Uavhengig av andre åpne kort. Rør bare ordlistene i `signal.py` og testene.

## Mål
Norske saker om havvind, kraft og nett får riktig poengsum og havner ikke nederst på nyhetssiden. Eksempel: «SeaTwirl vil overta testplassen etter TetraSpar på METCentre» skal vises som havvind (Offshore wind), ikke som «Other energy».

## Hvorfor
19. november 2026 hentet Energiwatch 28 saker uten feil (status grønn), men mange av dem fikk lav poengsum. Energiwatch sender bare overskrift og én setning fordi resten er bak betalingsmur, og da finner ordlistene i `signal.py` for lite. Claude kjørte dagens feed (30 saker) gjennom `score_signal` med ordene i dette kortet lagt inn. 11 saker ble flyttet riktig:

| Overskrift | Før | Etter |
|---|---|---|
| SeaTwirl vil overta testplassen etter TetraSpar på METCentre | 31 other | 66 offshore_wind |
| Skriver ned Wind Catching Systems med 6,9 millioner | 25 other | 60 offshore_wind |
| NVE gir grønt lys for Lyses gigantbatteri i Lysebotn | 41 other | 61 adjacent |
| Kaller mulig tysk oppkjøp illevarslende for Equinor (utdrag om fornybar) | 33 other | 53 adjacent |
| Haugaland Kraft kjøper aksjepost for 716 millioner | 25 other | 45 adjacent |
| DSB fant 19 avvik hos nettselskapet Fjellnett | 25 other | 45 adjacent |
| EU ber Norge vedta energilover | 25 other | 45 adjacent |
| + Lyse kraftavtale, Statkraft-kraftverk, Skatteetaten/kraftselskaper, Sognekraft | 25 other | 45 adjacent |

Saker om olje, gass og cyberangrep mot Equinor ble liggende som other_energy. Det er riktig: olje og gass skal rangeres lavt (se toppen av `signal.py`). Claude sjekket også E24 og TU (275 saker). 13 ble riktig flyttet til adjacent, bl.a. «Strømstøtte for over en halv milliard gikk til bedrifter», «NVE truer Statkraft med tvangsmulkt», «EU får pepper for karbontoll» og «Netto null er dårlig for Norge». Eneste feiltreff var «Luftforsvaret har oppgradert Nasams-batteri», som er løst med mer presise batteri-ord under.

## Ferdig når
- [ ] `OFFSHORE_WIND` i `signal.py` får i tillegg: `"tetraspar"`, `"metcentre"`, `"seatwirl"`, `"wind catching"`, `"flytende vindturbin*"`, `"havvindturbin*"`, `"vindturbin* til havs"`.
- [ ] `RELATED["Wind"]` får i tillegg: `"turbin*"`, `"vindturbin*"`, `"vindkraftverk*"`.
- [ ] `RELATED["Grid"]` får i tillegg: `"nettselskap*"`, `"nettleie*"`, `"effekttariff*"`, `"nettariff*"`.
- [ ] `RELATED["Power market"]` får i tillegg: `"kraftselskap*"`, `"kraftverk*"`, `"vannkraft*"`, `"kraftavtale*"`, `"strømstøtte*"`.
- [ ] `RELATED["Electrification"]` får i tillegg: `"batterier"`, `"batteriene"`, `"batterilager*"`, `"batteripark*"`, `"batterifabrikk*"`, `"batterigigant*"`, `"gigantbatteri*"`, `"storbatteri*"`, `"battery storage"`, `"energilager*"`. Ikke bare `"batteri*"`: det traff «Nasams-batteri» (luftvern) i testen.
- [ ] `RELATED["Energy policy"]` får i tillegg: `"nve"`, `"rme"`, `"energilov*"`, `"energikoordinator*"`, `"netto null"`, `"net zero"`, `"karbontoll*"`, `"cbam"`.
- [ ] Nytt område `RELATED["Renewables"]` (etter `"Hydrogen"`): `"fornybar*"`, `"renewable*"`, `"grønn kraft"`, `"green power"`.
- [ ] `SCORING_VERSION` økes (f.eks. `"2026-11-19.1"`), slik at lagrede saker får ny poengsum ved neste oppstart (`rescore.py` gjør dette allerede).
- [ ] Ny test i `owis/tests/test_signal_scoring.py` med disse ekte overskriftene og utdragene fra Energiwatch:
  - «SeaTwirl vil overta testplassen etter TetraSpar på METCentre» / «To Enova-støttede prosjekter utgjør til sammen 74 MW. Nå vurderer testsenteret å øke effektgrensen.» → `offshore_wind`.
  - «Haugaland Kraft kjøper aksjepost for 716 millioner» / «Kraftselskapet på Haugalandet tar opp lån for å kjøpe tilbake aksjene til en av de mindre eierne.» → `adjacent_energy`.
  - «Elvia lanserer ny effekttariff – batterier kan bli vinnere» → `adjacent_energy`.
  - «Skriver ned Wind Catching Systems med 6,9 millioner» → `offshore_wind`.
  - «DSB fant 19 avvik hos nettselskapet Fjellnett» → `adjacent_energy`.
  - «Odal Vindkraftverk får utrede inntil 20 nye turbiner» → `adjacent_energy` (som i dag).
  - Vakt mot for mye: «Luftforsvaret har oppgradert Nasams-batteri: – Et viktig løft» → fortsatt `other_energy`.
  - Vakt mot for mye: «Equinor planlegger rask utbygging av nytt funn» med utdraget «Funnet i Nordsjøen kan bygges ut raskt med eksisterende oljeplattform.» → fortsatt `other_energy`.
- [ ] De eksisterende testene i `test_signal_scoring.py` er uendret og grønne. Særlig `test_keywords_match_whole_words_only`.
- [ ] `pytest owis/tests -q` er grønn.
- [ ] I svar-filen: skriv poengsummen før og etter for overskriftene i testen.

## Design (bestemt av Claude – ikke endre)
- Bare nye ord i eksisterende lister, pluss det nye området «Renewables». Ingen endring i poengvekter, `FOCUS_POINTS`, `GEO_WEIGHT`, `SOURCE_WEIGHT` eller i hvordan `classify_focus` regner.
- Ordene skrives med små bokstaver, og `*` brukes som i resten av filen (tillater norske sammensatte ord og bøyninger).

## Filer som kan endres
- `owis/modules/news/processing/signal.py`
- `owis/tests/test_signal_scoring.py`
- `DECISIONS.md`, `PROJECT_STATUS.md`

## Ikke rør
- `owis/modules/news/collectors/` (innhentingen virker).
- `owis/modules/news/processing/editorial.py` (interesseområdene).
- Kildelisten og databasen.

## Tips
- `_terms()` lager ordmønstrene. Ord uten `*` må stå som hele ord.
- Pass på at `"rme"` og `"nve"` ikke treffer inni andre ord. Det gjør de ikke med `_terms`, men test gjerne «firmenavn» eller lignende.
- `rescore.py` kjører bare når `SCORING_VERSION` endres, og bruker ikke AI.

## Utenfor oppgaven
- Nye norske ord i interesseområdene i `editorial.py`.
- Hente mer tekst fra artikler bak betalingsmur.
- Endre vekten for Energiwatch som kilde.
