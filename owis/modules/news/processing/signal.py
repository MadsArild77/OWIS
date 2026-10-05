"""Focus classification and signal scoring for market insight.

Offshore wind is the primary focus. Grid, power markets, energy policy, maritime
and supply chain are related areas. Other energy (oil and gas, solar, EVs, nuclear)
is kept but ranked low. The score follows the specification's components so a
reader can see why a story ranks where it does.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SCORING_VERSION = "2026-10-06.1"


def _terms(*words: str) -> list[re.Pattern]:
    """Whole-word patterns; a trailing * allows Norwegian compounds (havvind*)."""
    patterns = []
    for word in words:
        stem = word.rstrip("*").lower()
        tail = "" if word.endswith("*") else r"(?![\w])"
        patterns.append(re.compile(rf"(?<![\w]){re.escape(stem)}{tail}"))
    return patterns


OFFSHORE_WIND = _terms(
    "offshore wind", "offshore-wind", "havvind*", "floating wind", "floating offshore", "flytende vind*",
    "vindkraft til havs", "vind til havs", "offshore turbine*", "offshore wind farm*", "wind turbine installation vessel*",
    "wtiv", "monopile*", "inter-array", "export cable*", "offshore substation*", "utsira nord", "sørlige nordsjø*",
    "sorlige nordsjo*", "dogger bank", "hornsea", "hywind", "borkum", "east anglia", "crown estate", "seabed lease*",
)
RELATED = {
    "Grid": _terms("grid", "power grid", "strømnett*", "kraftnett*", "transmission", "interconnector*", "utenlandskabel*",
                   "substation*", "statnett", "tennet", "nettilknytning*", "nettkapasitet*"),
    "Power market": _terms("power market*", "electricity market*", "kraftmarked*", "strømmarked*", "strømpris*", "kraftpris*",
                           "power price*", "electricity price*", "norgespris*", "prisområde*", "ppa", "ppas"),
    "Electrification": _terms("electrification", "elektrifisering*", "kraftbehov*", "power demand", "data centre*", "data center*",
                              "datasenter*", "datasentre*"),
    "Energy policy": _terms("energy policy", "energipolitikk*", "energy security", "forsyningssikkerhet*", "kraftbalanse*",
                            "energy ministry", "energidepartementet", "energy minister", "energiminister*", "support scheme*",
                            "støtteordning*", "contract for difference", "contracts for difference", "cfd", "cfds",
                            "differansekontrakt*", "state aid", "statsstøtte*"),
    "Maritime": _terms("maritime", "maritim*", "shipping", "shipyard*", "verft*", "vessel*", "fartøy*", "port", "ports", "havn*",
                       "harbour*", "harbor*"),
    "Supply chain": _terms("supply chain*", "leverandørindustri*", "leverandørkjede*", "supplier*", "fabrication", "fabrikk*",
                           "factory", "factories"),
    "Wind": _terms("wind farm*", "wind power", "wind energy", "wind turbine*", "vindkraft*", "vindpark*", "onshore wind"),
    "Hydrogen": _terms("hydrogen", "electrolyser*", "electrolyzer*", "ammonia"),
}
OTHER_ENERGY = _terms(
    "oil", "gas", "lng", "petroleum", "upstream", "drilling", "olje*", "gass*", "solar", "solcelle*", "photovoltaic",
    "electric vehicle*", "ev", "evs", "elbil*", "nuclear", "kjernekraft*", "coal", "kull", "lithium", "charging station*",
)
IMPACT = {
    "Investment decision": _terms("final investment decision", "fid", "investeringsbeslutning*"),
    "Contract or order": _terms("contract*", "awarded", "award*", "orders", "ordered", "order for", "order from", "kontrakt*", "tildel*", "signs", "signed", "selected"),
    "Auction or tender": _terms("auction*", "tender*", "lease round", "leasing round", "auksjon*", "utlysning*", "anbud*",
                                "prequalif*", "prekvalifis*"),
    "Approval or permit": _terms("consent", "approved", "approval", "permit*", "konsesjon*", "godkjen*", "licence*", "license*"),
    "Deal or financing": _terms("acquire*", "acquisition*", "merger", "stake", "financing", "finance deal", "funding", "raises",
                                "oppkjøp*", "finansiering*", "investment*", "investering*"),
    "Setback": _terms("cancel*", "scrap*", "delay*", "postpone*", "halt*", "bankrupt*", "layoff*", "writedown*", "write-down*",
                      "impairment*", "avlys*", "utsett*", "konkurs*", "nedskriv*", "permitter*"),
    "Policy decision": _terms("law", "bill", "budget", "regulation*", "directive", "consultation", "høring*", "stortinget",
                              "regjeringen", "parliament", "subsid*", "statsbudsjett*"),
}
CAPACITY = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:gw|mw)\b", re.IGNORECASE)

GEO_WEIGHT = {
    "Norway": 15,
    **dict.fromkeys(["Nordics", "North Sea", "Denmark", "Sweden", "Finland", "Iceland", "Baltic Sea"], 12),
    **dict.fromkeys(["UK", "EU", "Germany", "Netherlands", "Belgium", "Poland", "Ireland", "France", "Baltics"], 11),
    **dict.fromkeys(["Europe", "Spain", "Portugal", "Italy"], 9),
    **dict.fromkeys(["USA", "Japan", "South Korea", "Taiwan", "Australia", "Canada", "Brazil"], 6),
    "Global": 5,
}
# Lower-case fragment of the source name -> credibility for offshore wind market news.
SOURCE_WEIGHT = {
    "recharge": 10, "offshorewind": 10, "offshore wind": 10, "windpower monthly": 10, "europower": 10, "montel": 10,
    "4c offshore": 10, "energiwatch": 9, "reuters": 9, "bloomberg": 9, "financial times": 9, "upstream": 8, "e24": 8,
    "teknisk ukeblad": 8, "tu.no": 8, "windeurope": 8, "gwec": 8, "renewables now": 7, "energy voice": 7,
    "windpowernl": 6, "energy live news": 6, "clean technica": 4, "cleantechnica": 4, "renewable watch": 4,
}
FOCUS_POINTS = {"offshore_wind": 35, "adjacent_energy": 20, "other_energy": 5}


def _hits(text: str, patterns: list[re.Pattern]) -> int:
    return sum(1 for pattern in patterns if pattern.search(text))


@dataclass
class Focus:
    bucket: str
    confidence: float
    areas: list[str] = field(default_factory=list)


def classify_focus(text: str) -> Focus:
    lower = str(text or "").lower()
    offshore = _hits(lower, OFFSHORE_WIND)
    areas = [name for name, patterns in RELATED.items() if _hits(lower, patterns)]
    other = _hits(lower, OTHER_ENERGY)
    if offshore:
        return Focus("offshore_wind", 0.92 if offshore >= 2 else 0.84, ["Offshore wind", *areas])
    if areas and other <= len(areas) * 2:
        return Focus("adjacent_energy", 0.85 if len(areas) >= 2 else 0.75, areas)
    if other:
        return Focus("other_energy", 0.86 if other >= 2 else 0.72, areas)
    return Focus("other_energy", 0.5, areas)


_LEARNED_SOURCE_WEIGHT: dict[str, int] = {}


def set_learned_source_weights(weights: dict[str, int]) -> None:
    """Weights learned from each source's observed relevance (see registry.source_advisor)."""
    _LEARNED_SOURCE_WEIGHT.clear()
    _LEARNED_SOURCE_WEIGHT.update({str(k): int(v) for k, v in (weights or {}).items()})


