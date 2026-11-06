from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .open_data import date_only, number, fetch_error, report, fetch_uk_notices, fetch_canadabuys_notices


TED_API_ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"
DOFFIN_SEARCH_URL = "https://api.doffin.no/webclient/api/v2/search-api/search"
WORLDBANK_API_ENDPOINT = "https://search.worldbank.org/api/v2/procnotices"

TED_FIELDS = [
    "publication-number",
    "publication-date",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "classification-cpv",
    "notice-type",
    "links",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-request",
    "estimated-value-proc",
    "estimated-value-cur-proc",
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

    deadlines = raw.get("deadline-receipt-tender-date-lot") or raw.get("deadline-receipt-request") or []
    if isinstance(deadlines, str):
        deadlines = [deadlines]
    dates = [date_only(value) for value in deadlines]
    deadline = min((value for value in dates if value), default=None)
    description = f"{title} {buyer}".strip().lower()
    return {
        "id": f"TED-{pub_number}",
        "deadline_raw": deadline,
        "estimated_value": number(_extract_first_value(raw.get("estimated-value-proc"))),
        "currency": _extract_first_value(raw.get("estimated-value-cur-proc")) or None,
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
    clean_date = date_only(pub_date) or ""
    source_url = ""
    if not source_url and notice_id:
        source_url = f"https://doffin.no/notices/{notice_id}"

    cpv_raw = raw.get("cpvCodes") or []
    cpv_codes = [str(x) for x in cpv_raw] if isinstance(cpv_raw, list) else []

    description = f"{title} {buyer} {raw.get('description') or ''}".strip().lower()
    return {
        "id": f"DOFFIN-{notice_id}",
        "deadline_raw": raw.get("deadline"),
        "estimated_value": number((raw.get("estimatedValue") or {}).get("amount")),
        "currency": (raw.get("estimatedValue") or {}).get("currencyCode"),
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
        raw.get("bid_description")
        or raw.get("project_name")
        or raw.get("notice_title")
        or raw.get("title")
        or raw.get("projectname")
        or ""
    ).strip()
    buyer = str(
        raw.get("contact_organization")
        or raw.get("borrower")
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
    country_names = {"Norway": "NOR", "Denmark": "DNK", "United Kingdom": "GBR",
                     "France": "FRA", "Poland": "POL", "Germany": "DEU", "Netherlands": "NLD",
                     "India": "IND", "Turkiye": "TUR", "Vietnam": "VNM", "Brazil": "BRA",
                     "St. Kitts and Nevis": "KNA", "Canada": "CAN", "South Africa": "ZAF"}
    country = _map_worldbank_country(country_raw) if country_raw else country_names.get(raw.get("project_ctry_name"), "")

    pub_date = str(
        raw.get("noticedate")
        or raw.get("submission_date")
        or raw.get("notice_date")
        or raw.get("ddate")
        or raw.get("publisheddate")
        or ""
    ).strip()
    clean_date = date_only(pub_date) or ""

    source_url = str(raw.get("url") or raw.get("link") or raw.get("href") or "").strip()
    if not source_url and notice_id:
        source_url = f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{notice_id}"

    description = (
        f"{title} {buyer} {raw.get('project_name') or ''} "
        f"{raw.get('bid_description') or raw.get('procurement_description') or raw.get('description') or raw.get('project_desc') or ''}"
    ).strip().lower()

    return {
        "id": f"WB-{notice_id}",
        "deadline_raw": raw.get("submission_deadline_date"),
        "estimated_value": None,
        "currency": None,
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
    valid_cpv = [str(code) for code in profile_bundle.get("all_cpv_codes", []) if len(str(code)) == 8]
    clauses = [f"classification-cpv IN ({' '.join(valid_cpv)})"] if valid_cpv else []
    for term in (profile_bundle.get("keywords_by_company") or {}).get("OWIS", []):
        escaped = str(term).replace('"', '')
        clauses.append(f'FT ~ "{escaped}"')
    if not clauses:
        return [], {"source": "TED", "items": 0, "filtered": 0, "status": "error", "error": "No search terms"}
    date_from = (datetime.now(timezone.utc) - timedelta(days=max(days_back, 1))).strftime("%Y%m%d")
    query = f"({' OR '.join(clauses)}) AND buyer-country IN ({' '.join(countries)}) AND PD >= {date_from}"

    headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if ted_api_key:
        headers["X-API-Key"] = ted_api_key

    items: list[dict[str, Any]] = []
    fetched = 0
    error: str | None = None

    try:
        with httpx.Client(timeout=30) as client:
            for page in range(1, 151):
                payload = {"query": query, "fields": TED_FIELDS, "page": page, "limit": 100}
                resp = client.post(TED_API_ENDPOINT, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if data.get("timedOut") or not isinstance(data.get("notices"), list):
                    raise ValueError("Incomplete TED search response")
                batch = data["notices"]
                fetched += len(batch)
                if not batch:
                    if fetched < int(data.get("totalNoticeCount") or 0):
                        raise ValueError("Incomplete TED results")
                    break
                for raw in batch:
                    notice_type = str(raw.get("notice-type") or "").upper()
                    if notice_type.startswith(EXCLUDED_TED_PREFIXES):
                        continue
                    normalized = _normalize_ted(raw)
                    if normalized["id"] != "TED-":
                        items.append(normalized)
                if fetched >= int(data.get("totalNoticeCount") or 0):
                    break
            else:
                raise ValueError("TED result limit reached; narrow date window")
    except Exception as exc:
        error = fetch_error(exc)

    report = {
        "source": "TED",
        "items": fetched,
        "filtered": fetched - len(items),
        "status": "ok" if error is None else "error",
        "error": error,
    }
    return items, report


def _doffin_search_paginated(client: httpx.Client, base_params: dict[str, Any]) -> list[dict[str, Any]]:
    all_hits: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = {**base_params, "page": page, "numHitsPerPage": 100}
        resp = client.post(DOFFIN_SEARCH_URL, json=payload, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data.get("hits"), list) or "numHitsTotal" not in data:
            raise ValueError("Missing Doffin search results")
        hits = data["hits"]
        all_hits.extend(hits)
        total = int(data["numHitsTotal"])
        if len(all_hits) >= total:
            return all_hits
        accessible = int(data.get("numHitsAccessible") or total)
        if not hits or len(all_hits) >= accessible:
            raise ValueError("Doffin result limit reached; narrow date window")
        page += 1


def fetch_doffin_notices(profile_bundle: dict[str, Any], days_back: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    date_from = (datetime.now(timezone.utc) - timedelta(days=max(days_back, 1))).strftime("%Y-%m-%d")
    facets = {"publicationDate": {"from": date_from, "to": None},
              "type": {"checkedItems": RELEVANT_DOFFIN_TYPES}}
    queries = []
    cpv_codes = profile_bundle.get("all_cpv_codes") or []
    if cpv_codes:
        queries.append({"sortBy": "PUBLICATION_DATE_DESC", "facets": {**facets, "cpvCodesId": {"checkedItems": cpv_codes}}})
    terms = set(profile_bundle.get("all_qualifiers") or [])
    for keywords in (profile_bundle.get("keywords_by_company") or {}).values():
        terms.update(keywords)
    for term in sorted(terms):
        queries.append({"sortBy": "PUBLICATION_DATE_DESC", "facets": facets, "searchString": term})
    rows = {}
    error = None
    fetched = 0
    try:
        with httpx.Client(timeout=30) as client:
            for query in queries:
                for raw in _doffin_search_paginated(client, query):
                    fetched += 1
                    if raw.get("id"):
                        rows[raw["id"]] = raw
    except Exception as exc:
        error = fetch_error(exc)
    items = [_normalize_doffin(row) for row in rows.values()
             if (row.get("type") in RELEVANT_DOFFIN_TYPES or set(row.get("allTypes") or []).intersection(RELEVANT_DOFFIN_TYPES))
             and (date_only(row.get("publicationDate") or row.get("issueDate")) or "") >= date_from
             and row.get("status") not in {"AWARDED", "CANCELLED", "EXPIRED"}]
    return items, report("DOFFIN", fetched, fetched - len(items), error)


def _extract_worldbank_notices(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ["procnotices", "procurementnotices", "notices", "results", "items", "data"]:
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
    offset = 0
    while True:
        params = {
            "format": "json",
            "rows": 100,
            "os": offset,
            "qterm": keyword,
            "srt": "noticedate",
            "order": "desc",
        }
        resp = client.get(WORLDBANK_API_ENDPOINT, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data.get("procnotices"), list) or "total" not in data:
            raise ValueError("Missing World Bank search results")
        batch = _extract_worldbank_notices(data)
        if not batch:
            if offset < int(data.get("total") or 0):
                raise ValueError("Incomplete World Bank results")
            break
        rows.extend(batch)
        dates = [date_only(row.get("noticedate") or row.get("submission_date")) for row in batch]
        if all(dates) and min(dates) < date_from:
            break
        total = int(data.get("total") or data.get("totalrows") or 0)
        if offset + len(batch) >= total:
            break
        offset += len(batch)
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
            for term in terms:
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
        error = fetch_error(exc)

    dedup: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        rid = str(row.get("id") or row.get("procno") or row.get("noticeId") or "").strip()
        if rid and rid not in dedup:
            dedup[rid] = row

    items = [item for row in dedup.values() if (item := _normalize_worldbank(row))["publication_date"] >= date_from]
    report = {
        "source": "WORLDBANK",
        "items": len(raw_rows),
        "filtered": len(raw_rows) - len(items),
        "status": "ok" if error is None else "error",
        "error": error,
    }
    return items, report


def fetch_dealengine_style_notices_with_report(
    profile_bundle: dict[str, Any],
    enabled_sources: list[str],
    days_back: int,
    ted_api_key: str = "",
    since_by_source: dict[str, str] | None = None,
    until: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    countries = [
        "FRA",
        "POL",
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

    for source in ["UK_FTS", "UK_CF", "CANADABUYS"]:
        if source not in source_set:
            continue
        since = (since_by_source or {}).get(source)
        if source == "CANADABUYS":
            batch, source_report = fetch_canadabuys_notices(days_back, since, until)
        else:
            batch, source_report = fetch_uk_notices(source, days_back, since, until)
        items.extend(batch)
        reports.append(source_report)

    dedup: dict[str, dict[str, Any]] = {}
    for item in items:
        notice_id = str(item.get("id") or "").strip()
        if notice_id and notice_id not in dedup:
            dedup[notice_id] = item
        elif notice_id:
            for source_report in reports:
                if source_report["source"] == item["source"]:
                    source_report["filtered"] = source_report.get("filtered", 0) + 1
                    break

    return list(dedup.values()), reports