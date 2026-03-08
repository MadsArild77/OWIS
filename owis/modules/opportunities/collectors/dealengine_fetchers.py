from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


TED_API_ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"
DOFFIN_SEARCH_URL = "https://betaapi.doffin.no/public/v2/search"
WORLDBANK_API_ENDPOINT = "https://search.worldbank.org/api/v2/procurementnotices"

TED_FIELDS = [
    "publication-number",
    "publication-date",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "classification-cpv",
    "notice-type",
    "links",
]

EXCLUDED_TED_PREFIXES = ("CAN", "CORR", "VEAT", "BUS", "UNN")
RELEVANT_DOFFIN_TYPES = ["COMPETITION", "ANNOUNCEMENT_OF_COMPETITION", "PRE_ANNOUNCEMENT"]


def _extract_first_value(value: Any) -> str:
    if isinstance(value, dict):
        for lang in ["eng", "en", "ENG", "EN"]:
            if lang in value:
                found = value[lang]
                if isinstance(found, list):
                    return str(found[0]) if found else ""
                return str(found)
        first = next(iter(value.values()), None)
        if isinstance(first, list):
            return str(first[0]) if first else ""
        return str(first) if first is not None else ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value is not None else ""


def _map_worldbank_country(raw_code: str) -> str:
    mapping = {
        "NO": "NOR",
        "DK": "DNK",
        "GB": "GBR",
        "UK": "GBR",
        "DE": "DEU",
        "NL": "NLD",
        "SE": "SWE",
        "BE": "BEL",
        "IE": "IRL",
        "US": "USA",
        "AU": "AUS",
        "MX": "MEX",
        "CL": "CHL",
        "CO": "COL",
        "IN": "IND",
        "SG": "SGP",
        "AE": "ARE",
        "SA": "SAU",
        "ZA": "ZAF",
        "GH": "GHA",
    }
    code = (raw_code or "").strip().upper()
    if not code:
        return ""
    if len(code) == 3:
        return code
    return mapping.get(code, code)


def _normalize_ted(raw: dict[str, Any]) -> dict[str, Any]:
    pub_number = str(raw.get("publication-number") or "").strip()
    title = _extract_first_value(raw.get("notice-title") or "")
    buyer = _extract_first_value(raw.get("buyer-name") or "")

    country_raw = raw.get("buyer-country") or []
    country = country_raw[0] if isinstance(country_raw, list) and country_raw else str(country_raw or "")

    pub_date = str(raw.get("publication-date") or "")
    clean_date = pub_date.split("+")[0].split("T")[0] if pub_date else ""

    cpv_codes = raw.get("classification-cpv") or []
    if isinstance(cpv_codes, str):
        cpv_codes = [cpv_codes]

    links = raw.get("links") or {}
    source_url = ""
    if isinstance(links, dict):
        html_links = links.get("html") or {}
        if isinstance(html_links, dict):
            source_url = str(html_links.get("ENG") or html_links.get("eng") or "")
            if not source_url and html_links:
                source_url = str(next(iter(html_links.values())))
        elif isinstance(html_links, str):
            source_url = html_links
    if not source_url and pub_number:
        source_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_number}"

    description = f"{title} {buyer}".strip().lower()
    return {
        "id": f"TED-{pub_number}",
        "source": "TED",
        "title": title,
        "buyer": buyer,
        "country": country,
        "publication_date": clean_date,
        "url": source_url or "https://ted.europa.eu",
        "cpv_codes": [str(x) for x in cpv_codes if str(x).strip()],
        "description": description,
    }


def _normalize_doffin(raw: dict[str, Any]) -> dict[str, Any]:
    notice_id = str(raw.get("id") or "").strip()
    title = str(raw.get("heading") or "").strip()

    buyers = raw.get("buyer") or []
    buyer = ""
    if isinstance(buyers, list) and buyers:
        first = buyers[0]
        if isinstance(first, dict):
            buyer = str(first.get("name") or "").strip()
        else:
            buyer = str(first).strip()

    pub_date = str(raw.get("publicationDate") or raw.get("issueDate") or "")
    clean_date = pub_date[:10] if len(pub_date) >= 10 else ""
    source_url = str(raw.get("doffinClassicUrl") or "").strip()
    if not source_url and notice_id:
        source_url = f"https://doffin.no/notices/{notice_id}"

    cpv_raw = raw.get("cpvCodes") or []
    cpv_codes = [str(x) for x in cpv_raw] if isinstance(cpv_raw, list) else []

    description = f"{title} {buyer} {raw.get('description') or ''}".strip().lower()
    return {
        "id": f"DOFFIN-{notice_id}",
        "source": "DOFFIN",
        "title": title,
        "buyer": buyer,
        "country": "NOR",
        "publication_date": clean_date,
        "url": source_url,
        "cpv_codes": cpv_codes,
        "description": description,
    }


