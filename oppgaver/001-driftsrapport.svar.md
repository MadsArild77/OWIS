# Svar på 001 – driftsrapport

## Gjort

- Nytt lesende API: `GET /api/news/ops-report?days=30`, med samme innloggingsbeskyttelse som resten av appen. Perioden kan være 1–366 dager.
- Nytt kort **System health** nederst i **Settings → News sources**, med alle seks seksjoner og **Refresh**. Rapporten lastes når Settings åpnes.
- Kommandolinje: `python -m owis.scripts.ops_report --db <sti-til-databasekopi> --days 30`. Skriver samme rapport som Markdown. SQLite åpnes skrivebeskyttet; manglende fil opprettes ikke.
- Ingen innhenting, AI, søk eller ny lagring. Ingen avhengigheter eller temaendringer.

## Slik ser Mads resultatet

Åpne appen, velg **Settings**, behold **News sources**, og rull ned til **System health**. Trykk **Refresh** for nye tall. Produksjon må få denne endringen før kortet blir synlig der; ingenting er pushet eller utrullet.

## Beregninger og begrensninger

- Perioden inkluderer dagens dato i Europe/Oslo. Nye artikler og uketabeller bruker `fetched_at`, altså når artikkelen ble lagret. Mandag er ukestart, og første/siste uke kan være ufullstendig.
- Fulltekst bruker eksisterende `news_content_basis`: `fulltext`, `alternative_fulltext` og `feed_text` teller som fulltekst; `feed_excerpt` som ingress. Ingen ny lengdeterskel. Manglende grunnlag telles separat. Betalingsmur betyr lagret `access=restricted`; en artikkel kan samtidig ha tilgjengelig alternativ fulltekst. Prosentene trenger derfor ikke summere til 100.
- Fulltekst og poengsum viser dagens lagrede tilstand for artiklene i perioden, ikke historiske øyeblikksbilder. Artikler som er slettet ved opprydding inngår ikke.
- «Offshore wind & related» bruker appens eksisterende kategorier `offshore_wind` og `adjacent_energy`. Bare lagrede poeng og klassifiseringer brukes; rapporten utløser ingen ny klassifisering. Andelen bruker alle lagrede artikler i perioden som nevner.
- Automatiske sammenslåinger og oppfølgingskoblinger telles fra beslutningsloggen (`news_learning_feedback`, `actor=auto`). Dette bevarer tellingen dersom paret senere vurderes på nytt. Siste 50 vises med gjeldende titler og kilder. Manglende par/artikler gir «Not recorded»; AI-sikkerhet vises bare dersom parets beslutningstid fortsatt samsvarer med logghendelsen.
- **Antall saker Mads har delt opp igjen: Not recorded.** Eksisterende kode logger én `unmerge` per artikkel, uten opprinnelig saks-ID eller felles hendelses-ID. Antall saker kan dermed ikke beregnes sikkert. Ingen ny lagring er lagt til.
- En aktiv morgenrapport har ennå ingen sluttstatus og vises som «Not recorded». En avbrutt kjøring eldre enn to timer vises som `failed`, som eksisterende morgenrapportkode. Ingen databasestatus endres. Dager uten rad vises som `missing`. Levering innen 07:00 krever fullført rapport på riktig Oslo-dato.
- Søkemåneden og grensen følger Source advisor: UTC-måned, registrerte søk og eksisterende `OWI_SEARCH_MONTHLY_LIMIT` med standard 1000. Rapporten kjenner ikke andre brukeres forbruk av samme nøkkel.
- Ingen nye produktbeslutninger er innført. `DECISIONS.md` er ikke endret fordi kortets tillatte filliste ikke inkluderer den. Statuslinjen er lagt til i `PROJECT_STATUS.md`.

## Kontroll

- Nye tester bruker isolerte databaser med kjente rader: alle rapporttall, poenggrenser, sommertid, lokal midnatt, leveringstid, siste 50 sammenslåinger, tomme data, skrivebeskyttet lesing, CLI, innlogging og ugyldige perioder.
- JavaScript: alle tre innebygde skript i `news.html` består syntakssjekk.
- Visningsfunksjonen er kjørt med testdata i Node: tabeller, hele prosent, HTML-escaping, «Not recorded», tomtilstand og feilhåndtering/reaktivering av Refresh består.
- Nettlesersjekk er **ikke gjennomført**. Ingen app med produksjonsdata er startet. Visuell plassering og knappens oppførsel må derfor kontrolleres av Mads.
- Hele testsettet: `C:/Users/madsa/Documents/Codex/OWIS/.venv/Scripts/python.exe -m pytest owis/tests -q --basetemp .pytest-tmp` → **273 bestått**, 13 eksisterende deprecation-advarsler, 14 min 16 sek. Under denne kjøringen ble rapporttestene utvidet fra fire til syv; endelig versjon ble derfor også kjørt separat: `-m pytest owis/tests/test_ops_report.py -q --basetemp .pytest-ops-final` → **7 bestått**, 5 deprecation-advarsler.
- Testenes midlertidige mapper er lagt innenfor arbeidskopien (`--basetemp`) for å følge mappebegrensningen. Automatisk godkjenningskontroll avviste sletting med «blocked by policy», så testmappene ligger igjen usporet og er ikke med i commit.
