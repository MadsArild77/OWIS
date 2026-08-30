# Anna O — nettside

Statisk nettside for **Anna O** (tidligere Hanskemagasinet), Strandgaten 139, Haugesund.
Ren HTML, CSS og litt JavaScript. Ingen build, ingen rammeverk, ingen database — filene
i denne mappen er nøyaktig det som ligger på serveren.

**Hvorfor så enkelt:** det gjør at siden kan legges rett inn på Hostinger uten
byggeserver, laster på under et sekund, og kan endres av hvem som helst som tør å
åpne en HTML-fil. Når dere senere vil ha kampanjesider, blogg eller bookingsystem,
står det en plan for det nederst.

---

## 1. Må gjøres før lansering

Punktene her er ting jeg **ikke** kunne verifisere. Gå gjennom dem før siden settes live.

| # | Hva | Hvor |
|---|-----|------|
| 1 | **Merkelisten.** Ligger som utkommentert HTML — fyll inn de faktiske merkene og fjern kommentartegnene. Ikke publiser merker butikken ikke fører. | `sortiment.html`, søk `MERKELISTE` |
| 2 | **Åpningstider.** Hentet fra offentlige oppføringer. Bekreft at de stemmer. | `kontakt.html`, `index.html`, footer på alle sider, `HOURS` i `assets/js/site.js` |
| 3 | **Kartkoordinater.** Markøren er satt omtrent i Haugesund sentrum. Hent nøyaktig punkt fra openstreetmap.org og bytt `bbox` og `marker`. | `kontakt.html` og `index.html`, søk `TODO` |
| 4 | **Org.nr. 912 492 842.** Bekreft mot Brønnøysund. | footer på alle sider |
| 5 | **E-postadresse.** Står som `post@hmag.no`. Skal den bli `post@annao.no` ved navnebyttet? | alle sider + JSON-LD |
| 6 | **Historikk.** Tidslinjen har bare 1926 og dagens situasjon, fordi det var det jeg fant belegg for. Fyll på med ekte årstall. | `historien.html`, søk `TODO` |
| 7 | **Bilder.** Alle bildeflater er plassholdere. Se punkt 3 under. | overalt, søk `BYTT UT` |
| 8 | **Domenevalg.** Se punkt 2 under. | `scripts/set-domain.sh` |

---

## 2. Domene

Repoet er satt opp for `annao.no`. Skal dere heller bruke `anna-o.no`:

```bash
cd annao
./scripts/set-domain.sh anna-o.no
```

Skriptet oppdaterer canonical-URL, Open Graph-tagger, `sitemap.xml` og `robots.txt`.

**Anbefaling:** registrer begge, pek den ene til den andre med 301-redirect i hPanel,
og bruk `annao.no` som hovedadresse. Den er kortest å oppgi over telefon.

**hmag.no:** ikke la den dø. Sett opp 301-redirect fra `hmag.no` til det nye domenet i
hPanel. Da arver dere søkerangeringen som er bygget opp over år, i stedet for å starte
på null. Behold redirecten i minst to år.

---

## 3. Bilder

Siden bruker plassholdere som ser bevisste ut, men de skal byttes. Hvert sted er
merket med `<!-- BYTT UT: ... -->` rett over.

Det som trengs:

| Fil | Format | Motiv |
|-----|--------|-------|
| `butikk-hero.jpg` | stående 4:5 | Butikkinteriør eller en ansatt i arbeid. Dette er det første folk ser. |
| `tilpasning.jpg` | liggende 16:10 | Prøverom eller tilpasningssituasjon, diskret |
| `tilpasning-portrett.jpg` | stående 4:5 | Portrett av en ansatt |
| `detalj.jpg` | liggende 16:10 | Nærbilde av materiale, søm eller hylle |
| `undertoy.jpg` `badetoy.jpg` `nattoy.jpg` `stromper.jpg` | liggende 16:10 | En per kategori |
| `og-bilde.jpg` | 1200×630 | Bildet som vises når noen deler lenken på Facebook |

Slik bytter du: legg filen i `assets/img/`, og erstatt hele `<div class="ph">…</div>`
med `<img src="/assets/img/filnavn.jpg" alt="Beskrivelse" width="900" height="1125" loading="lazy">`.

Komprimer bildene først — hold dem under 250 kB hver. `squoosh.app` gjør jobben gratis.

---

## 4. Legge siden ut på Hostinger

### Alternativ A — automatisk fra GitHub (anbefalt)

1. hPanel → **Websites** → domenet → **Advanced** → **GIT**
2. Repository: `https://github.com/MadsArild77/OWIS`
3. Branch: den grenen dere lander på (nå `claude/anna-o-webside-7lcg5o`)
4. **Directory:** `public_html`
5. Etter første deploy: kopier **Webhook URL**-en Hostinger gir deg, og legg den inn
   i GitHub under repoets *Settings → Webhooks*. Da oppdateres siden automatisk ved
   hver push.

> Merk: Hostingers Git-integrasjon kopierer hele repoet. Siden nettsiden ligger i
> undermappen `annao/`, er den ryddigste løsningen på sikt å flytte disse filene til
> et eget repo som bare inneholder nettsiden. Se punkt 7.

### Alternativ B — manuelt (raskest for å komme i gang i dag)