def _normalize_worldbank(raw: dict[str, Any]) -> dict[str, Any]:
    notice_id = str(raw.get("id") or raw.get("procno") or raw.get("noticeId") or "").strip()
    title = str(
        raw.get("project_name")
        or raw.get("notice_title")
        or raw.get("title")
        or raw.get("projectname")
        or ""
    ).strip()
    buyer = str(
        raw.get("borrower")
        or raw.get("contact_agency")
        or raw.get("contact_agency_name")
        or raw.get("agencyname")
        or ""
    ).strip()

    country_raw = str(
        raw.get("contact_country_code")
        or raw.get("countrycode")
        or raw.get("country_code")
        or raw.get("country")
        or ""
    ).strip()
    country = _map_worldbank_country(country_raw)

    pub_date = str(
        raw.get("submission_date")
        or raw.get("notice_date")
        or raw.get("ddate")
        or raw.get("publisheddate")
        or ""
    ).strip()
    clean_date = pub_date[:10] if len(pub_date) >= 10 else ""

    source_url = str(raw.get("url") or raw.get("link") or raw.get("href") or "").strip()
    if not source_url and notice_id:
        source_url = "https://projects.worldbank.org/en/projects-operations/procurement"

    description = (
        f"{title} {buyer} "
        f"{raw.get('procurement_description') or raw.get('description') or raw.get('project_desc') or ''}"
    ).strip().lower()

    return {
        "id": f"WB-{notice_id}",
        "source": "WORLDBANK",
        "title": title,
        "buyer": buyer,
        "country": country,
        "publication_date": clean_date,
        "url": source_url,
        "cpv_codes": [],
        "description": description,
    }


