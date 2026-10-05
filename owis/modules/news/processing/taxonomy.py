"""Fixed vocabulary for geographies, actors and themes.

AI output and keyword rules both pass through here so filters show one name per
place, company and theme ("UK", never also "United Kingdom" or "uk").
"""
from __future__ import annotations

import re

# Lower-case alias -> canonical name. Short aliases are matched as whole words.
GEO_ALIASES: dict[str, str] = {
    "norway": "Norway", "norwegian": "Norway", "norge": "Norway", "norsk": "Norway", "norske": "Norway",
    "denmark": "Denmark", "danish": "Denmark", "danmark": "Denmark",
    "sweden": "Sweden", "swedish": "Sweden", "sverige": "Sweden",
    "finland": "Finland", "finnish": "Finland",
    "iceland": "Iceland",
    "uk": "UK", "u.k.": "UK", "united kingdom": "UK", "britain": "UK", "great britain": "UK", "british": "UK",
    "england": "UK", "scotland": "UK", "scottish": "UK", "wales": "UK", "welsh": "UK", "storbritannia": "UK",
    "ireland": "Ireland", "irish": "Ireland",
    "germany": "Germany", "german": "Germany", "tyskland": "Germany",
    "netherlands": "Netherlands", "dutch": "Netherlands", "nederland": "Netherlands", "holland": "Netherlands",
    "belgium": "Belgium", "belgian": "Belgium",
    "france": "France", "french": "France", "frankrike": "France",
    "spain": "Spain", "spanish": "Spain", "portugal": "Portugal", "portuguese": "Portugal",
    "italy": "Italy", "italian": "Italy", "poland": "Poland", "polish": "Poland",
    "estonia": "Baltics", "latvia": "Baltics", "lithuania": "Baltics", "baltic states": "Baltics", "baltics": "Baltics",
    "eu": "EU", "european union": "EU", "european commission": "EU", "brussels": "EU", "eea": "EU", "eøs": "EU",
    "europe": "Europe", "european": "Europe", "europa": "Europe",
    "nordics": "Nordics", "nordic": "Nordics", "norden": "Nordics", "scandinavia": "Nordics",
    "north sea": "North Sea", "nordsjøen": "North Sea", "baltic sea": "Baltic Sea", "østersjøen": "Baltic Sea",
    "usa": "USA", "u.s.": "USA", "united states": "USA", "america": "USA", "american": "USA",
    "canada": "Canada", "brazil": "Brazil", "australia": "Australia",
    "japan": "Japan", "japanese": "Japan", "south korea": "South Korea", "korea": "South Korea", "korean": "South Korea",
    "taiwan": "Taiwan", "taiwanese": "Taiwan", "china": "China", "chinese": "China", "kina": "China",
    "india": "India", "indian": "India", "vietnam": "Vietnam", "philippines": "Philippines",
    "global": "Global", "worldwide": "Global", "international": "Global",
    "rogaland": "Norway", "haugalandet": "Norway", "karmøy": "Norway", "karmoy": "Norway", "bergen": "Norway", "stavanger": "Norway",
    "utsira": "Norway", "vestland": "Norway",
}

# Canonical actor -> aliases. Matching ignores case; short names are whole words only.
ACTORS: dict[str, list[str]] = {
    "Equinor": ["equinor"], "Ørsted": ["ørsted", "orsted"], "RWE": ["rwe"], "Vattenfall": ["vattenfall"],
    "Statkraft": ["statkraft"], "Statnett": ["statnett"], "Hafslund": ["hafslund"], "Aker Solutions": ["aker solutions"],
    "Aker Horizons": ["aker horizons"], "Vårgrønn": ["vårgrønn", "vargronn"], "Deep Wind Offshore": ["deep wind offshore"],
    "Fred. Olsen": ["fred. olsen", "fred olsen"], "Odfjell": ["odfjell"], "Kongsberg": ["kongsberg"],
    "Moreld": ["moreld"], "Havfram": ["havfram"], "Ventyr": ["ventyr"], "Norsk Havvind": ["norsk havvind"],
    "TotalEnergies": ["totalenergies"], "BP": ["bp"], "Shell": ["shell"], "Iberdrola": ["iberdrola"],
    "ScottishPower": ["scottishpower", "scottish power"], "SSE": ["sse renewables", "sse"], "EnBW": ["enbw"],
    "Ocean Winds": ["ocean winds"], "Corio": ["corio generation", "corio"], "CIP": ["copenhagen infrastructure partners", "cip"],
    "Northland Power": ["northland power"], "Parkwind": ["parkwind"], "BlueFloat": ["bluefloat"],
    "Principle Power": ["principle power"], "BW Ideol": ["bw ideol"], "Hexicon": ["hexicon"],
    "Siemens Gamesa": ["siemens gamesa"], "Siemens Energy": ["siemens energy"], "Vestas": ["vestas"],
    "GE Vernova": ["ge vernova"], "Nordex": ["nordex"], "Mingyang": ["mingyang", "ming yang"],
    "Goldwind": ["goldwind"], "Envision": ["envision energy"],
    "Prysmian": ["prysmian"], "Nexans": ["nexans"], "NKT": ["nkt"], "Hitachi Energy": ["hitachi energy"],
    "Cadeler": ["cadeler"], "DEME": ["deme"], "Van Oord": ["van oord"], "Jan De Nul": ["jan de nul"],
    "Boskalis": ["boskalis"], "Seaway7": ["seaway7", "seaway 7"], "Subsea7": ["subsea7", "subsea 7"],
    "Sif": ["sif group"], "Smulders": ["smulders"], "Navantia": ["navantia"], "Windar": ["windar"],
    "Crown Estate": ["crown estate"], "TenneT": ["tennet"], "Energinet": ["energinet"], "National Grid": ["national grid"],
    "NVE": ["nve"], "ESA": ["esa"], "Enova": ["enova"], "Offshore Norge": ["offshore norge"],
    "Norwegian Offshore Wind": ["norwegian offshore wind"], "WindEurope": ["windeurope"], "GWEC": ["gwec"],
    "European Commission": ["european commission", "eu commission"],
}

