# Offshore Wind Intelligence System – Master Structure & Build Specification

## 1. Formål

Dette systemet skal bygges som en **modulær, portabel og kostnadsbevisst intelligence-plattform** for offshore vind og relaterte markeder. Arkitekturen skal fungere både som:

1. **selvstendige domenemoduler** som kan brukes hver for seg
2. et samlet **topplag / executive brief / control center** som syntetiserer signaler fra flere moduler
3. et praktisk grunnlag for **effektiv koding med LLM**, særlig med gratis eller billige verktøy
4. et system som også mater en **LinkedIn idea database i Notion** for thought leadership og merkevarebygging

Systemet skal bygges trinnvis, modul for modul. Toppmodulen skal først bygges når 2–3 underliggende moduler leverer stabile signaler.

---

# 2. Designprinsipper

## 2.1 Modulært først
Hver modul skal kunne:
- hente egne kilder
- prosessere egne signaler
- ha eget presentasjonslag
- fungere uten toppmodulen

## 2.2 Felles signalformat, ikke monolittisk kjerne
Modulene trenger ikke dele all intern logikk, men de må kunne eksportere et standardisert **signal contract** til topplaget.

## 2.3 AI er rådgivende, ikke sannhetskilde
AI skal:
- oppsummere
- klassifisere
- prioritere
- foreslå koblinger
- generere briefs

AI skal ikke skjule råsignalene. Brukeren skal kunne gå fra syntese → modul → originalkilde.

## 2.4 Human-in-the-loop læring
Systemet skal kunne foreslå:
- hva som hører sammen
- hvilke signaler som er viktige
- hvilke LinkedIn-idéer som er interessante

Bruker skal kunne:
- bekrefte
- avvise
- korrigere

Dette bygger et proprietært læringslag over tid.

## 2.5 Lav kostnad og portabilitet
Systemet skal:
- kunne starte på billige eller gratis verktøy
- kunne hostes enkelt
- ikke låses til én leverandør
- minimere tokens og API-kall

## 2.6 Structured data first
Det viktigste i tidlig fase er ikke full autonomi, men:
- god kildeinnhenting
- ryddig struktur
- tydelig metadata
- sporbarhet

---

# 3. Overordnet arkitektur

## 3.1 Logisk arkitektur

Sources → Domain Module → Structured Signals → Top Layer / Executive Brief → Outputs

Hver domenemodul observerer sitt eget område. Topplaget leser signaler fra modulene, lager syntese og presenterer dette som et executive brief / control center.

## 3.2 Teknisk arkitektur

Hver modul bør bestå av:

1. **Source registry**
2. **Collector / ingestion**
3. **Raw storage**
4. **Module-specific processing**
5. **Structured signal output**
6. **Module presentation layer**
7. **Optional Notion export**

Topplaget bør bestå av:

1. **Signal aggregator**
2. **Semantic synthesis layer**
3. **Executive dashboard / brief**
4. **Learning interface**
5. **LinkedIn idea enrichment**

---

# 4. Modulfilosofi

## 4.1 Domenemoduler er selvstendige enheter
Hver modul skal kunne brukes som en egen miniapplikasjon.

Eksempler:
- News module
- Regulatory & Policy module
- Opportunities module
- Projects module
- Supply Chain module
- Stakeholders module

Hver modul skal ha:
- egen kildeoversikt
- egen prosesslogikk
- eget UI / visningslag
- egen intern prioritering
- eksport av standardiserte signaler

## 4.2 Topplaget skal ikke erstatte modulene
Topplaget skal fungere som:
- index
- executive brief
- control center
- semantic synthesis

Det skal bygge på signalene modulene allerede har løftet frem.

## 4.3 Tidlig fase
Bygg 2–3 moduler først. Anbefalt rekkefølge:

1. News
2. Opportunities
3. Regulatory & Policy

Deretter bygges topplaget.

---

# 5. Foreslåtte hovedmoduler

## 5.1 Dashboard / Executive Brief (topplag)
Ikke første modul. Bygges etter at 2–3 moduler leverer strukturerte signaler.

Funksjon:
- vise top signals på tvers
- vise emerging themes
- vise new opportunities
- vise policy shifts
- gi executive summary

Input:
- strukturerte signaler fra modulene

Output:
- executive brief
- weekly summary
- AI-syntese
- LinkedIn-ideer på toppnivå

---

## 5.2 News / Market Signals
Formål:
Samle og analysere løpende markedsnyheter.

Typiske kilder:
- Recharge
- EnergiWatch
- Europower
- Windpower Monthly
- relevante selskapsmeldinger
- andre nisjekilder