1. Lag et zip-arkiv av innholdet i `annao/` (ikke mappen selv — filene)
2. hPanel → **File Manager** → `public_html`
3. Last opp zip-en og pakk ut

### Etter deploy

- hPanel → **SSL** → installer gratis SSL-sertifikat på domenet
- Åpne `.htaccess` og fjern kommentartegnene foran HTTPS- og www-reglene
- Sjekk at `https://domenet.no/404-test` viser 404-siden

---

## 5. Slik endrer du innhold

Alt innhold står direkte i HTML-filene. Åpne filen, finn teksten, skriv om.

Det er fem sider:

| Fil | Side |
|-----|------|
| `index.html` | Forsiden |
| `tilpasning.html` | BH-tilpasning — den viktigste siden for å få folk i butikken |
| `sortiment.html` | Varekategorier og merker |
| `historien.html` | 1926 til i dag, og forklaringen på navnebyttet |
| `kontakt.html` | Adresse, åpningstider, kart |

**Viktig:** meny og footer er kopiert inn i hver fil. Endrer du menyen, må du endre
den i alle fem (og i `404.html`). Det er prisen for å slippe et build-steg — og
grunnen til at punkt 7 anbefaler et rammeverk når siden vokser.

**Rebrand-stripen** øverst («Hanskemagasinet blir Anna O») fjernes ved å slette
`<div class="ticker">…</div>` i hver fil. La den stå i minst et halvt år.

**Farger og typografi** styres ett sted: `:root` øverst i `assets/css/style.css`.
Bytter du `--wine` der, endres alt som bruker primærfargen.

---

## 6. Hvordan siden er bygget for å skape butikkbesøk

Siden selger ikke varer. Den selger *grunnen til å gå inn døren*, og det er bygget inn
i strukturen:

- **Fagkunnskapen er hovedsaken, ikke produktene.** Tilpasning har egen side, egen
  plass i menyen og egen knapp i alle CTA-er. Det er den ene tingen en nettbutikk ikke
  kan kopiere.
- **Skål A–J og fra 65 i omkrets gjentas overalt.** Det er søkeordet folk faktisk
  googler når de ikke finner noe som passer, og det er beviset på at utvalget er ekte.
- **«Vi har ikke nettbutikk» er snudd til et argument.** Det står som et bevisst valg
  begrunnet i kvalitet, ikke som en mangel.
- **Telefonnummeret er en knapp på hver eneste side**, i header, footer og i hver
  seksjon som avsluttes. Telefon er konverteringen — ikke en handlekurv.
- **Lokal SEO** er på plass: `ClothingStore`-strukturert data med adresse og
  åpningstider, så butikken kan vises riktig i Google Maps og i «åpent nå»-søk.
- **FAQ-ene svarer på det som stopper folk:** må jeg bestille time, hva koster det,
  gjelder gavekortet mitt.

---

## 7. Veien videre

Når dere er klare for en fullstendig nettside, i denne rekkefølgen:

1. **Eget repo.** Flytt disse filene ut av OWIS-repoet til `annao-web`. Gjør
   Hostinger-deployen renere og historikken lesbar.
2. **Astro eller Eleventy.** Gir felles header/footer i én fil i stedet for seks
   kopier, samtidig som output fortsatt er statiske filer som Hostinger elsker.
   Dette er det første som bør gjøres når siden får flere enn ti sider.
3. **Timebestilling.** En «book tilpasning»-knapp som faktisk booker. Setmore eller
   Calendly holder i første omgang og kan settes opp på en ettermiddag.
4. **Ekte bilder og en fotograf.** Størst enkeltløft for hvordan siden oppleves.
   Prioriter dette over ny funksjonalitet.
5. **Innhold som rangerer.** Guider av typen «slik måler du BH-størrelse» og «slik
   ser du at BH-en er for stor i bandet» trekker søk fra hele distriktet og bygger
   fagkunnskapen som er hele salgsargumentet.
6. **Google Business-profil.** Oppdater navnet fra Hanskemagasinet til Anna O
   samtidig som siden går live, ikke etterpå. Legg inn nytt domene, nye bilder og be
   om et par ferske omtaler.
7. **Nyhetsbrev.** Kundene kommer tilbake når nye leveranser lander. Et enkelt
   påmeldingsfelt koblet til Mailchimp er nok.
8. **Analyse.** Plausible eller Fathom framfor Google Analytics — enklere, og ingen
   cookiebanner.

---

## 8. Teknisk

- Ingen avhengigheter, ingen `node_modules`, ingen byggesteg
- Fungerer uten JavaScript — JS legger bare til mobilmeny, innfading og «åpent nå»
- Respekterer `prefers-reduced-motion`
- Fonter lastes fra Google Fonts. Skal dere være helt trygge på GDPR, last ned
  `Cormorant Garamond` og `Inter` til `assets/fonts/` og bytt `<link>`-en mot
  `@font-face`. Da forsvinner også et eksternt kall og siden blir raskere.
- Ingen sporing, ingen cookies, ingen cookiebanner nødvendig slik den står nå

### Kjøre lokalt

```bash
cd annao
python3 -m http.server 8000
# åpne http://localhost:8000
```

Bruk en server, ikke `file://` — lenkene er absolutte (`/kontakt.html`).