# Lower-case theme synonyms (often from AI output) -> canonical theme key.
THEME_ALIASES: dict[str, str] = {
    "offshore wind": "offshore_wind", "offshore wind energy": "offshore_wind", "offshore wind power": "offshore_wind",
    "havvind": "offshore_wind", "floating wind": "floating_wind", "floating offshore wind": "floating_wind",
    "flytende havvind": "floating_wind", "wind energy": "wind", "wind power": "wind", "vindkraft": "wind",
    "onshore wind": "onshore_wind", "renewable energy": "renewables", "renewables": "renewables",
    "fornybar energi": "renewables", "energy transition": "energy_transition", "energiomstilling": "energy_transition",
    "grid": "grid", "power grid": "grid", "electricity grid": "grid", "strømnett": "grid", "transmission": "grid",
    "electrification": "electrification", "elektrifisering": "electrification",
    "power market": "power_market", "electricity market": "power_market", "power prices": "power_market",
    "energy policy": "policy", "regulation": "policy", "politics": "policy",
    "maritime": "maritime", "shipping": "maritime", "ports": "ports", "port": "ports",
    "supply chain": "supply_chain", "investment": "finance", "investments": "finance", "financing": "finance",
    "hydrogen": "hydrogen", "solar": "solar", "solar energy": "solar", "solar power": "solar",
    "battery storage": "batteries", "energy storage": "batteries", "batteries": "batteries",
    "electric vehicles": "electric_vehicles", "ev": "electric_vehicles", "oil and gas": "oil_gas",
    "oil & gas": "oil_gas", "petroleum": "oil_gas", "nuclear": "nuclear", "nuclear power": "nuclear",
}


def _pattern(alias: str) -> re.Pattern:
    escaped = re.escape(alias.lower())
    return re.compile(rf"(?<![\w]){escaped}(?![\w])")


_GEO_PATTERNS = [(_pattern(alias), name) for alias, name in GEO_ALIASES.items()]
_ACTOR_PATTERNS = [(_pattern(alias), name) for name, aliases in ACTORS.items() for alias in aliases]
_ACTOR_LOOKUP = {alias: name for name, aliases in ACTORS.items() for alias in [name.lower(), *aliases]}


def _unique(values):
    seen, out = set(), []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def canonical_geo(value: str) -> str:
    text = str(value or "").strip()
    return GEO_ALIASES.get(text.lower(), text[:1].upper() + text[1:] if text.islower() else text)


def normalize_geographies(values) -> list[str]:
    names = _unique(canonical_geo(v) for v in values if str(v or "").strip())
    specific = [n for n in names if n != "Global"]
    return specific or ["Global"]


def extract_geographies(text: str) -> list[str]:
    lower = str(text or "").lower()
    return normalize_geographies([name for pattern, name in _GEO_PATTERNS if pattern.search(lower)])


_COMPANY_SUFFIX = re.compile(r"[\s,]+(asa|as|a/s|plc|ltd|limited|ag|se|gmbh|inc|n\.?v\.?|b\.?v\.?|group)\.?$", re.IGNORECASE)


def canonical_actor(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    known = _ACTOR_LOOKUP.get(text.lower()) or _ACTOR_LOOKUP.get(_COMPANY_SUFFIX.sub("", text).lower())
    return known or text


def normalize_actors(values) -> list[str]:
    return _unique(canonical_actor(v) for v in values if str(v or "").strip())


def extract_actors(text: str) -> list[str]:
    lower = str(text or "").lower()
    return _unique(name for pattern, name in _ACTOR_PATTERNS if pattern.search(lower))


def canonical_theme(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return THEME_ALIASES.get(text, re.sub(r"[^\w]+", "_", text).strip("_"))


def normalize_themes(values) -> list[str]:
    return _unique(canonical_theme(v) for v in values if str(v or "").strip())


_NORWEGIAN_WORDS = re.compile(r"(?<![\w])(og|ikke|det|som|til|fra|med|for|har|skal|vil|kan|strøm|kraft\w*)(?![\w])")


def looks_norwegian(text: str) -> bool:
    lower = str(text or "").lower()
    hits = len(_NORWEGIAN_WORDS.findall(lower))
    return hits >= 5 or (hits >= 3 and any(ch in lower for ch in "æøå"))


def geographies_for(title: str, text: str, given=None) -> list[str]:
    """Canonical geographies from AI/stored tags, else the opening text; Norwegian-language stories default to Norway."""
    geos = normalize_geographies(given or [])
    if geos == ["Global"]:
        geos = extract_geographies(f"{title} {str(text or '')[:1200]}")
    if geos == ["Global"] and looks_norwegian(f"{title} {str(text or '')[:1200]}"):
        geos = ["Norway"]
    return geos
