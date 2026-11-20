# 010 – Ny morgenrapport, strammere filtre og daglig anbudshenting

> Utført direkte av Claude 20. november 2026 etter valg fra Mads, ikke av Codex.

## Mål
Morgenrapporten får med politikk, trender, frister og nye anbud, og er lettere å lese. Politikklista og
anbudslista viser mindre som ikke gjelder havvind, og anbud hentes uten at Mads må trykke.

## Hvorfor
Produksjonssjekken 20. november (se svar 009) viste at AI-input ble kuttet ved 24 000 tegn, at trender
manglet alle 30 dager, at tre av fire politikksaker ikke gjaldt havvind, nett eller hydrogen, at MAV-profilen
fanget HR og IT, og at anbudslista hadde stått stille siden 6. november.

## Valg Mads har tatt
- Format: kort først (dagens viktigste og tre punkter), deretter saker gruppert på tema, frister og nye anbud.
- Politikksøket i morgenrapporten: ukentlig (mandag).
- Energidepartementet og Stortingets spørsmål til energiministeren: følg alt som før.
- MAV-profilen: rådgivning innen havvind.
- Anbud: hent daglig kl. 04:30.

## Ferdig når
- [x] Politikk, hendelser og tidligere dager når AI-en; nyhetene kuttes først om input blir for lang.
- [x] Ny visning med temaer, frister de neste 14 dagene og nye anbud; eldre rapporter vises som før.
- [x] Advarslene fra politikksøket er slått sammen.
- [x] Politikksøket kjøres mandager; andre dager bare kjente kilder.
- [x] Importfil for strammere politikktemaer, og fil som setter dem tilbake.
- [x] MAV krever havvind; daglig anbudshenting kl. 04:30 tar også ut gamle treff som ikke lenger passer.
- [x] `pytest owis/tests -q` er grønn på Python 3.11 og 3.13.

## Utenfor oppgaven
Felles innhentingsmotor (trinn 2), nye kilder for NVE/Statnett/Havtil, Kommisjonens pressemeldinger.
