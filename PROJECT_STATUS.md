# OWIS – utviklingsstatus

Oppdatert 5. oktober 2026. [Dokumentasjon](DOCUMENTATION.md) · [Beslutninger](DECISIONS.md) · [Plan](IMPLEMENTATION_PLAN.md)

## Gjeldende status

Sist kontrollerte kodegrunnlag er `main`, inkludert PR #8 (`4258468`) og
Settings-fanene (`600619b`). Dette er utviklingsstatus, ikke en bekreftelse på
hvilken versjon eller konfigurasjon som kjører i produksjon.

| Område | Status | Detaljer |
|---|---|---|
| Nyheter og redaksjonell flyt | Implementert med kjente begrensninger | RSS/nettsider, relevans, tilbakemeldinger, research, Copy info og researchede saker; se [EDITORIAL.md](EDITORIAL.md) |
| Relevans og poengsum | Ny modell med havvind først, fast taksonomi og betalingsmur-dekning | Se [D13](DECISIONS.md); må kontrolleres på nye produksjonsdata |
| Kilderådgiver og lært kildevekting | Implementert | [D15](DECISIONS.md); forslag om nye kilder krever verifiserte treff over tid |
| Artikkelmatching | Automatisk gruppering av sikre treff etter hver innhenting; usikre i Review | [D14](DECISIONS.md), [MATCHING.md](MATCHING.md); feilrate på virkelige data ikke målt |
| Morgenrapport og politikk | Grunnversjon implementert | Siste døgn, kommende milepæler, radar og valgfri 06-kjøring; [MORNING_REPORT.md](MORNING_REPORT.md) |
| Jurisdiksjoner og kilder (trinn 1) | Ferdig og flettet til main | Felles register, organisasjoner, test og import/eksport; [SOURCE_CONFIGURATION.md](SOURCE_CONFIGURATION.md) |
| Settings | Ferdig på main | Separate News- og Regulatory-faner; News er standard |
| Tilgang og drift | Innlogging i kode; ikke aktivert | Krever `OWI_ACCESS_PASSWORD` i Railway; se [D10](DECISIONS.md) og [teknisk README](owis/README.md) |
| Grensesnitt | Ny nyhetsside med sidemeny, søk, leserute og lyst/mørkt tema | Se [D11 og D12](DECISIONS.md) |
| Felles innhentingsmotor (trinn 2) | Ikke startet | Betinget henting, endringskontroll og versjoner |
| Norge-adaptere (trinn 3) | Ikke startet | Regjeringens kalender/høringer og Stortingets komiteer, med prioritering |
| Morgenrapport og drift (trinn 4) | Videre integrasjon gjenstår | Koble ny motor og adaptere til rapporten, kontrollere dekning og drift |
| Opportunities | Eksisterende startmodul | Ikke nyvalidert i denne dokumentasjonsoppdateringen; se [teknisk README](owis/README.md) |
| Lyd/NotebookLM | Åpent forslag | Ingen automatisk integrasjon implementert |

## Sist gjennomførte validering

3. oktober: 166 tester bestod lokalt for trinn 1, og GitHub-testene for PR #8
bestod. Nettlesertest med isolert database kontrollerte organisasjonshierarki,
faktisk HTML-forhåndsvisning, lagring/omlasting og pause/gjenopptak.
Settings-fanene ble deretter kontrollert med mus og tastatur, samt JavaScript-syntaks.
Ingen nye apptester er kjørt for dokumentasjonsoppdateringen 4. oktober.

5. oktober: innlogging, opprydding i driftsoppsett og begrensning av
oppstartskopier. Fire nye tester; hele testsettet kjørt lokalt på Python 3.13.
Testmiljøet på Railway svarte uten innlogging før endringen.
Samme dag: nytt lyst/mørkt tema kontrollert i nettleser med testdata,
inkludert kontrast i alle visninger, temabryter, artikkelvisning og mobilbredde.
Ny nyhetsside (D12) kontrollert i nettleser: søk, emnefilter, dagsgruppering,
leserute, hurtigtaster, alle seksjoner og innstillinger, kontrast på minst
5,2:1 i begge temaer og ingen sidelengs rulling på mobil.
Relevansmodellen (D13) er kalibrert mot et utdrag på 500 produksjonsartikler:
havvind-saker med kontrakter/auksjoner havner øverst (85–96), elbil- og solsaker
under 56. 180 tester består lokalt.

