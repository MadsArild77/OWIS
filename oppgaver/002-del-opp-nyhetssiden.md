# 002 – Del opp nyhetssiden i egne filer

> Gjøres etter at 001 er slått sammen, siden den også endrer `news.html`. Kan gjøres samtidig med 003 (ulike filer).

## Mål
Nyhetssiden ser ut og virker nøyaktig som før, men stil og JavaScript ligger i egne filer i stedet for i én fil på 3 500 linjer. Ingen ting endres for Mads.

## Hvorfor
`owis/apps/web/news.html` har sidestil (linje ~9–461) og tre skriptblokker (~834–3284, ~3285–3367, ~3368–3513) i samme fil. Hver endring i nyhetssiden krever at hele filen leses, og det gir flere feil og dyrere oppgaver. Dette er ren flytting, ikke omskriving.

## Ferdig når
- [ ] `news.html` inneholder bare HTML-oppsettet og lenker til filene under.
- [ ] Stilen ligger i `owis/apps/web/news.css`.
- [ ] JavaScript ligger i filer etter område, f.eks. `news-core.js` (felles hjelpere, API-kall, tilstand), `news-feed.js` (strøm, saker, leserute), `news-morning.js` (morgenrapport og politikk), `news-workspace.js` (Researched, Review, Source advisor) og `news-settings.js`. Nøyaktig inndeling velger du ut fra koden; skriv den i svar-filen.
- [ ] Rekkefølgen skriptene lastes i gir samme oppførsel som i dag (vanlige `<script>`-tagger, ikke moduler, slik at globale funksjoner og `onclick="..."` i HTML virker som før).
- [ ] Alle nye filer lenkes med versjonsparameter (`?v=1`), og `/static` gir ikke gamle filer etter en utrulling. Bruk den enkleste løsningen som passer med `StaticFiles` i `main.py`, og beskriv den i svar-filen.
- [ ] Ingen kode er endret utover flytting og det som trengs for at den skal virke i egne filer. `git diff --stat` skal vise at linjene i hovedsak er flyttet.
- [ ] Nettlesersjekk (lokal preview med testdatabase): News, Stories/News-bryteren, åpne en sak, Morning brief, Policy & regulation, Researched, Review, Source advisor, Settings (begge faner), lyst/mørkt tema, hurtigtastene `/`, `j`, `k`, `Esc` og mobilbredde. Ingen feil i konsollen. Skriv hva som ble sjekket i svar-filen.
- [ ] `pytest owis/tests -q` er grønn.

## Design (bestemt av Claude – ikke endre)
- Ingen visuelle endringer, ingen nye funksjoner, ingen omdøping av funksjoner eller ID-er.
- Ingen byggesteg, ingen bundler, ingen nye avhengigheter.
- `theme.css`, `theme.js` og `source-config.js` lastes som i dag.

## Filer som kan endres
- `owis/apps/web/news.html`
- `owis/apps/web/news.css`, `owis/apps/web/news-*.js` (nye)
- `owis/apps/api/main.py` (bare hvis det trengs for hurtigbuffer på `/static`)

## Ikke rør
- `owis/apps/web/theme.css`, `theme.js`, `source-config.js`, `opportunities.html`.
- Alt under `owis/modules/`.

## Tips
- Ingen tester leser `news.html` i dag, så nettlesersjekken er den viktigste kontrollen.
- `/news` sendes med `Cache-Control: no-store`, men filer under `/static` gjør ikke det.

## Utenfor oppgaven
- Rydding, omskriving eller deling av store funksjoner.
- Samme oppdeling for `opportunities.html`.
