# Offshore Wind Intelligence System – Build Order, File Structure & News Module v1

## 1. Formål

Dette dokumentet bryter ned masterstrukturen til en **praktisk byggeplan** som kan brukes direkte til utvikling modul for modul.

Dokumentet dekker:

- anbefalt build order
- fil- og mappestruktur
- kjernedatamodeller
- signal contract v1
- praktisk implementeringsrekkefølge
- detaljert spesifikasjon for **News module v1**

Målet er at dette skal kunne brukes direkte som grunnlag for koding med LLM, særlig i små og kostnadseffektive steg.

---

# 2. Anbefalt build order

## Fase 0 – Foundation

Bygg minimum felles infrastruktur som alle moduler trenger.

### Leveranser

- konfigurasjonsstruktur
- enkel lagring
- source registry-format
- signal contract v1
- enkel Notion export helper
- enkel frontend shell / base layout

### Output

En liten, stabil kjerne som senere moduler kan bruke uten å bli monolittisk.

---

## Fase 1 – News module v1

Bygg første komplette modul som et vertikalt snitt.

### Leveranser

- news source registry
- RSS fetcher
- enkel article fetcher/parser
- raw storage
- summarization/classification pipeline
- signal export
- egen modulvisning
- LinkedIn idea export

### Resultat

Første fungerende modul som både står alene og eksporterer standardiserte signaler.

---

## Fase 2 – Opportunities module v1

Bygg andre modul med fokus på konkrete muligheter.

### Leveranser

- source registry for opportunities
- collectors for utvalgte kilder
- mechanism classification
- deadline/relevance extraction
- signal export
- egen visning

### Resultat

Første action-oriented modul.

---

## Fase 3 – Regulatory & Policy module v1

Bygg tredje modul med fokus på rammeverk og implikasjoner.

### Leveranser

- source registry for policy sources
- collectors
- classification by jurisdiction / policy type
- implications logic
- signal export
- egen visning

### Resultat

Tredje stabile modul og grunnlag for topplag.

---

## Fase 4 – Top layer / Executive brief v1

Bygg første samlelag når 2–3 moduler fungerer.

### Leveranser

- signal aggregator
- top signal ranking
- executive summary
- emerging themes
- top LinkedIn ideas
- enkel cross-module visning

---

## Fase 5 – Learning layer v1

Bygg brukerbekreftelse av koblinger og signaler.

### Leveranser

- suggested links
- confirm / reject
- lagring av feedback
- enkel admin / review-visning

---

# 3. Praktisk arkitekturvalg

## 3.1 Anbefalt stack i tidlig fase

### Backend

- Python
- FastAPI

### Frontend

- enkel React + Vite
- alternativt enkel server-rendered løsning hvis du vil minimere kompleksitet

### Database

- SQLite i tidlig fase
- senere Postgres ved behov

### Jobs

- cron eller GitHub Actions
- eventuelt enkel scheduler på VPS

### Notion

- Notion API for LinkedIn idea DB og eventuelt enkel signal-logg

### AI

- billigste fornuftige API eller lokal modell senere
- AI kun på nye eller endrede objekter

---

# 4. Fil- og mappestruktur

Dette er anbefalt struktur for hele kodebasen.

```text
platform/
  README.md
  requirements.txt
  .env.example

  core/
    config/
      settings.py
      source_registry_schema.md

    storage/
      db.py
      models.py
      migrations/

    signals/
      signal_contract.py
      signal_mapper.py

    notion/
      notion_client.py
      linkedin_export.py

    llm/
      client.py
      prompts/
        summarise.txt
        classify_signal.txt
        linkedin_angle.txt
        why_it_matters.txt

    utils/
      dates.py
      hashing.py
      text.py
      urls.py

  modules/
    news/
      README.md
      registry/
        sources.yaml

      collectors/
        rss_fetcher.py
        article_fetcher.py
        source_scanner.py

      parsing/
        article_parser.py
        cleaner.py

      processing/
        summarise.py
        classify.py
        scoring.py
        linkedin.py
        export_signals.py

      storage/
        models.py
        repository.py

      presentation/
        api.py
        schemas.py

    opportunities/
      registry/
      collectors/
      parsing/
      processing/
      storage/
      presentation/

    policy/
      registry/
      collectors/
      parsing/
      processing/
      storage/
      presentation/

  apps/
    web/
      src/
        pages/
          NewsPage.tsx
          OpportunitiesPage.tsx
          PolicyPage.tsx
          ExecutivePage.tsx
        components/
        lib/

  jobs/
    run_news_fetch.py
    run_news_processing.py
    run_news_notion_export.py
    run_opportunities_fetch.py
    run_policy_fetch.py
    run_executive_refresh.py

  docs/
    architecture/
    modules/
    prompts/
```

---

# 5. Felles kjernedatamodeller

## 5.1 RawItem

Representerer et rått objekt hentet fra en kilde.

### Felter

- id
- module\_type
- source\_name
- source\_url
- item\_url
- title\_raw
- content\_raw
- content\_hash
- fetched\_at
- published\_at\_raw
- status