## Neste arbeid og begrensninger

Neste utviklingstrinn er **trinn 2: felles innhentingsmotor**, etter den lagrede
[planen](IMPLEMENTATION_PLAN.md). Konfigurerbare intervaller, tema-/personregler
og kalenderkilder betyr foreløpig ikke at disse brukes av innhentingen.
Morgenrapportens eksisterende politikkoppslag bruker fortsatt egne kildegrupper.

Aktiv produksjonsversjon, miljøvariabler, kildehelse og automatisk kjøring er ikke
kontrollert på nytt her. Historiske testmiljøopplysninger nedenfor er ikke en
bekreftelse på dagens drift.

## Historikk – bevart fra tidligere utviklingsarbeid

Notatene nedenfor beskriver tidligere tidspunkt. Grennavn, testtall, neste steg,
preview-adresser og utrullingsstatus kan være utdaterte. Gjeldende status står over.

### Baseline 23. september 2026

## Arbeidssted

- Lokal mappe: `C:\Users\madsa\Documents\Codex\OWIS`.
- Repo: https://github.com/MadsArild77/OWIS
- Arbeidsgren: `work/resume-owis`, basert på `7069c638` fra 12. mai 2026.
- Den gamle arbeidskopien i `C:\Users\madsa\OneDrive\OpenAI` er beholdt. Git-sporet arbeid, inkludert upublisert arkivering, er bevart i denne arbeidsgrenen.
- Integritetskontrollerte SQLite-backuper av `owi.db`, `e2e_test.db` og `master_e2e.db` ligger i `owis/data`. Disse og testdata er ignorert av Git.
- Andre prosjekter og eksportfiler i OpenAI-mappen er beholdt der.

## Verifisert nyhetsflyt

- De gamle RSS-adressene til Recharge og WindEurope svarte 404. WindEurope er korrigert til `/feed/`, OffshoreWIND.biz er lagt til, og den ødelagte Recharge-kilden er deaktivert.
- 60 feed-elementer hentet fra to kilder; 5 eldre enn 30 dager filtrert bort; **55 artikler lagret og behandlet uten feil** i `work/live-validation.db`.
- Andre innhenting: **0 nye artikler og 0 behandlingsfeil**.
- Signalformat og kilde-URL kontrollert for alle 55. Én originalartikkel fra hver kilde svarte HTTP 200.
- Hoveddatabasen fra originalen er tom. Testdataene ligger separat og er kopiert til `work/preview.db` for visning.
- Nyhetsliste og artikkeldetaljer med kildehenvisning er kontrollert i nettleseren.
- **38 automatiserte tester består**. Fire deprecation-advarsler kommer fra feedparser under Python 3.13.
- Avhengighetskontroll og oppstartskontroll består.

## Rettelser

- RSS-henting har timeout, HTTP-feilkontroll og kontroll av feedformat. Feilrapportering skiller nå ødelagte kilder fra vellykket innhenting.
- Fulltekst fra feed bevares. Korte RSS-utdrag avvises ikke som om de var skrapede nettsider.
- HTML, script og stilinnhold fjernes før oppsummering. Aktørforkortelser matches som egne ord, og overskriften inngår i regelbasert tagging.
- Arkivering bevarer manuelle vurderinger, sammenslåinger, læringshistorikk og parvurderinger. Arkiverte URL-er hentes ikke inn igjen. Datoer sammenlignes som tidspunkt, og databasefeil ruller arkiveringen tilbake.
- SQLite-forbindelser lukkes eksplisitt etter transaksjoner.
- PowerShell-oppstart bruker prosjektets virtuelle miljø og korrekt arbeidsmappe, uten konflikt med den reserverte `$Host`-variabelen.
- Metadatafeltenes bakgrunn er tilpasset mørkt tema for lesbar kontrast.

## Forhåndsvisning og videre arbeid

Forhåndsvisning: http://127.0.0.1:8765/news. Den bruker `work/preview.db`, med AI og Notion-eksport deaktivert. Logger og launcher-PID ligger i `work`. Prosessen stopper ved omstart; se README for vanlig oppstart.

