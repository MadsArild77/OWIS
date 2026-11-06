from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


UK_ENDPOINTS = {
    "UK_FTS": "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages",
    "UK_CF": "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search",
}
CANADA_URL = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"
SOURCE_NAMES = {
    "TED": "TED (EU/EEA)",
    "DOFFIN": "Doffin (Norway)",
    "WORLDBANK": "World Bank",
    "UK_FTS": "Find a Tender (UK)",
    "UK_CF": "Contracts Finder (UK)",
    "CANADABUYS": "CanadaBuys (Canada)",
}


def date_only(value: Any) -> str | None:
    text = str(value or "").strip()
    for fmt, candidate in [("%Y-%m-%d", text[:10]), ("%d-%b-%Y", text[:11])]:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if 0 <= result < float("inf") else None
    except (ValueError, TypeError):
        return None


def fetch_error(exc: Exception) -> str:
    # Do not persist request headers, URLs with credentials, or response bodies.
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, ValueError):
        return str(exc)[:120]
    return exc.__class__.__name__


def report(source: str, fetched: int, filtered: int, error: str | None) -> dict[str, Any]:
    return {"source": source, "items": fetched, "filtered": filtered,
            "status": "ok" if error is None else "error", "error": error}


def window_start(days_back: int, since: str | None) -> str:
    return since or (datetime.now(timezone.utc) - timedelta(days=max(1, days_back))).isoformat()


def normalize_ocds(raw: dict[str, Any], source: str) -> dict[str, Any] | None:
    tender = raw.get("tender") or {}
    status = tender.get("status")
    tags = set(raw.get("tag") or [])
    if status not in {"active", "planned"} and not (
        not status and tags.intersection({"planning", "planningUpdate"})
    ):
        return None
    if not raw.get("ocid") or not tender.get("title"):
        return None
    buyer = (raw.get("buyer") or {}).get("name") or next(
        (p.get("name", "") for p in raw.get("parties", []) if "buyer" in p.get("roles", [])), ""
    )
    classifications = []
    for part in [tender, *(tender.get("items") or [])]:
        classifications.extend([part.get("classification") or {}, *(part.get("additionalClassifications") or [])])
    cpvs = sorted({str(c["id"]) for c in classifications if c.get("scheme") == "CPV" and c.get("id")})
    documents = tender.get("documents") or []
    url = next((d["url"] for d in documents if d.get("documentType") == "tenderNotice" and d.get("url")), "")
    if not url:
        notice_id = str(raw.get("id") or "")
        if source == "UK_FTS":
            url = f"https://www.find-tender.service.gov.uk/Notice/{notice_id}"
        else:
            url = f"https://www.contractsfinder.service.gov.uk/Notice/{notice_id.rsplit('-', 1)[0]}"
    value = tender.get("value") or {}
    return {
        "id": str(raw["ocid"]), "source": source,
        "title": tender["title"], "description": tender.get("description") or "",
        "buyer": buyer, "country": "GBR", "cpv_codes": cpvs,
        "publication_date": date_only(raw.get("date")), "url": url,
        "deadline_raw": (tender.get("tenderPeriod") or {}).get("endDate"),
        "estimated_value": number(value.get("amount")), "currency": value.get("currency"),
    }


def _release_time(raw: dict[str, Any]) -> datetime:
    try:
        value = datetime.fromisoformat(str(raw.get("date") or "").replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError
        return value
    except ValueError:
        raise ValueError("Invalid OCDS release date") from None


def _get_with_retry(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    # Contracts Finder answers 429 during long reads; wait as told, at most a minute per try.
    for attempt in range(4):
        response = client.get(url, **kwargs)
        if response.status_code != 429 or attempt == 3:
            return response
        wait = response.headers.get("Retry-After", "")
        time.sleep(min(int(wait), 60) if wait.isdigit() else 15)
    return response


def fetch_uk_notices(source: str, days_back: int, since: str | None = None,
                     until: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoint = UK_ENDPOINTS[source]
    start = window_start(days_back, since)
    end = until or datetime.now(timezone.utc).isoformat()
    prefix = "updated" if source == "UK_FTS" else "published"
    params = {f"{prefix}From": start[:19], f"{prefix}To": end[:19], "limit": 100}
    latest: dict[str, dict[str, Any]] = {}
    fetched = 0
    error = None
    try:
        with httpx.Client(timeout=60) as client:
            url = endpoint
            visited = set()
            while url:
                if url in visited:
                    raise ValueError("Repeated pagination link")
                visited.add(url)
                response = _get_with_retry(client, url, params=params, headers={"Accept": "application/json"})
                response.raise_for_status()
                data = response.json()
                if not isinstance(data.get("releases"), list):
                    raise ValueError("Missing OCDS releases")
                for raw in data["releases"]:
                    fetched += 1
                    ocid = raw.get("ocid")
                    if ocid and (ocid not in latest or _release_time(raw) > _release_time(latest[ocid])):
                        latest[ocid] = raw
                next_link = (data.get("links") or {}).get("next")
                url = urljoin(endpoint, next_link) if next_link else ""
                if url and (urlparse(url).netloc != urlparse(endpoint).netloc or urlparse(url).scheme != "https"):
                    raise ValueError("Invalid pagination origin")
                params = None
    except Exception as exc:
        error = fetch_error(exc)
    items = [item for raw in latest.values() if (item := normalize_ocds(raw, source)) is not None]
    return items, report(source, fetched, fetched - len(items), error)


def fetch_canadabuys_notices(days_back: int, since: str | None = None,
                            until: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = window_start(days_back, since)[:10]
    end = (until or datetime.now(timezone.utc).isoformat())[:10]
    items = []
    fetched = 0
    error = None
    try:
        with httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "OWIS/1.0"}) as client:
            response = client.get(CANADA_URL)
            response.raise_for_status()
            reader = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))
            required = {"referenceNumber-numeroReference", "publicationDate-datePublication", "title-titre-eng"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Missing CanadaBuys CSV columns")
            for raw in reader:
                fetched += 1
                published = date_only(raw.get("publicationDate-datePublication"))
                if not published or not start <= published <= end:
                    continue
                if raw.get("tenderStatus-appelOffresStatut-eng", "").lower() != "open":
                    continue
                notice_id = raw.get("referenceNumber-numeroReference")
                if not notice_id:
                    continue
                items.append({
                    "id": f"CANADABUYS-{notice_id}", "source": "CANADABUYS",
                    "title": raw.get("title-titre-eng", ""),
                    "description": raw.get("tenderDescription-descriptionAppelOffres-eng", ""),
                    "buyer": raw.get("contractingEntityName-nomEntitContractante-eng", ""),
                    "country": "CAN", "cpv_codes": [], "publication_date": published,
                    "url": raw.get("noticeURL-URLavis-eng", ""),
                    "deadline_raw": raw.get("tenderClosingDate-appelOffresDateCloture") or None,
                    "estimated_value": None, "currency": None,
                })
    except Exception as exc:
        error = fetch_error(exc)
    return items, report("CANADABUYS", fetched, fetched - len(items), error)
