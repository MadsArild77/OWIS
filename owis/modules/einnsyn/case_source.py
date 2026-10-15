"""One eInnsyn case, read from eInnsyn's open API: its journal posts and open documents.

The monitor's Notion data only lists cases and journal post titles. Opening a case
reads the public API directly (no key needed) for the full record, including which
journal posts have a public file and its download link.
"""
from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

API = "https://api.einnsyn.no"
CACHE_SECONDS = 1800
DIRECTION = {
    "inngaaende_dokument": "incoming",
    "utgaaende_dokument": "outgoing",
    "organinternt_dokument_for_oppfoelging": "internal",
    "organinternt_dokument_uten_oppfoelging": "internal",
}


def case_ref(url_or_id: str) -> str:
    """The case id in an eInnsyn link (old IRI or new sm_ id), or the value itself."""
    value = str(url_or_id or "").strip()
    if value.startswith("http") and "saksmappe" in value:
        return (parse_qs(urlparse(value).query).get("id") or [value])[0]
    return value


class CaseSource:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30)
        self._cache: dict[str, tuple[float, dict]] = {}
        self._units: dict[str, str] = {}
        self._lock = threading.Lock()

    def _get(self, path: str, params: Any = None) -> dict:
        url = path if path.startswith("http") else f"{API}{path}"
        for attempt in range(1, 4):
            try:
                resp = self.client.get(url, params=params)
                if resp.status_code not in (429, 500, 502, 503, 504) or attempt == 3:
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 3:
                    raise
            time.sleep(2 * attempt)
        raise RuntimeError("unreachable")

    def _unit(self, unit_id: str) -> str:
        if unit_id and unit_id not in self._units:
            try:
                self._units[unit_id] = str(self._get(f"/enhet/{unit_id}").get("navn") or "")
            except Exception:
                self._units[unit_id] = ""
        return self._units.get(unit_id, "")

    def case(self, url_or_id: str) -> dict | None:
        ref = case_ref(url_or_id)
        if not ref:
            return None
        with self._lock:
            hit = self._cache.get(ref)
            if hit and time.time() - hit[0] < CACHE_SECONDS:
                return hit[1]
        case = self._load(ref)
        if case:
            with self._lock:
                self._cache[ref] = (time.time(), case)
        return case

    def _load(self, ref: str) -> dict | None:
        if ref.startswith("sm_"):
            folder = self._get(f"/saksmappe/{ref}")
        else:
            items = self._get("/saksmappe", [("externalIds", ref)]).get("items") or []
            folder = items[0] if items else None
        if not folder:
            return None
        params = [("limit", 100), ("expand", "dokumentbeskrivelse.dokumentobjekt"),
                  ("expand", "korrespondansepart"), ("expand", "skjerming")]
        data = self._get(f"/saksmappe/{folder['id']}/journalpost", params)
        posts = list(data.get("items") or [])
        for _ in range(9):
            if not data.get("next"):
                break
            data = self._get(data["next"])
            posts.extend(data.get("items") or [])
        journal = sorted((self._post(p) for p in posts), key=lambda p: (p["date"], p["number"]), reverse=True)
        return {
            "ref": ref,
            "id": folder["id"],
            "title": str(folder.get("offentligTittel") or ""),
            "case_number": str(folder.get("saksnummer") or ""),
            "agency": self._unit(str(folder.get("journalenhet") or "")),
            "unit": str(folder.get("administrativEnhet") or ""),
            "url": f"https://einnsyn.no/saksmappe?id={ref}",
            "journal_posts": journal,
            "open_documents": sum(len(p["documents"]) for p in journal),
            "posts_with_documents": sum(1 for p in journal if p["documents"]),
        }

    @staticmethod
    def _post(p: dict) -> dict:
        def party(kind: str) -> str:
            for part in p.get("korrespondansepart") or []:
                if isinstance(part, dict) and part.get("korrespondanseparttype") == kind:
                    name = str(part.get("korrespondansepartNavn") or "").strip()
                    if name and name != "*":
                        return name
            return ""

        documents = []
        for desc in p.get("dokumentbeskrivelse") or []:
            if not isinstance(desc, dict):
                continue
            role = "attachment" if str(desc.get("tilknyttetRegistreringSom") or "").endswith("vedlegg") else "main"
            for obj in desc.get("dokumentobjekt") or []:
                obj_id = obj.get("id") if isinstance(obj, dict) else obj
                if obj_id:
                    documents.append({"title": str(desc.get("tittel") or ""), "role": role,
                                      "url": f"{API}/dokumentobjekt/{obj_id}/download"})
        documents.sort(key=lambda d: d["role"] != "main")
        kind = str(p.get("journalposttype") or "")
        return {
            "id": str(p.get("id") or ""),
            "number": int(p.get("journalpostnummer") or 0),
            "date": str(p.get("journaldato") or p.get("dokumentetsDato") or p.get("publisertDato") or "")[:10],
            "published": str(p.get("publisertDato") or "")[:10],
            "title": str(p.get("offentligTittel") or ""),
            "direction": DIRECTION.get(kind, kind.replace("_", " ")),
            "from": party("avsender"),
            "to": party("mottaker"),
            "restricted": bool(p.get("skjerming")),
            "documents": documents,
        }