def fetch_ted_notices(
    profile_bundle: dict[str, Any],
    days_back: int,
    countries: list[str],
    ted_api_key: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cpv_codes = profile_bundle.get("all_cpv_codes") or []
    if not cpv_codes:
        return [], {"source": "TED", "items": 0, "status": "skipped", "error": "no_cpv_codes"}

    valid_cpv = [code for code in cpv_codes if len(str(code)) == 8]
    if not valid_cpv:
        return [], {"source": "TED", "items": 0, "status": "skipped", "error": "no_valid_cpv_codes"}

    date_from = (datetime.now(timezone.utc) - timedelta(days=max(days_back, 1))).strftime("%Y%m%d")
    country_query = " ".join(countries)
    cpv_query = " ".join(valid_cpv)
    query = (
        f"classification-cpv IN ({cpv_query}) "
        f"AND buyer-country IN ({country_query}) "
        f"AND PD >= {date_from}"
    )

    headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if ted_api_key:
        headers["X-API-Key"] = ted_api_key

    items: list[dict[str, Any]] = []
    error: str | None = None

    try:
        with httpx.Client(timeout=30) as client:
            for page in range(1, 6):
                payload = {"query": query, "fields": TED_FIELDS, "page": page, "limit": 100}
                resp = client.post(TED_API_ENDPOINT, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("notices") or []
                if not batch:
                    break
                for raw in batch:
                    notice_type = str(raw.get("notice-type") or "").upper()
                    if notice_type.startswith(EXCLUDED_TED_PREFIXES):
                        continue
                    normalized = _normalize_ted(raw)
                    if normalized["id"] != "TED-":
                        items.append(normalized)
    except Exception as exc:
        error = f"{exc.__class__.__name__}: {exc}"

    report = {
        "source": "TED",
        "items": len(items),
        "status": "ok" if error is None else "error",
        "error": error,
    }
    return items, report


def _doffin_search_paginated(client: httpx.Client, base_params: list[tuple[str, str]]) -> list[dict[str, Any]]:
    all_hits: list[dict[str, Any]] = []
    for page in range(1, 8):
        params = [*base_params, ("page", str(page)), ("numHitsPerPage", "100")]
        resp = client.get(DOFFIN_SEARCH_URL, params=params, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("hits") or []
        if isinstance(hits, dict):
            hits = [hits] if hits.get("id") else []
        if not isinstance(hits, list) or not hits:
            break

        all_hits.extend(hits)

        total = int(data.get("numHitsAccessible") or data.get("numHitsTotal") or 0)
        if total and len(all_hits) >= total:
            break
    return all_hits


def fetch_doffin_notices(
    profile_bundle: dict[str, Any],
    days_back: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    date_from = (datetime.now(timezone.utc) - timedelta(days=max(days_back, 1))).strftime("%Y-%m-%d")

    cpv_codes = profile_bundle.get("all_cpv_codes") or []
    qualifiers = profile_bundle.get("all_qualifiers") or []

    base = [("issueDateFrom", date_from), ("status", "ACTIVE")]
    for notice_type in RELEVANT_DOFFIN_TYPES:
        base.append(("type", notice_type))

    raw_rows: list[dict[str, Any]] = []
    error: str | None = None

    try:
        with httpx.Client(timeout=30) as client:
            if cpv_codes:
                cpv_params = [*base, *[("cpvCode", str(code)) for code in cpv_codes]]
                raw_rows.extend(_doffin_search_paginated(client, cpv_params))

            for kw in qualifiers[:12]:
                kw_params = [*base, ("searchString", str(kw))]
                raw_rows.extend(_doffin_search_paginated(client, kw_params))
    except Exception as exc:
        error = f"{exc.__class__.__name__}: {exc}"

    dedup: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        rid = str(row.get("id") or "").strip()
        if rid and rid not in dedup:
            dedup[rid] = row

    items = [_normalize_doffin(row) for row in dedup.values()]
    report = {
        "source": "DOFFIN",
        "items": len(items),
        "status": "ok" if error is None else "error",
        "error": error,
    }
    return items, report


def _extract_worldbank_notices(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ["procurementnotices", "notices", "results", "items", "data"]:
            if key not in data:
                continue
            value = data[key]
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                return [x for x in value.values() if isinstance(x, dict)]
    return []


def _worldbank_keyword_search(client: httpx.Client, keyword: str, date_from: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, 600, 100):
        params = {
            "format": "json",
            "rows": 100,
            "os": offset,
            "q": keyword,
            "strdate": date_from,
        }
        resp = client.get(WORLDBANK_API_ENDPOINT, params=params)
        resp.raise_for_status()
        data = resp.json()
        batch = _extract_worldbank_notices(data)
        if not batch:
            break
        rows.extend(batch)
        total = int(data.get("total") or data.get("totalrows") or 0)
        if total and offset + 100 >= total:
            break
    return rows


def fetch_worldbank_notices(
    profile_bundle: dict[str, Any],
    days_back: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    keywords_by_company = profile_bundle.get("keywords_by_company") or {}
    qualifiers = profile_bundle.get("all_qualifiers") or []

    search_terms: list[str] = []
    if keywords_by_company:
        merged: set[str] = set()
        for terms in keywords_by_company.values():
            for term in list(terms)[:5]:
                merged.add(str(term))
        search_terms = sorted(merged)
    else:
        search_terms = [str(x) for x in qualifiers[:8]]

    if not search_terms:
        return [], {"source": "WORLDBANK", "items": 0, "status": "skipped", "error": "no_search_terms"}

    date_from = (datetime.now(timezone.utc) - timedelta(days=max(days_back, 1))).strftime("%Y-%m-%d")

    raw_rows: list[dict[str, Any]] = []
    error: str | None = None
    try:
        with httpx.Client(timeout=30) as client:
            for term in search_terms:
                raw_rows.extend(_worldbank_keyword_search(client, term, date_from))
    except Exception as exc:
        error = f"{exc.__class__.__name__}: {exc}"

    dedup: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        rid = str(row.get("id") or row.get("procno") or row.get("noticeId") or "").strip()
        if rid and rid not in dedup:
            dedup[rid] = row

    items = [_normalize_worldbank(row) for row in dedup.values()]
    report = {
        "source": "WORLDBANK",
        "items": len(items),
        "status": "ok" if error is None else "error",
        "error": error,
    }
    return items, report


def fetch_dealengine_style_notices_with_report(
    profile_bundle: dict[str, Any],
    enabled_sources: list[str],
    days_back: int,
    ted_api_key: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    countries = [
        "NOR",
        "DNK",
        "GBR",
        "DEU",
        "NLD",
        "SWE",
        "BEL",
        "IRL",
        "MEX",
        "CHL",
        "COL",
        "IND",
        "AUS",
        "SGP",
        "ARE",
        "SAU",
        "ZAF",
        "GHA",
    ]

    items: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    source_set = {s.strip().upper() for s in enabled_sources if s.strip()}

    if "TED" in source_set:
        ted_items, ted_report = fetch_ted_notices(profile_bundle, days_back=days_back, countries=countries, ted_api_key=ted_api_key)
        items.extend(ted_items)
        reports.append(ted_report)

    if "DOFFIN" in source_set:
        doffin_items, doffin_report = fetch_doffin_notices(profile_bundle, days_back=days_back)
        items.extend(doffin_items)
        reports.append(doffin_report)

    if "WORLDBANK" in source_set:
        wb_items, wb_report = fetch_worldbank_notices(profile_bundle, days_back=days_back)
        items.extend(wb_items)
        reports.append(wb_report)

    dedup: dict[str, dict[str, Any]] = {}
    for item in items:
        notice_id = str(item.get("id") or "").strip()
        if notice_id and notice_id not in dedup:
            dedup[notice_id] = item

    return list(dedup.values()), reports