### Formål

- sporbarhet
- deduplisering
- reprocessing uten ny fetching

---

## 5.2 Signal

Representerer et standardisert signal eksportert fra en modul.

### Felter

- signal\_id
- module\_type
- module\_item\_id
- title n- source\_name
- source\_url
- published\_at
- country
- geography\_tags
- theme\_tags
- actors
- summary
- why\_it\_matters
- signal\_score
- confidence
- linkedin\_angle
- linkedin\_candidate
- raw\_reference
- created\_at
- updated\_at

---

## 5.3 SuggestedLink

Representerer en AI-foreslått kobling mellom signaler.

### Felter

- id
- signal\_id\_a
- signal\_id\_b
- link\_type
- rationale
- confidence
- status
- created\_at
- reviewed\_at

Status:

- suggested
- confirmed
- rejected

---

## 5.4 LinkedInIdea

Representerer en eksportert idé til Notion eller intern content queue.

### Felter

- id
- signal\_id
- title
- angle
- summary
- why\_it\_matters
- module\_type
- geography
- topic
- priority
- status
- notion\_page\_id
- created\_at

---

# 6. Signal contract v1

Alle moduler skal eksportere signaler i dette formatet.

```json
{
  "signal_id": "news_20260308_001",
  "module_type": "news",
  "module_item_id": "123",
  "title": "Example title",
  "source_name": "Recharge",
  "source_url": "https://...",
  "published_at": "2026-03-08T08:00:00Z",
  "country": "Norway",
  "geography_tags": ["Norway", "North Sea"],
  "theme_tags": ["policy", "floating wind"],
  "actors": ["Equinor", "Government"],
  "summary": "...",
  "why_it_matters": "...",
  "signal_score": 78,
  "confidence": 0.84,
  "linkedin_angle": "Possible angle for post",
  "linkedin_candidate": true,
  "raw_reference": "raw_456"
}
```

---

# 7. Praktisk utviklingsrekkefølge per modul

For hver modul skal du bygge i denne rekkefølgen:

## Steg 1 – Source registry

Definer kildene i enkel YAML eller JSON.

## Steg 2 – Raw collector

Hent nye objekter og lagre rått.

## Steg 3 – Parser

Rens innhold og trekk ut tekst.

## Steg 4 – Module processing

Kjør modulspesifikk analyse:

- oppsummering
- klassifisering
- scoring
- LinkedIn-vinkel

## Steg 5 – Signal export

Mapp moduldata til signal contract.

## Steg 6 – Presentation layer

Bygg enkel side/API for modulen.

## Steg 7 – Notion export

Eksporter utvalgte signaler til LinkedIn idea DB.

---

# 8. News module v1 – formål

News module v1 skal være første fungerende modul og gi:

- kontinuerlig innsamling av markedsnyheter
- enkel AI-assistert strukturering
- egen modulside
- LinkedIn-ideer basert på signalene
- eksport av standardiserte signaler til senere topplag

Dette er den beste første modulen fordi den:

- er relativt enkel å starte med
- gir rask synlig verdi
- bygger datapipeline-kompetanse
- gir grunnlag for senere syntese

---

# 9. News module v1 – scope

## In scope

- definert liste med nyhetskilder
- RSS-basert innhenting der mulig
- enkel article fetch ved behov
- lagring av råobjekter
- deduplisering
- enkel AI-oppsummering
- enkel tagging
- enkel scoring
- LinkedIn angle suggestion
- enkel visning av latest og top signals

## Out of scope i v1

- avansert clustering
- full entity resolution
- komplisert fulltekstsøk
- cross-module linking
- komplisert brukerstyrt review

---

# 10. News module v1 – source registry

## Format

Eksempel `sources.yaml`:

```yaml
sources:
  - name: Recharge
    homepage: https://www.rechargenews.com
    type: rss
    url: https://www.rechargenews.com/rss
    enabled: true
    geography_tags: [global, europe]
    priority: high

  - name: EnergiWatch
    homepage: https://energiwatch.no
    type: rss
    url: https://energiwatch.no/rss
    enabled: true
    geography_tags: [norway, nordics]
    priority: high

  - name: Europower
    homepage: https://www.europower.no
    type: rss
    url: https://www.europower.no/rss
    enabled: true
    geography_tags: [norway, europe]
    priority: high
```

## Minimumsfelter

- name
- type
- url
- enabled
- priority
- geography\_tags

---

# 11. News module v1 – datamodell

## 11.1 NewsRawItem

Felter:

- id
- source\_name
- feed\_item\_id
- article\_url
- title\_raw
- summary\_raw
- content\_raw
- content\_hash
- published\_at
- fetched\_at
- status

## 11.2 NewsProcessedItem

Felter:

- id
- raw\_item\_id
- title
- cleaned\_text
- summary
- theme\_tags
- geography\_tags
- actors
- why\_it\_matters
- signal\_score
- confidence
- linkedin\_angle
- linkedin\_candidate
- processed\_at

