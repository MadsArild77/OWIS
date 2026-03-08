from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


_DEDUP_FIELD_CANDIDATES = [
    "TED Publication Number",
    "Notice ID",
    "Dedup Key",
    "External ID",
    "Source ID",
]


class OpportunitiesNotionExporter:
    def __init__(self, api_key: str, database_id: str, notion_version: str = "2022-06-28") -> None:
        self.api_key = api_key.strip()
        self.database_id = database_id.strip()
        self.notion_version = notion_version.strip() or "2022-06-28"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }

    def _pick_field(
        self,
        db_props: dict[str, dict[str, Any]],
        candidates: list[str],
        allowed_types: list[str] | None = None,
    ) -> str | None:
        for name in candidates:
            prop = db_props.get(name)
            if not isinstance(prop, dict):
                continue
            prop_type = str(prop.get("type") or "")
            if allowed_types and prop_type not in allowed_types:
                continue
            return name
        return None

    def _title_field(self, db_props: dict[str, dict[str, Any]]) -> str | None:
        for name, prop in db_props.items():
            if isinstance(prop, dict) and prop.get("type") == "title":
                return name
        return self._pick_field(db_props, ["Name", "Title"], ["title"])

    def _extract_property_text(self, prop: dict[str, Any]) -> str:
        prop_type = str(prop.get("type") or "")
        if prop_type == "title":
            parts = prop.get("title") or []
            return "".join(str(x.get("plain_text") or "") for x in parts if isinstance(x, dict)).strip()
        if prop_type == "rich_text":
            parts = prop.get("rich_text") or []
            return "".join(str(x.get("plain_text") or "") for x in parts if isinstance(x, dict)).strip()
        if prop_type == "select":
            selected = prop.get("select") or {}
            return str(selected.get("name") or "").strip()
        if prop_type == "multi_select":
            values = prop.get("multi_select") or []
            return ",".join(
                str(x.get("name") or "").strip() for x in values if isinstance(x, dict) and str(x.get("name") or "").strip()
            )
        if prop_type == "url":
            return str(prop.get("url") or "").strip()
        if prop_type == "number":
            value = prop.get("number")
            return "" if value is None else str(value)
        return ""

    def _normalize_date(self, value: str) -> str | None:
        raw = (value or "").strip()
        if not raw:
            return None
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    def _set_property(
        self,
        out_props: dict[str, Any],
        db_props: dict[str, dict[str, Any]],
        field_name: str | None,
        value: Any,
    ) -> None:
        if not field_name or value is None:
            return

        prop = db_props.get(field_name)
        if not isinstance(prop, dict):
            return

        prop_type = str(prop.get("type") or "")
        if prop_type == "title":
            text = str(value).strip()
            if text:
                out_props[field_name] = {"title": [{"text": {"content": text[:2000]}}]}
            return

        if prop_type == "rich_text":
            text = str(value).strip()
            if text:
                out_props[field_name] = {"rich_text": [{"text": {"content": text[:2000]}}]}
            return

        if prop_type == "select":
            text = str(value).strip()
            if text:
                out_props[field_name] = {"select": {"name": text[:100]}}
            return

        if prop_type == "multi_select":
            values = value if isinstance(value, list) else [value]
            cleaned = [{"name": str(v).strip()[:100]} for v in values if str(v).strip()]
            if cleaned:
                out_props[field_name] = {"multi_select": cleaned}
            return

        if prop_type == "url":
            text = str(value).strip()
            if text:
                out_props[field_name] = {"url": text[:2000]}
            return

        if prop_type == "date":
            date_str = self._normalize_date(str(value))
            if date_str:
                out_props[field_name] = {"date": {"start": date_str}}
            return

        if prop_type == "number":
            try:
                out_props[field_name] = {"number": float(value)}
            except (TypeError, ValueError):
                pass
            return

        if prop_type == "checkbox":
            out_props[field_name] = {"checkbox": bool(value)}

    def _lead_path(self, source_name: str, profile_name: str) -> str:
        source = (source_name or "").strip().upper()
        suffix_map = {
            "TED": "TED radar",
            "DOFFIN": "Doffin",
            "WORLDBANK": "World Bank",
        }
        suffix = suffix_map.get(source, source or "Source")
        profile = (profile_name or "").strip().upper() or "PROFILE"
        return f"{profile} - {suffix}"

    def _build_properties(
        self,
        item: dict[str, Any],
        db_props: dict[str, dict[str, Any]],
        dedup_field: str | None,
        dedup_key: str,
    ) -> dict[str, Any]:
        props: dict[str, Any] = {}

        title_field = self._title_field(db_props)
        self._set_property(props, db_props, title_field, item.get("title") or "Untitled opportunity")

        source_name = str(item.get("source_name") or "")
        profile_name = str(item.get("profile_name") or "")

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Source"], ["select", "rich_text"]),
            source_name,
        )

        if dedup_field:
            self._set_property(props, db_props, dedup_field, dedup_key)

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Discovered Date", "Created"], ["date"]),
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Discovered By"], ["select", "rich_text"]),
            "Automation",
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Lead Path"], ["select", "rich_text"]),
            self._lead_path(source_name, profile_name),
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Status"], ["select", "rich_text"]),
            "New",
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Country"], ["select", "rich_text"]),
            item.get("country") or "",
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Publication Date", "Notice Date"], ["date"]),
            item.get("publication_date") or "",
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Source Link", "Source URL", "URL"], ["url", "rich_text"]),
            item.get("source_url") or "",
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Strategic Fit"], ["select", "rich_text"]),
            item.get("strategic_fit") or "",
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Competition Level"], ["select", "rich_text"]),
            item.get("competition_level") or "",
        )

        family = item.get("opportunity_family") or ""
        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Project Type", "Opportunity Family"], ["multi_select", "rich_text", "select"]),
            [family] if family else [],
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Mechanism Type", "Mechanism"], ["select", "rich_text"]),
            item.get("mechanism_type") or "",
        )

        services = [s.strip() for s in str(item.get("matched_services") or "").split(",") if s.strip()]
        qualifiers = [s.strip() for s in str(item.get("matched_qualifiers") or "").split(",") if s.strip()]

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Matched Services"], ["multi_select", "rich_text"]),
            services,
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Matched Qualifiers", "Qualifier Match"], ["multi_select", "rich_text"]),
            qualifiers,
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Deadline", "Due Date"], ["date"]),
            item.get("deadline") or "",
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Signal Score", "Score"], ["number", "rich_text"]),
            item.get("signal_score"),
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Confidence"], ["number", "rich_text"]),
            item.get("confidence"),
        )

        notes = item.get("recommended_action") or ""
        why = item.get("why_it_matters") or ""
        combined = f"{notes} {why}".strip()

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["Your Qualification Notes", "Qualification Notes", "Notes"], ["rich_text"]),
            notes,
        )

        self._set_property(
            props,
            db_props,
            self._pick_field(db_props, ["AI Reason", "Why It Matters"], ["rich_text"]),
            combined,
        )

        return props

    def _fetch_db_properties(self, client: httpx.Client) -> dict[str, dict[str, Any]]:
        resp = client.get(
            f"https://api.notion.com/v1/databases/{self.database_id}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        props = data.get("properties") or {}
        if not isinstance(props, dict):
            return {}
        return {str(k): v for k, v in props.items() if isinstance(v, dict)}

    def _dedup_field(self, db_props: dict[str, dict[str, Any]]) -> str | None:
        return self._pick_field(
            db_props,
            _DEDUP_FIELD_CANDIDATES,
            ["rich_text", "title", "select"],
        )

    def _fetch_existing_dedup_values(
        self,
        client: httpx.Client,
        db_props: dict[str, dict[str, Any]],
        dedup_field: str | None,
    ) -> set[str]:
        if not dedup_field:
            return set()

        keys: set[str] = set()
        has_more = True
        cursor: str | None = None

        while has_more:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor

            resp = client.post(
                f"https://api.notion.com/v1/databases/{self.database_id}/query",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results") or []:
                if not isinstance(page, dict):
                    continue
                props = page.get("properties") or {}
                if not isinstance(props, dict):
                    continue
                raw_prop = props.get(dedup_field)
                if not isinstance(raw_prop, dict):
                    continue
                value = self._extract_property_text(raw_prop)
                if value:
                    keys.add(value)

            has_more = bool(data.get("has_more"))
            cursor = data.get("next_cursor")

        return keys

    def export_items(
        self,
        items: list[dict[str, Any]],
        max_items: int = 100,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("NOTION_API_KEY is empty")
        if not self.database_id:
            raise ValueError("NOTION_OPPORTUNITIES_DB_ID is empty")

        queue = items[: max(0, max_items)]

        with httpx.Client(timeout=30) as client:
            db_props = self._fetch_db_properties(client)
            dedup_field = self._dedup_field(db_props)
            existing = self._fetch_existing_dedup_values(client, db_props, dedup_field)

            imported = 0
            skipped_duplicates = 0
            failed = 0
            failures: list[dict[str, str]] = []

            seen_in_run: set[str] = set()

            for item in queue:
                notice_id = str(item.get("notice_id") or "").strip()
                profile = str(item.get("profile_name") or "").strip().upper()
                dedup_key = f"{notice_id}:{profile}" if notice_id and profile else notice_id or ""

                if dedup_key and dedup_key in seen_in_run:
                    skipped_duplicates += 1
                    continue

                if dedup_field and dedup_key and dedup_key in existing:
                    skipped_duplicates += 1
                    continue

                props = self._build_properties(item, db_props, dedup_field, dedup_key)
                if not props:
                    failed += 1
                    failures.append(
                        {
                            "title": str(item.get("title") or "Untitled"),
                            "error": "no_mapped_properties",
                        }
                    )
                    continue

                if dry_run:
                    imported += 1
                    seen_in_run.add(dedup_key)
                    continue

                try:
                    resp = client.post(
                        "https://api.notion.com/v1/pages",
                        headers=self._headers(),
                        json={"parent": {"database_id": self.database_id}, "properties": props},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    imported += 1
                    seen_in_run.add(dedup_key)
                    if dedup_key:
                        existing.add(dedup_key)
                except Exception as exc:
                    failed += 1
                    failures.append(
                        {
                            "title": str(item.get("title") or "Untitled"),
                            "error": f"{exc.__class__.__name__}: {exc}",
                        }
                    )

        return {
            "attempted": len(queue),
            "imported": imported,
            "skipped_duplicates": skipped_duplicates,
            "failed": failed,
            "dry_run": dry_run,
            "dedup_field": dedup_field,
            "failures": failures[:10],
        }