def source_weight(source_name: str, learned: bool = True) -> int:
    if learned and source_name in _LEARNED_SOURCE_WEIGHT:
        return _LEARNED_SOURCE_WEIGHT[source_name]
    name = str(source_name or "").lower()
    return next((weight for key, weight in SOURCE_WEIGHT.items() if key in name), 6)


def evidence_weight(basis: dict | None, text: str) -> int:
    """Small bonus for verified text; a paywall alone must not push an important story down."""
    kind = (basis or {}).get("basis")
    if kind in {"fulltext", "alternative_fulltext"}:
        return 10
    if kind == "feed_text" or len(text or "") >= 1500:
        return 8
    return 6


def score_signal(title: str, text: str, geographies: list[str], actors: list[str],
                 source_name: str = "", basis: dict | None = None) -> tuple[int, Focus, list[str]]:
    """Return score (0-100), focus and short reasons a reader can understand."""
    blob = f"{title} {text}".lower()
    focus = classify_focus(blob)
    reasons = [{"offshore_wind": "Offshore wind", "adjacent_energy": " / ".join(focus.areas[:2]) or "Related energy",
                "other_energy": "Other energy"}[focus.bucket]]
    score = FOCUS_POINTS[focus.bucket] if focus.confidence > 0.5 else 0

    impacts = [name for name, patterns in IMPACT.items() if _hits(blob, patterns)]
    impact = min(len(impacts) * 8, 24) + (6 if CAPACITY.search(blob) else 0)
    score += min(impact, 30)
    reasons += impacts[:2]

    geo_points = max((GEO_WEIGHT.get(g, 3) for g in geographies), default=5)
    score += geo_points
    best_geo = max(geographies, key=lambda g: GEO_WEIGHT.get(g, 3), default="")
    if geo_points >= 11:
        reasons.append(best_geo)

    # The story decides the score; the source only adds a little confidence (0-5).
    source_points = round(source_weight(source_name) / 2)
    score += source_points
    if source_points >= 5:
        reasons.append("Trade press")

    score += evidence_weight(basis, text)
    score += 5 if len(actors) >= 2 else 3 if actors else 0
    return max(0, min(score, 100)), focus, reasons


def is_linkedin_candidate(score: int, focus: Focus) -> bool:
    return score >= 70 and focus.bucket != "other_energy"
