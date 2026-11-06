# Svar på 002 – Del opp nyhetssiden i egne filer

## Gjort

`news.html` er redusert fra 3 644 til 417 linjer. HTML-oppsettet, eksisterende
stilattributter og HTML-handlinger er beholdt. Stilblokken er flyttet til `news.css`.
JavaScript er flyttet ordrett, uten omdøping eller omskriving, til disse filene i
samme rekkefølge som i originalen:

- `news-core.js`: felles tilstand, API-hjelpere, fremdrift og tekstformatering.
- `news-detail.js`: navigasjon og hjelpere for leseruten.
- `news-morning.js`: morgenrapport og politikk.
- `news-research.js`: researchede saker, research og kopiering.
- `news-feed.js`: saker, artikkeldetaljer, filtre og visning av strømmen.
- `news-review.js`: vurdering, sammenslåing og handlinger på artikler.
- `news-settings.js`: kildetabell, kildeinnstillinger og innhentingsknapper.
- `news-boot.js`: oppstart og tilkobling av hendelser.
- `news-shell.js`: sideoverskrifter, temasøk og hurtigtaster.
- `news-advisor.js`: driftsrapport, søkebudsjett, kilderådgiver og seksjonslenker.

Inndelingen følger sammenhengende deler av originalen for å unngå å flytte på
kjørerekkefølgen. Alle nye filer har `?v=1`. Skriptene lastes med vanlige
skripttagger, uten moduler, async eller defer. `theme.css`, `theme.js` og
`source-config.js` lastes som før, inkludert defer på sistnevnte.

En liten middleware i `main.py` setter `Cache-Control: no-store` på svar under
`/static/`. Eksisterende `StaticFiles` beholdes. Nettleseren lagrer dermed ikke
disse svarene for senere gjenbruk. Dette gjelder alle statiske filer og er bevisst
valgt som den enkleste løsningen uten byggesteg eller vedlikehold av filhasher.
Beslutningen er ført i D30 og statuslinjen er oppdatert.

## Slik ser Mads det

Åpne `/news` som før. Siden skal se ut og fungere som før; dette kortet gir ingen
ny funksjon. Filoppdelingen er synlig i kildekoden og nettleserens nettverksfane.

## Kontroller

- Maskinell sammenligning mot originalen: CSS, samlet JavaScript og gjenværende
  HTML-oppsett er identiske.
- `node --check` bestod for alle ti JavaScript-filene.
- Lokal Chromium-sjekk på port 8002 med egen testdatabase og tre syntetiske
  artikler. Planlagte jobber og AI var slått av, og eksterne nettverkstilkoblinger
  var blokkert i preview-prosessen. Ingen ekte innhenting ble startet.
- News, Stories/News-bryteren, åpning/lukking av en sak, Morning brief,
  Policy & regulation, Researched, Review queue, Source advisor og begge
  Settings-fanene ble åpnet og kontrollert. Rapport- og researchvisningene
  ble kontrollert i tom tilstand, uten generering av innhold.
- Hurtigtastene `/`, `j`, `k` og `Esc` virket. Lyst og mørkt tema ble kontrollert.
  Mobilbredde 390 px viste nyhetslisten og åpnet leseruten uten sidebredde-overløp.
- Alle nye filer svarte med HTTP 200 og `Cache-Control: no-store`.
- Ingen JavaScript-feil ble registrert. Nettleseren logget én HTTP 404 for
  `/favicon.ico`; ikonruten og ikonoppsettet er ikke endret av dette kortet.
- Hele pytest-settet bestod: **319 passed, 272 warnings**, på 11 minutter og
  8 sekunder. Kjørt én gang med
  `C:/Users/madsa/Documents/Codex/OWIS/.venv/Scripts/python.exe -m pytest owis/tests -q --basetemp .pytest-tmp`.
  Advarslene gjelder foreldede API-er i FastAPI, Starlette/AnyIO og feedparser.

## Avgrensninger

Ingen designendringer, nye avhengigheter eller endringer under `owis/modules/`.
Produksjon og ekte innhenting er ikke testet. Midlertidig testdatabase og
skjermbilder ligger under `.pytest-preview/` og inngår ikke i commit.
