from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from owis.core.config.settings import OPPORTUNITIES_ACTIVE_PROFILES, OPPORTUNITIES_PROFILES_PATH


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip().lower() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip().lower() for x in value.split(",") if x.strip()]
    return []


def _clean_cpv(codes: list[str]) -> list[str]:
    valid: list[str] = []
    for code in codes:
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if len(digits) != 8:
            continue
        if digits == "00000000" or digits.endswith("999999"):
            continue
        if digits not in valid:
            valid.append(digits)
    return valid


def load_profile_bundle(active_profiles: list[str] | None = None) -> dict[str, Any]:
    active = [p.strip().upper() for p in (active_profiles or OPPORTUNITIES_ACTIVE_PROFILES) if p.strip()]
    active_set = set(active)

    path = Path(OPPORTUNITIES_PROFILES_PATH)
    if not path.exists():
        return {
            "by_company": {},
            "all_cpv_codes": [],
            "all_qualifiers": [],
            "cpv_by_company": {},
            "qualifiers_by_company": {},
            "keywords_by_company": {},
        }

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("profiles") if isinstance(raw, dict) else []

    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_cpv_codes: set[str] = set()
    all_qualifiers: set[str] = set()
    cpv_by_company: dict[str, set[str]] = defaultdict(set)
    qualifiers_by_company: dict[str, set[str]] = defaultdict(set)
    keywords_by_company: dict[str, set[str]] = defaultdict(set)

    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue

        company = str(row.get("company") or "").strip().upper()
        if not company:
            continue
        if active_set and company not in active_set:
            continue

        name = str(row.get("name") or company).strip()
        category = str(row.get("category") or "Other").strip()

        keywords = _clean_list(row.get("keywords"))
        aliases = _clean_list(row.get("aliases"))
        qualifiers = _clean_list(row.get("qualifier"))
        negatives = _clean_list(row.get("negative_keywords"))
        cpv_codes = _clean_cpv(_clean_list(row.get("cpv_codes")))

        merged_keywords: list[str] = []
        for item in [*keywords, *aliases]:
            if item not in merged_keywords:
                merged_keywords.append(item)

        profile = {
            "name": name,
            "category": category,
            "keywords": merged_keywords,
            "qualifier": qualifiers,
            "negative_keywords": negatives,
            "cpv_eu": cpv_codes,
        }

        by_company[company].append(profile)
        all_cpv_codes.update(cpv_codes)
        all_qualifiers.update(qualifiers)
        cpv_by_company[company].update(cpv_codes)
        qualifiers_by_company[company].update(qualifiers)
        keywords_by_company[company].update(merged_keywords)

    return {
        "by_company": dict(by_company),
        "all_cpv_codes": sorted(all_cpv_codes),
        "all_qualifiers": sorted(all_qualifiers),
        "cpv_by_company": {k: sorted(v) for k, v in cpv_by_company.items()},
        "qualifiers_by_company": {k: sorted(v) for k, v in qualifiers_by_company.items()},
        "keywords_by_company": {k: sorted(v) for k, v in keywords_by_company.items()},
    }