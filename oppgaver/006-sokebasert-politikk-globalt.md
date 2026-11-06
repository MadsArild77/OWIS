# 006 – Søkebasert politikk for flytende havvind og globale tidligfasemarkeder

> Uavhengig av 004/005, men rør bare `governance.py` og de få linjene i `morning.py` som er nevnt.

## Mål
Morgenrapportens politikkdel finner også milepæler, auksjoner og høringer i markedene der myndighetenes egne sider ikke kan leses automatisk: flytende havvind i Sør-Europa, Baltikum, Asia/Stillehavet, Amerika og Midtøsten.

## Hvorfor
Claude testet myndighetskildene 3. november 2026 ([POLICY_SOURCES.md](../POLICY_SOURCES.md)). Mange av de viktigste svarer 403, lastes med JavaScript eller nås ikke fra Norge: METI (Japan), valtioneuvosto.fi og TEM (Finland), ypen.gov.gr (Hellas), mase.gov.it (Italia), eoliennesenmer.fr (Frankrike) og departementene i Saudi-Arabia, Oman og De forente arabiske emirater. Den søkebaserte politikkdelen (`governance.py`, Tavily) når disse sidene uten egne adaptere. Den dekker i dag bare Norge, EU, Norden og deler av Europa.

## Ferdig når
- [ ] `REGIONS` i `governance.py` får disse nye radene, etter de eksisterende (rekkefølgen er prioritet, så de nye droppes først når søkebudsjettet er stramt):
  - `('Europe', ['eoliennesenmer.fr', 'cre.fr', 'ypen.gov.gr', 'herema.gr', 'dgeg.gov.pt', 'mase.gov.it', 'miteco.gob.es'], 'floating offshore wind tender auction éolien flottant eólica flotante eolico galleggiante deadline')`
  - `('Nordics', ['tem.fi', 'valtioneuvosto.fi', 'metsa.fi', 'energiavirasto.fi', 'regeringen.se', 'energimyndigheten.se'], 'offshore wind merituulivoima havsbaserad vindkraft auction permit legislation deadline')`
  - `('Europe', ['enmin.lrv.lt', 'kem.gov.lv', 'kliimaministeerium.ee', 'gov.pl', 'ure.gov.pl'], 'offshore wind auction Baltic Sea legislation deadline Lithuania Latvia Estonia Poland')`
  - `('Asia-Pacific', ['meti.go.jp', 'enecho.meti.go.jp', 'mlit.go.jp', 'motie.go.kr', 'moeaea.gov.tw', 'dcceew.gov.au', 'oir.gov.au', 'doe.gov.ph', 'moit.gov.vn', 'mnre.gov.in'], 'offshore wind auction round tender floating legislation deadline')`
  - `('Americas', ['boem.gov', 'doi.gov', 'federalregister.gov', 'gov.br', 'minenergia.gov.co'], 'offshore wind lease sale auction legislation permit deadline')`
  - `('Middle East', ['enerji.gov.tr', 'moenergy.gov.sa', 'mem.gov.om', 'moei.gov.ae', 'masdar.ae'], 'offshore wind tender feasibility memorandum auction')`
- [ ] Prompten i `extract()` sier ikke lenger at Norge/EU er det eneste fokuset for disse regionene. Regelen om at EU-vedtak ikke automatisk gjelder i Norge beholdes. Ellers ingen endring i prompt eller validering.
- [ ] Sorteringen i `morning.py` (`{'Norway': 0, 'EU': 1, 'Nordics': 2, 'Europe': 3}`) får `'Asia-Pacific': 4, 'Americas': 5, 'Middle East': 6`.
- [ ] `coverage_note` i `morning.py` nevner de nye regionene: «Norway and EU are prioritised; Nordic, European, Asia-Pacific, Americas and Middle East coverage is search-based and depends on the listed official domains.»
- [ ] Regionvelgeren på Policy & regulation har valgene Asia-Pacific, Americas og Middle East (gjør det her hvis 004 ikke er gjort ennå, ellers finnes de).
- [ ] **Rotasjon for å spare søkebudsjettet:** de seks nye radene søkes ikke hver dag. Hver morgenrapport søker to av dem etter faste par i rekkefølgen over, valgt ut fra datoen (dag i året modulo 3), slik at hver rad søkes hver tredje dag. Det gir 2 ekstra søk per rapport, rundt 60 i måneden. De åtte eksisterende radene søkes hver dag som før. En rad som ikke er på tur, gjør ingen søk, men sjekker fortsatt kjente kilder fra forrige rapport på nytt (`previous_sources`) uten at det teller mot søkebudsjettet. Finnes ingen slike kilder, får raden status `not_scheduled` i dekningen, uten advarsel.
- [ ] Søkene teller mot søkebudsjettet som før (D17). Skriv i svar-filen faktisk antall ekstra søk per morgenrapport og per måned.
- [ ] `pytest owis/tests -q` er grønn. Test (mocket søk og AI) at en ny region gir hendelser med riktig `region`, og at et treff fra et domene utenfor listen avvises (`official_url`).
- [ ] `MORNING_REPORT.md` og `POLICY_SOURCES.md` er oppdatert.

## Design (bestemt av Claude – ikke endre)
- Ingen nye kilder i registeret og ingen ny visning. Dette er bare flere søkeregioner.
- Engelske regionnavn som over, nøyaktig.

## Filer som kan endres
- `owis/modules/news/processing/governance.py`
- `owis/modules/news/processing/morning.py` (bare sortering og `coverage_note`)
- Regionvelgeren i nyhetssiden (`news.html` eller riktig `news-*.js` etter 002)
- `owis/tests/` (ny eller utvidet test)
- `MORNING_REPORT.md`, `POLICY_SOURCES.md`

## Ikke rør
- Søkebudsjettets grenser og prioritering (`search_budget.py`).
- `policy_sources.json`.

## Utenfor oppgaven
- Egne adaptere for de blokkerte sidene.
- Oversettelse av japansk, koreansk eller annet ikke-latinsk innhold utover det AI-en allerede gjør.
