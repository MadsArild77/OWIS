# Svar på 011 – Rettelser etter første produksjonskjøring

> Utført direkte av Claude 20. november 2026 etter at kort 009 og 010 var rullet ut.

## Funnet i produksjon
- Fem nye COWI-treff: tre fra Verdensbanken uten land (Tyrkia, Mongolia) og fire bygge-/leveransekontrakter
  (grunnentreprise Tjeldbergodden, riving Dokkeskjærskaien, «Design, Supply and Installation», «Construction of …»).
- TED stoppet med HTTP 429 etter 1800 anbud.
- «So what» brukte «crucial» i to av fem saker, og «Watch next» var tom.

## Gjort
Se D36. Feiltreffene forsvinner når den nye versjonen starter (opprydding ved oppstart); lagrede anbud beholdes.

## Testresultat
412 bestått på Python 3.13 og 3.11. Nye tester: de fire COWI-feiltreffene fra produksjon, TED som venter ved 429,
tomme «So what» som tas ut, og opprydding ved oppstart.