Oppgaver:
- hente RSS og artikler
- ekstrahere tekst
- oppsummere
- klassifisere topic/subtopic
- score relevans
- generere why_it_matters
- generere mulig LinkedIn-vinkel

Presentasjonslag:
- latest articles
- top signals
- filtered by geography/topic
- saved LinkedIn ideas

Særskilt rolle:
Dette er første og mest naturlige modul fordi den gir løpende signalstrøm.

---

## 5.3 Regulatory & Policy
Formål:
Overvåke regulatoriske og politiske utviklinger per region og jurisdiksjon.

Eksempler:
- EU
- Norway
- UK
- Spain
- Japan
- andre prioriterte markeder

Kildetyper:
- departementer
- regulatorer
- energimyndigheter
- konsultasjonsportaler
- støttesystem-sider
- offentlige kunngjøringer

Oppgaver:
- oppdage nye policy-signaler
- trekke ut jurisdiction, authority, policy_type, status, deadlines
- skrive implications
- plassere i relevant kategori
- markere endringer som kan påvirke marked, prosjekter eller industri

Presentasjonslag:
- country/region overview
- latest policy updates
- consultations and deadlines
- key implications

Særskilt rolle:
Policy-signaler er ofte blant de viktigste driverne i offshore vind og må derfor behandles som egen modul.

---

## 5.4 Opportunities
Formål:
Identifisere konkrete muligheter, både kommersielle og strategiske.

Denne modulen bør deles i underenheter:

### A. Market Competitions
Eksempler:
- områdeutlysninger
- CfD-auksjoner
- leasing rounds
- støttekonkurranser
- prequalification-runder

### B. Procurement / Tenders
Eksempler:
- TED
- Doffin
- Find a Tender
- World Bank
- EBRD

### C. Funding Calls
Eksempler:
- Innovation Norway
- Horizon Europe
- OWGP
- Just Transition Fund

### D. Strategic Programs
Eksempler:
- pilotprogrammer
- demonstrasjonsprogrammer
- EOI / RFI-lignende prosesser

Oppgaver:
- hente notices og kunngjøringer
- klassifisere opportunity family og mechanism type
- trekke ut deadline, authority, relevance, actionability
- generere recommended_action

Presentasjonslag:
- latest opportunities
- upcoming deadlines
- high relevance opportunities
- market competitions overview

Særskilt rolle:
Denne modulen peker direkte mot handling og potensielle inntekter.

---

## 5.5 Projects / Project Pipeline
Formål:
Holde oversikt over prosjektportefølje og markedsutvikling på prosjektnivå.

Datapunkter:
- project_name
- developer
- capacity
- country
- technology
- project_stage
- tender/allocation model
- expected timeline

Presentasjonslag:
- project list
- by geography
- by stage
- new status changes

Kommentar:
Kan bygges senere, når de tre første modulene er etablert.

---

## 5.6 Supply Chain
Formål:
Følge industribevegelser og fysisk kapasitet i verdikjeden.

Eksempler:
- OEM-utvikling
- fabrikkinvesteringer
- havner
- installasjonsfartøy
- kabelkapasitet
- substasjoner

Presentasjonslag:
- major supply chain moves
- manufacturing developments
- ports and vessels
- capacity trends

Kommentar:
Bør komme etter News, Opportunities og Policy.

---

## 5.7 Stakeholders / Companies
Formål:
Koble signaler til selskaper, aktører og relasjoner.

Datapunkter:
- company
- person
- role
- geography
- activity
- linked signals

Presentasjonslag:
- company pages
- stakeholder watchlist
- relevant recent signals

Kommentar:
Kan kobles til Marketing Hub og Notion senere.

---

## 5.8 AI Synthesis / Themes
Dette er ikke en rådatamodul, men et semantisk topplag.

Funksjon:
- koble signaler på tvers
- identifisere emerging themes
- foreslå what matters now
- foreslå strategiske implikasjoner
- generere briefing-notater

Kommentar:
Bygges først når minst 2–3 moduler leverer standardiserte signaler.

---

# 6. Signal contract v1

Alle moduler skal eksportere signaler til topplaget i et standardisert format.

## 6.1 Minimumsfelter

- signal_id
- module_type
- title
- source_name
- source_url
- published_at
- country
- geography_tags
- theme_tags
- actors
- summary
- why_it_matters
- signal_score
- confidence
- raw_reference

## 6.2 Valgfrie felter

- deadline
- authority
- policy_type
- mechanism_type
- opportunity_family
- recommended_action
- project_stage
- linked_entities
- linkedin_angle
- linkedin_status

## 6.3 Prinsipp
Modulene kan ha egne interne datamodeller, men topplaget forholder seg til signal contract.

---

# 7. Datamodell per lag