Oppsummeringer i testen er tekstutdrag. Tagging, prioritering og «why it matters» er regelbasert og krever fortsatt faglig kalibrering. Enkelte feeder gir bare korte utdrag. AI-matching er testet på syntetiske eksempler; kvalitet på virkelige artikkelpar gjenstår.

Neste steg er å kalibrere relevans og scoring, og deretter implementere News/LinkedIn-eksport til Notion med valgt måldatabase. Opportunities har allerede egen Notion-eksport, men News har ikke den spesifiserte eksportjobben. News v1 er derfor ikke erklært ferdig.

Ingen publisert app eller automatisk innhenting er aktivert av denne gjennomgangen. NorthernBlue-portalen har fortsatt OWIS som `building` / `planned`. Prosjektmappen er klar for åpning i Codex; registrering i sidepanelet er ikke utført.


## Matching-oppdatering

OpenAI-basert semantisk kandidatsøk, lagring av analyser, fem relasjonstyper og manuell godkjenning er implementert. Oppdateringer kobles som separate hendelser. Godkjente sammenslåinger bevarer hele eksisterende manuelle grupper og skjer i en databasetransaksjon.

**66 tester består**. Railway-innlogging er aktiv, og eksisterende OpenAI-nøkkel ble brukt til en isolert test uten å endre driftsinnstillinger. Den billige modellen `gpt-4o-mini` beholdes, med `text-embedding-3-small` for kandidatsøk.

Direkte OpenAI-test: **30/30 syntetiske norsk/engelske artikkelpar bestod**, ingen feilaktige same-event-klassifiseringer. Beregnet kostnad fra faktisk tokenbruk: **0,00418107 USD**. Testkjøringen har egen konservativ grense på 0,10 USD; appen har fortsatt pargrense og caching, ikke en global dollargrense. Se MATCHING.md for detaljer og begrensninger.

Endringene ligger i utkast til PR #1. Ingen produksjonsutrulling er utført. Neste kvalitetssteg er et manuelt merket sett med virkelige artikler; sammenslåing krever fortsatt menneskelig godkjenning.

## Kontroll med virkelige kilder

12 målrettet valgte par i 61 artikler: 11/12 relasjonstyper stemte, alle 8 positive kandidater funnet, ingen feilaktige same-event. Kostnad cirka 0,00194 USD. Avviket var unrelated kontra related_topic for ulike vindparker. Datagrunnlaget består i stor grad av korte utdrag/overskrifter; faglig vurdering og bedre fulltekstdekning gjenstår. Ingen utrulling. Detaljer i MATCHING.md.

## Interaktiv redaksjonell flyt

Implementert hurtigvalg, begrunnelser, angring, lagrede utkast og interesseområder for energi, maritim næring og nett/elektrifisering. RSS og nettsideindekser filtreres før fullteksthenting. Tilgang og kildegrunnlag vises, og lukkede saker kan få verifiserte åpne alternativer. Overvåkede URL-er lagres i databasen; slettede standardkilder gjenopprettes ikke. Se EDITORIAL.md.

84 tester består. Railway-miljøet owis-review er opprettet for live-test med eget /data-volum. Produksjon er ikke oppgradert. Lokal AI-aktivering ble stoppet av automatisk godkjenningskontroll; eksisterende preview har fortsatt AI av.

## Fullført live-test

Live-test: https://owis-web-owis-review.up.railway.app/news. Utkast-rettelsen i 3e8e249 er rullet ut. Åtte artikler behandlet, sju med åpen artikkeltekst. Norsk LinkedIn-utkast ble generert og lagret. Hurtigvurdering ble testet i nettleser, bevart gjennom omstart og deretter angret. Alle fire registrerte kilder og utkastet var identiske etter omstart.

Ved import av bare energiwatch.no ble kjent RSS-endepunkt funnet og lagret: https://rss-feed-api.aws.jyllands-posten.dk/energiwatch.no/latest. Live helsekontroll bekreftet at feeden inneholder artikler. Testmiljøet har eget /data-volum; produksjon er ikke oppgradert. GitHub pytest bestod alle 84 tester.
