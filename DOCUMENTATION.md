# OWIS – dokumentasjon og beslutninger

Felles inngang til prosjektets dokumentasjon. Oppdatert 5. oktober 2026.
Dokumentene lagres og versjoneres sammen med koden i Git.

## Start her

- **Hva er ferdig, og hva gjenstår?** [Prosjektstatus](PROJECT_STATUS.md).
- **Hva har vi bestemt, og hvorfor?** [Beslutningslogg](DECISIONS.md).
- **Hva skal vi implementere nå?** [Implementeringsplan](IMPLEMENTATION_PLAN.md).
- **Hvordan starter og konfigurerer jeg OWIS?** [Oppstart](README.md) og [teknisk oppsett](owis/README.md).

## Alle dokumenter

| Dokument | Formål og bruk |
|---|---|
| [Dokumentasjonsoversikt](DOCUMENTATION.md) | Denne inngangen og reglene for vedlikehold |
| [Beslutningslogg](DECISIONS.md) | Avtalte valg, begrunnelser, implementeringsstatus og åpne spørsmål |
| [Prosjektstatus](PROJECT_STATUS.md) | Gjeldende utviklingsstatus; tidligere verifiseringer er merket historikk |
| [Implementeringsplan](IMPLEMENTATION_PLAN.md) | Sjekklister og ferdigkriterier for de fire neste utviklingstrinnene |
| [README](README.md) | Kort prosjektinngang og lokal oppstart |
| [Teknisk README](owis/README.md) | Konfigurasjon, jobber og appoppsett |
| [Kildekonfigurasjon](SOURCE_CONFIGURATION.md) | Jurisdiksjoner, organisasjoner, kildeeditor, migrering og API |
| [Redaksjonell flyt](EDITORIAL.md) | Relevans, tilbakemeldinger, research, kildeutvidelse og utkast |
| [Matching](MATCHING.md) | Artikkelkobling, AI-oppsett, kostnadsgrenser og evaluering |
| [Morgenrapport](MORNING_REPORT.md) | Rapportinnhold, tidsstyring, kildegrunnlag og begrensninger |
| [Masterspesifikasjon](offshore_wind_intelligence_system_master_spec.md) | Overordnet produktvisjon og arkitektur; beskriver også funksjoner som ikke er bygget |
| [Byggerekkefølge og News v1](offshore_wind_build_order_and_news_v_1_spec.md) | Opprinnelig kravgrunnlag; senere beslutninger kan endre retningen |
| [NorthernBlue Portal](portal/README.md) | Separat portal med lenker til OWIS og andre apper |

## Hvordan holde oversikten oppdatert

1. Nye produkt- og arkitekturvalg føres i beslutningsloggen med status, begrunnelse
   og lenke til plan, dokumentasjon eller commit/PR. Ideer merkes som åpne forslag.
2. Når et trinn fullføres, oppdateres prosjektstatus og plan i samme endring.
   Oppgi hva som er testet, og skill mellom kode på `main` og bekreftet utrulling.
3. Funksjonsdetaljer vedlikeholdes i fagdokumentet for området, ikke som kopier
   i alle oversiktene. Nye dokumenter legges til i tabellen over.
4. Tidligere beslutninger slettes ikke ved omvalg; marker dem som erstattet og
   lenk til den nye beslutningen. Historiske testtall og driftsopplysninger dateres.

Ved motstrid beskriver prosjektstatus hva vi sist har verifisert, planen hva som
gjenstår, og beslutningsloggen hvilken retning som er avtalt. Spesifikasjonene er
kravgrunnlag, ikke bevis på implementering. Uklarheter avklares og dokumenteres.