## 7.1 Raw layer
Lagre:
- URL
- HTML / tekst
- hentet tidspunkt
- source metadata
- eventuelle PDF-er

Formål:
- sporbarhet
- debugging
- reprocessing uten ny scraping

## 7.2 Module layer
Hver modul lagrer egne berikede objekter.

Eksempel News:
- topic
- subtopic
- article text
- article summary

Eksempel Opportunities:
- authority
- deadline
- opportunity family
- mechanism type

## 7.3 Signal layer
Et standardisert signalobjekt sendt til topplaget.

## 7.4 Learning layer
Lagre:
- AI-suggested relationships
- user confirmed relationships
- rejected links
- corrected tags
- corrected priorities

---

# 8. Hvordan håndtere ulikhet mellom land

Systemet skal ikke hardkode per land som hovedlogikk.

## 8.1 Hardcode taxonomy, not jurisdictions
Bygg et lite sett med universelle kategorier:
- opportunity_family
- mechanism_type
- stage
- status
- policy_type

## 8.2 Local attributes
Legg lokale særtrekk i fleksible attributter.

Eksempel:
- support_model
- local_content_rules
- allocation_object
- award_model

## 8.3 LLM mapping
Bruk LLM til å mappe lokale beskrivelser til kontrollert taksonomi.

Dette gir:
- bedre skalering
- mindre landspesifikk kode
- mer fleksibilitet

---

# 9. AI-rolle i systemet

## 9.1 Ikke fri web-crawling først
LLM skal ikke være hovedmotor for å finne internett.

Riktig rekkefølge:
1. collectors finner kandidater
2. extraction henter tekst
3. LLM forstår og organiserer

## 9.2 AI brukes til
- relevansvurdering
- klassifisering
- oppsummering
- why_it_matters
- scoring
- suggested links
- LinkedIn angle suggestions
- executive synthesis

## 9.3 AI er advisory
Råsignaler og kilder skal være tilgjengelige. AI-laget skal være tydelig merket som syntese og forslag.

---

# 10. Learning interface

Dette skal innføres relativt tidlig, men kan starte enkelt.

## 10.1 Systemet foreslår
- disse signalene hører sammen
- dette er trolig samme tema
- dette bør være high priority
- dette bør være LinkedIn-relevant

## 10.2 Bruker kan
- bekrefte
- avvise
- korrigere
- markere usikker
- tagge selv

## 10.3 Verdi
Dette bygger gradvis et mer presist proprietært intelligenslag.

---

# 11. LinkedIn idea integration

Alle moduler skal kunne generere signaler som kan brukes til thought leadership.

## 11.1 Minimumsfelter for Notion / LinkedIn Idea DB

- signal_id
- title
- source_url
- module_type
- summary
- why_it_matters
- linkedin_angle
- geography
- topic
- priority
- status
- created_at

## 11.2 Typisk bruk
Et signal kan merkes som:
- strong post candidate
- possible comment angle
- needs more context
- not for content

## 11.3 Formål
Dette gjør at systemet ikke bare er intelligence, men også en brand-building engine.

---

# 12. Praktisk byggeplan

## Fase 1 – Foundations
Bygg:
1. source registry structure
2. raw storage
3. first module: News
4. simple UI for News
5. Notion export for LinkedIn ideas

## Fase 2 – Action layer
Bygg:
1. Opportunities module
2. structured opportunity types
3. deadlines and relevance logic
4. simple UI for Opportunities

## Fase 3 – Strategic layer
Bygg:
1. Regulatory & Policy module
2. jurisdiction structure
3. implications logic
4. policy UI

## Fase 4 – Top layer
Når minst 2–3 moduler fungerer:
1. signal aggregator
2. semantic synthesis
3. executive brief
4. emerging themes
5. cross-module ranking

## Fase 5 – Learning
Bygg:
1. suggested relationships
2. user confirm / reject
3. saved corrections
4. future ranking refinement

## Fase 6 – Expansion
Mulige neste moduler:
- Projects
- Supply Chain
- Stakeholders
- Funding as separate unit

---

# 13. Presentasjonslag

## 13.1 Hver modul trenger eget presentasjonslag
Målet er at hver modul skal fungere som en egen side eller miniapp.

Eksempel:
- /news
- /opportunities
- /policy

Hver side bør ha:
- latest items
- top signals
- filters
- source traceability
- AI notes
- LinkedIn candidate tags

## 13.2 Topplaget
Topplaget bør vise:
- executive summary
- top cross-module signals
- emerging themes
- upcoming deadlines
- latest opportunities
- top LinkedIn-worthy signals

---

# 14. Hosting og portabilitet

## 14.1 Prinsipp
Systemet skal være enkelt å flytte.

