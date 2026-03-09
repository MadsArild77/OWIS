import json
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

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

    def _post_json_prompt(self, system_prompt: str, user_text: str, max_tokens: int | None = None) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        if AI_PROVIDER not in {"openai_compatible", "openai", "mistral", "deepseek"}:
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
                response = client.post(
                    f"{AI_BASE_URL.rstrip('/')}{AI_ENDPOINT}",
                    headers=self._build_headers(),
                    json=payload,
                )
                response.raise_for_status()
                api_payload = response.json()

            content = api_payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception:
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
            "confidence": float(parsed.get("confidence", 0.65)),
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
            "confidence": max(0.0, min(float(parsed.get("confidence", 0.5)), 1.0)),
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
            "confidence": max(0.0, min(float(parsed.get("confidence", 0.0)), 1.0)),
            "reason_short": str(parsed.get("reason_short") or ""),
            "overlap_entities": [str(x).strip() for x in entities if str(x).strip()],
            "overlap_timeframe": str(parsed.get("overlap_timeframe") or ""),
        }