## 11.3 NewsSignalExport

Mapped til signal contract.

---

# 12. News module v1 – prosessflyt

## 12.1 Collector flow

1. les `sources.yaml`
2. hent RSS items
3. sjekk om item er nytt via hash / URL
4. lagre nytt item i raw storage

## 12.2 Parsing flow

1. hent raw item
2. fetch artikkelinnhold hvis nødvendig
3. rens tekst
4. lagre cleaned\_text

## 12.3 Processing flow

1. oppsummer artikkel
2. klassifiser tema
3. trekk ut geografi og aktører
4. generer why\_it\_matters
5. beregn signal\_score
6. generer linkedin\_angle
7. marker linkedin\_candidate true/false
8. lagre processed item
9. eksporter signal

---

# 13. News module v1 – scoring

Bruk enkel scoremodell i v1.

## Komponenter

- market impact (0–30)
- geography relevance (0–20)
- strategic relevance (0–20)
- source credibility (0–10)
- linkedin potential (0–20) optional internal helper

## Output

- signal\_score: 0–100

## Prinsipp

Hold scoren enkel i v1. Unngå overkomplisert logikk.

---

# 14. News module v1 – AI prompts

News module trenger i praksis 4 små prompttyper:

## 14.1 Summary prompt

Kort oppsummering av artikkelen i 2–4 setninger.

## 14.2 Classification prompt

Velg:

- topic
- subtopic
- geography
- actors

## 14.3 Why-it-matters prompt

Skriv kort hvorfor dette betyr noe for offshore wind market intelligence.

## 14.4 LinkedIn angle prompt

Skriv 1–3 mulige vinkler for thought leadership.

### Viktig

Promptene skal være korte og faste for å spare tokens.

---

# 15. News module v1 – API / presentasjonslag

## API-endepunkter

### `GET /api/news/latest`

Returnerer siste prosesserte artikler.

### `GET /api/news/top-signals`

Returnerer artikler med høyest score siste periode.

### `GET /api/news/item/{id}`

Returnerer detaljvisning.

### `GET /api/news/linkedin-candidates`

Returnerer signaler markert for content-idéer.

---

## UI-visning

### Side: `/news`

Sekjsoner:

- Latest
- Top signals
- By geography
- By theme
- LinkedIn candidates

### Detaljkort bør vise

- title
- source
- published\_at
- summary
- why\_it\_matters
- score
- tags
- source link
- linkedin angle

---

# 16. News module v1 – Notion export

## Formål

Bygge LinkedIn idea database parallelt med intelligence-databasen.

## Eksportlogikk

Eksporter bare items der:

- linkedin\_candidate = true eller
- signal\_score over definert terskel

## Felter til Notion

- title
- module\_type
- source\_url
- summary
- why\_it\_matters
- linkedin\_angle
- geography
- theme\_tags
- priority
- status = idea

---

# 17. Jobs for News module v1

Anbefalte jobber:

## `run_news_fetch.py`

- leser source registry
- henter nye items
- lagrer raw

## `run_news_processing.py`

- finner uprosesserte raw items
- parser og analyserer
- eksporterer signaler

## `run_news_notion_export.py`

- finner nye LinkedIn-kandidater
- eksporterer til Notion

### Eksempel på scheduler

- fetch: hver time
- processing: hver time eller annenhver time
- notion export: 2 ganger daglig

---

# 18. Kostnadskontroll i News module

## Regler

- prosesser kun nye artikler
- lagre cleaned text så du unngår ny parsing
- bruk korte prompts
- bruk billig modell for standardbehandling
- batch om mulig
- ikke kjør AI på artikler som åpenbart er irrelevante hvis enkel regel kan filtrere dem bort

## Billig før dyrt

Bruk enkel heuristikk først:

- relevante kilder
- nøkkelord
- minimum tekstlengde

Kjør AI etterpå.

---

# 19. Definition of done – News module v1

News module v1 er ferdig når den kan:

1. hente nye artikler fra definerte kilder
2. lagre råinnhold og unngå duplikater
3. oppsummere og tagge artikler
4. gi enkel signalscore
5. generere why\_it\_matters
6. generere LinkedIn-vinkel
7. vise dette i eget presentasjonslag
8. eksportere signaler i signal contract v1
9. eksportere relevante idéer til Notion

---

# 20. Neste steg etter News module v1

Når News fungerer, bygg Opportunities module med samme logikk:

- source registry
- raw collector
- parser
- classification
- signal export
- own UI

Etter News + Opportunities + Policy:

- bygg topplaget
- bygg enkel executive brief
- bygg første suggested-links engine

---

# 21. Kort konklusjon

Riktig praktisk vei videre er:

1. bygg minimal foundation
2. bygg News som første komplette vertikale modul
3. gjenbruk mønsteret for Opportunities og Policy
4. bygg topplaget først når signaler fra 2–3 moduler er stabile

Dette gir rask fremdrift, lav kostnad, høy portabilitet og god støtte for videre LLM-assistert utvikling.

---

End of document