Unngå:
- tung avhengighet til én databaseleverandør
- tung avhengighet til én AI-plattform
- proprietær plattformlås hvis mulig

## 14.2 Anbefalt tidlig fase
Mulige enkle løsninger:

### Frontend
- enkel statisk webapp
- lett React/Vite-løsning
- alternativt enkel server-rendered løsning

### Backend
- Python
- FastAPI eller enkel Flask

### Database
- SQLite i tidlig fase
- senere Postgres hvis nødvendig

### Jobs
- cron
- GitHub Actions
- enkel scheduler på server

### Storage
- lokale filer / enkel database / JSON cache

## 14.3 Webhotell vs server
Hvis klassisk webhotell ikke støtter nødvendige bakgrunnsjobber og Python godt nok, vil en enkel VPS ofte være bedre. Men arkitekturen bør være så enkel at flytting er mulig.

Målet er:
- lett å starte
- lett å migrere
- lett å forstå

---

# 15. Kostnadsbevisst AI-bruk

## 15.1 Hovedprinsipp
Bruk LLM kun der det gir reell verdi.

## 15.2 Reduser tokens ved å
- lagre raw content og gjenbruke
- unngå re-prosessering av samme innhold
- kjøre AI bare på nye eller endrede objekter
- bruke korte ekstrakter i stedet for hele dokumenter der mulig
- bruke billig modell først, dyrere bare ved behov
- batch-prosessere

## 15.3 Hierarki for modellbruk

### Billig / gratis der mulig
Brukes til:
- første klassifisering
- enkel oppsummering
- tag-forslag

### Bedre modell ved behov
Brukes til:
- executive synthesis
- komplekse policytolkninger
- tverrmodulær kobling

## 15.4 Praktisk råd
Ikke bruk AI på alt råinnhold. Bruk regler og parsing først, og la AI behandle ferdig ekstraherte kandidater.

---

# 16. Mappestruktur for kodebase

En anbefalt struktur:

```text
platform/
  core/
    signal_contract/
    storage/
    notion/
    synthesis/
    learning/
    config/

  modules/
    news/
      collectors/
      processing/
      presentation/
      exports/

    opportunities/
      collectors/
      processing/
      presentation/
      exports/

    policy/
      collectors/
      processing/
      presentation/
      exports/

    projects/
    supply_chain/
    stakeholders/

  apps/
    executive_dashboard/

  jobs/
    schedules/

  docs/
```

Dette støtter:
- modulær utvikling
- separat drift av moduler
- felles topplag senere

---

# 17. Praktisk implementering modul for modul

## 17.1 Bygg én modul som et komplett vertikalt snitt
For hver modul:
1. definer kilder
2. bygg collector
3. lag raw storage
4. bygg prosessering
5. eksporter signaler
6. bygg enkelt UI
7. koble til LinkedIn idea export

Dette er bedre enn å prøve å bygge all infrastruktur først.

## 17.2 Når en modul er stabil
Gå videre til neste modul.

## 17.3 Når 2–3 moduler er stabile
Bygg topplaget.

---

# 18. Hva systemet egentlig er

Den mest presise beskrivelsen er:

**A modular offshore wind intelligence platform with domain-specific standalone modules, a shared signal contract, AI-assisted synthesis, and a human-validated learning layer.**

På norsk:

**En modulær intelligence-plattform for offshore vind med selvstendige domenemoduler, et felles signalformat, AI-assistert syntese og et læringslag med menneskelig validering.**

---

# 19. Anbefalt v1-prioritet

## Must
- News
- Opportunities
- Policy
- signal contract
- LinkedIn idea export

## Should
- Executive dashboard
- learning interface (enkel)
- Notion sync improvements

## Later
- Projects
- Supply Chain
- Stakeholders
- more advanced semantic linking

---

# 20. Endelig byggelogikk

Den riktige arbeidsrekkefølgen er:

1. Bygg modulene som egne enheter
2. Sørg for at de presenterer egne signaler tydelig
3. Eksporter standardiserte signaler
4. Bygg et executive/topplag over dem
5. Legg til AI-syntese og læring gradvis

Ikke bygg en tung monolitt først.
Ikke bygg full autonomi først.
Bygg observerende domener først, syntese etterpå.

---

# 21. Kort oppsummering

Dette systemet skal:
- bygges modul for modul
- la hver modul fungere alene
- ha eget presentasjonslag per modul
- kunne samles i et executive/index/topplag
- være portabelt og leverandøruavhengig
- være kostnadsbevisst på AI og tokens
- bruke AI som forståelses- og synteselag, ikke som eneste sannhetskilde
- gi grunnlag for både intelligence og LinkedIn-drevet brand building

---

End of document

