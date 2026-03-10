import json
import re
from typing import Any

import httpx

from owis.core.config.settings import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_ENABLED,
    AI_ENDPOINT,
    AI_INPUT_MAX_CHARS,
    AI_MAX_TOKENS,
    AI_MODEL,
    AI_PROVIDER,
)


class AIClient:
    def __init__(self) -> None:
        self.enabled = AI_ENABLED and bool(AI_API_KEY)
        self.last_error: str | None = None

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

    def _parse_json_content(self, content: Any) -> dict[str, Any] | None:
        if isinstance(content, dict):
            return content
        text = str(content or "").strip()
        if not text:
            return None

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # Some providers prepend text before JSON despite prompt instructions.
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None

    def _coerce_confidence(self, value: Any, fallback: float = 0.5) -> float:
        if value is None:
            return max(0.0, min(float(fallback), 1.0))

        if isinstance(value, (int, float)):
            n = float(value)
            if n > 1.0:
                n = n / 100.0 if n <= 100.0 else 1.0
            return max(0.0, min(n, 1.0))

        raw = str(value).strip().lower()
        if not raw:
            return max(0.0, min(float(fallback), 1.0))

        labels = {
            "high": 0.85,
            "medium": 0.60,
            "med": 0.60,
            "low": 0.35,
            "hoy": 0.85,
            
            "middels": 0.60,
            "lav": 0.35,
        }
        if raw in labels:
            return labels[raw]

        if raw.endswith("%"):
            raw = raw[:-1].strip()

        try:
            n = float(raw)
            if n > 1.0:
                n = n / 100.0 if n <= 100.0 else 1.0
            return max(0.0, min(n, 1.0))
        except Exception:
            return max(0.0, min(float(fallback), 1.0))

    def _post_json_prompt(self, system_prompt: str, user_text: str, max_tokens: int | None = None) -> dict[str, Any] | None:
        if not self.enabled:
            self.last_error = "ai_disabled_or_missing_api_key"
            return None
        if AI_PROVIDER not in {"openai_compatible", "openai", "mistral", "deepseek"}:
            self.last_error = f"unsupported_ai_provider:{AI_PROVIDER}"
            return None

        payload = {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text[:AI_INPUT_MAX_CHARS]},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens or AI_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=25) as client:
                try:
                    response = client.post(
                        f"{AI_BASE_URL.rstrip('/')}{AI_ENDPOINT}",
                        headers=self._build_headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    # Some OpenAI-compatible providers reject response_format.
                    error_text = (exc.response.text or "") if exc.response is not None else ""
                    status = exc.response.status_code if exc.response is not None else None
                    if status in {400, 404, 415, 422} and "response_format" in error_text.lower():
                        fallback_payload = dict(payload)
                        fallback_payload.pop("response_format", None)
                        response = client.post(
                            f"{AI_BASE_URL.rstrip('/')}{AI_ENDPOINT}",
                            headers=self._build_headers(),
                            json=fallback_payload,
                        )
                        response.raise_for_status()
                    else:
                        raise

                api_payload = response.json()

            content = api_payload["choices"][0]["message"]["content"]
            parsed = self._parse_json_content(content)
            if parsed is None:
                self.last_error = "invalid_json_response"
                return None
            self.last_error = None
            return parsed
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            return None

    def enrich_news(self, text: str) -> dict[str, Any] | None:
        parsed = self._post_json_prompt(
            system_prompt=(
                "Return compact JSON only: summary,theme_tags,geography_tags,actors,why_it_matters,linkedin_angle,confidence. "
                "Keep summary short (max 3 sentences) and keep tags minimal."
            ),
            user_text=text,
            max_tokens=AI_MAX_TOKENS,
        )
        if not parsed:
            return None

        return {
            "summary": parsed.get("summary", ""),
            "theme_tags": parsed.get("theme_tags", []),
            "geography_tags": parsed.get("geography_tags", []),
            "actors": parsed.get("actors", []),
            "why_it_matters": parsed.get("why_it_matters", ""),
            "linkedin_angle": parsed.get("linkedin_angle", ""),
            "confidence": self._coerce_confidence(parsed.get("confidence"), 0.65),
        }

    def classify_news_domain(self, title: str, summary: str, themes: str) -> dict[str, Any] | None:
        parsed = self._post_json_prompt(
            system_prompt=(
                "Classify to one bucket only and return strict JSON: "
                "domain_bucket (offshore_wind|adjacent_energy|other_energy), confidence (0-1), reason_short."
            ),
            user_text=(
                f"Title: {title}\n"
                f"Summary: {summary}\n"
                f"Themes: {themes}\n"
                "Decide if this is directly offshore wind, adjacent energy context, or other energy/noise."
            ),
            max_tokens=180,
        )
        if not parsed:
            return None

        bucket = str(parsed.get("domain_bucket") or "").strip().lower()
        if bucket not in {"offshore_wind", "adjacent_energy", "other_energy"}:
            return None
        return {
            "domain_bucket": bucket,
            "confidence": self._coerce_confidence(parsed.get("confidence"), 0.5),
            "reason_short": str(parsed.get("reason_short") or ""),
        }

    def judge_news_match(self, item_a: dict[str, Any], item_b: dict[str, Any]) -> dict[str, Any] | None:
        parsed = self._post_json_prompt(
            system_prompt=(
                "You are strict at deciding if two news items describe the same real-world story/event. "
                "Return strict JSON with keys: same_story (yes|no), confidence (0-1), reason_short, overlap_entities (list), overlap_timeframe."
            ),
            user_text=(
                "Item A:\n"
                f"title={item_a.get('title','')}\n"
                f"summary={item_a.get('summary','')}\n"
                f"published_at={item_a.get('published_at','')}\n"
                f"source={item_a.get('source_name','')}\n\n"
                "Item B:\n"
                f"title={item_b.get('title','')}\n"
                f"summary={item_b.get('summary','')}\n"
                f"published_at={item_b.get('published_at','')}\n"
                f"source={item_b.get('source_name','')}"
            ),
            max_tokens=220,
        )
        if not parsed:
            return None

        same_story = str(parsed.get("same_story") or "").strip().lower()
        if same_story not in {"yes", "no"}:
            return None

        entities = parsed.get("overlap_entities")
        if not isinstance(entities, list):
            entities = []

        return {
            "same_story": same_story,
            "confidence": self._coerce_confidence(parsed.get("confidence"), 0.0),
            "reason_short": str(parsed.get("reason_short") or ""),
            "overlap_entities": [str(x).strip() for x in entities if str(x).strip()],
            "overlap_timeframe": str(parsed.get("overlap_timeframe") or ""),
        }

    def status(self, with_probe: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "enabled": bool(self.enabled),
            "provider": AI_PROVIDER,
            "model": AI_MODEL,
            "base_url": AI_BASE_URL,
            "endpoint": AI_ENDPOINT,
            "api_key_configured": bool(AI_API_KEY),
            "last_error": self.last_error,
            "probe_ok": None,
        }
        if with_probe and self.enabled:
            probe = self._post_json_prompt(
                system_prompt="Return strict JSON only with key ok=true.",
                user_text="ping",
                max_tokens=20,
            )
            data["probe_ok"] = probe is not None
            data["last_error"] = self.last_error
        return data

