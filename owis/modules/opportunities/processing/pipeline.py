from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


PRIMARY_MARKETS = {"NOR", "DNK", "GBR"}
SECONDARY_MARKETS = {
    "DEU",
    "NLD",
    "SWE",
    "BEL",
    "MEX",
    "CHL",
    "COL",
    "IND",
    "AUS",
    "ARE",
    "SAU",
}


def _clean_text(raw_text: str) -> str:
    return re.sub(r"\s+", " ", raw_text or "").strip()


def _summary(text: str) -> str:
    if not text:
        return "No summary available."
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:2]).strip()[:450]


def _detect_family(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ["grant", "funding", "support scheme", "horizon", "innovation"]):
        return "funding_calls"
    if any(k in lower for k in ["tender", "procurement", "rfp", "framework agreement"]):
        return "procurement_tenders"
    if any(k in lower for k in ["auction", "leasing", "cfd", "prequalification", "round"]):
        return "market_competitions"
    if any(k in lower for k in ["pilot", "demonstration", "program", "eoi", "rfi"]):
        return "strategic_programs"
    return "other"


def _detect_mechanism(text: str) -> str:
    lower = text.lower()
    if "cfd" in lower:
        return "cfd_auction"
    if any(k in lower for k in ["prequalification", "pre-qualification"]):
        return "prequalification"
    if any(k in lower for k in ["tender", "rfp", "call for tender"]):
        return "tender"
    if any(k in lower for k in ["grant", "funding call", "subsidy"]):
        return "grant"
    if any(k in lower for k in ["eoi", "rfi"]):
        return "eoi_rfi"
    return "notice"


def _extract_deadline(text: str) -> str | None:
    if not text:
        return None

    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso_match:
        return iso_match.group(1)

    dmy_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", text)
    if dmy_match:
        day = int(dmy_match.group(1))
        month = int(dmy_match.group(2))
        year = int(dmy_match.group(3))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    month_map = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    text_lower = text.lower()
    month_match = re.search(
        r"\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(20\d{2})\b",
        text_lower,
    )
    if month_match:
        day = int(month_match.group(1))
        month = month_map[month_match.group(2)]
        year = int(month_match.group(3))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


def _days_to_deadline(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        due = datetime.strptime(deadline, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (due - now).days
    except ValueError:
        return None


def _recommended_action(fit: str, deadline: str | None, matched_services: list[str]) -> str:
    days_left = _days_to_deadline(deadline)
    if days_left is not None and days_left <= 10:
        return "Escalate now: prepare bid/no-bid decision and assign owner within 24h."
    if fit == "Strong":
        return "Prepare qualification note and shortlist for bid/no-bid review this week."
    if matched_services:
        return "Run a fast capability check against matched services before deeper pursuit."
    return "Monitor this notice and reassess when more context or documents are available."


def _why_it_matters(family: str, mechanism: str, country: str, fit: str) -> str:
    location = country or "target markets"
    return (
        f"This signal indicates a {family.replace('_', ' ')} opportunity via {mechanism.replace('_', ' ')} "
        f"in {location}. Strategic fit is {fit.lower()}, so it can influence near-term pipeline prioritization."
    )


def _country_score(country: str) -> int:
    upper = (country or "").upper()
    if upper in PRIMARY_MARKETS:
        return 10
    if upper in SECONDARY_MARKETS:
        return 5
    return 2


def classify_notice(
    notice: dict[str, Any],
    profile_bundle: dict[str, Any],
    active_profiles: list[str],
) -> dict[str, Any] | None:
    description = (notice.get("description") or "").lower()
    country = str(notice.get("country") or "").upper()

    best: dict[str, Any] | None = None

    for profile_name in active_profiles:
        company_profiles = profile_bundle.get("by_company", {}).get(profile_name, [])
        if not company_profiles:
            continue

        negative_terms: set[str] = set()
        for profile in company_profiles:
            negative_terms.update(profile.get("negative_keywords") or [])
        if any(term in description for term in negative_terms):
            continue

        qualifier_terms: set[str] = set()
        for profile in company_profiles:
            qualifier_terms.update(profile.get("qualifier") or [])

        matched_qualifiers = sorted(term for term in qualifier_terms if term in description)
        if not matched_qualifiers:
            continue

        matched_profiles = [
            profile
            for profile in company_profiles
            if any(keyword in description for keyword in profile.get("keywords") or [])
        ]
        if not matched_profiles:
            continue

        score = _country_score(country) + len(matched_profiles) * 3
        strategic_fit = "Strong" if score >= 15 else ("Medium" if score >= 8 else "Weak")
        competition_level = "Low" if country == "NOR" else ("Medium" if country in {"DNK", "GBR"} else "High")

        candidate = {
            "profile_name": profile_name,
            "matched_services": sorted(
                {
                    str(profile.get("name") or "")
                    for profile in matched_profiles
                    if str(profile.get("name") or "").strip()
                }
            ),
            "matched_qualifiers": matched_qualifiers,
            "strategic_fit": strategic_fit,
            "competition_level": competition_level,
            "fit_score": score,
        }

        if best is None or candidate["fit_score"] > best["fit_score"]:
            best = candidate

    return best


def process_raw_item(
    raw: dict[str, Any],
    profile_bundle: dict[str, Any],
    active_profiles: list[str],
) -> dict[str, Any] | None:
    text = _clean_text(
        f"{raw.get('title_raw') or ''}. {raw.get('description_raw') or ''}. {raw.get('buyer_raw') or ''}"
    )
    classification = classify_notice(
        {
            "description": text.lower(),
            "country": raw.get("country_raw") or "",
        },
        profile_bundle=profile_bundle,
        active_profiles=active_profiles,
    )
    if classification is None:
        return None

    family = _detect_family(text)
    mechanism = _detect_mechanism(text)

    detected_deadline = _extract_deadline(text)
    publication_date = str(raw.get("publication_date") or "")
    deadline = detected_deadline or None

    fit_score = int(classification.get("fit_score") or 0)
    score = fit_score + (8 if family in {"market_competitions", "procurement_tenders"} else 4)
    if deadline:
        days_left = _days_to_deadline(deadline)
        if days_left is not None:
            if days_left < 0:
                score -= 10
            elif days_left <= 14:
                score += 12
            elif days_left <= 45:
                score += 6

    score = max(0, min(100, score))

    strategic_fit = str(classification.get("strategic_fit") or "Weak")
    confidence = 0.78 if strategic_fit == "Strong" else (0.67 if strategic_fit == "Medium" else 0.58)

    matched_services = classification.get("matched_services") or []
    matched_qualifiers = classification.get("matched_qualifiers") or []

    return {
        "raw_item_id": raw["id"],
        "title": raw.get("title_raw") or "Untitled opportunity",
        "source_name": raw.get("source_name") or "Unknown",
        "source_url": raw.get("notice_url") or "",
        "buyer": raw.get("buyer_raw") or "",
        "country": raw.get("country_raw") or "",
        "summary": _summary(text),
        "opportunity_family": family,
        "mechanism_type": mechanism,
        "deadline": deadline,
        "strategic_fit": strategic_fit,
        "competition_level": str(classification.get("competition_level") or "High"),
        "matched_services": ",".join(matched_services),
        "matched_qualifiers": ",".join(matched_qualifiers),
        "recommended_action": _recommended_action(strategic_fit, deadline, matched_services),
        "why_it_matters": _why_it_matters(family, mechanism, str(raw.get("country_raw") or ""), strategic_fit),
        "signal_score": score,
        "confidence": confidence,
        "profile_name": str(classification.get("profile_name") or ""),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "published_at": publication_date,
    }