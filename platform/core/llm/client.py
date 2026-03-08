import json
from typing import Any

import httpx

from platform.core.config.settings import AI_API_KEY, AI_BASE_URL, AI_ENABLED, AI_MODEL


class AIClient:
    def __init__(self) -> None:
        self.enabled = AI_ENABLED and bool(AI_API_KEY)

    def enrich_news(self, text: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        prompt = (
            "You are a market intelligence assistant for offshore wind. "
            "Return strict JSON with keys: summary, theme_tags, geography_tags, actors, why_it_matters, linkedin_angle, confidence. "
            "theme_tags/geography_tags/actors must be arrays of strings. confidence must be a number between 0 and 1."
        )

        body = {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:6000]},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(f"{AI_BASE_URL}/chat/completions", headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                "summary": parsed.get("summary", ""),
                "theme_tags": parsed.get("theme_tags", []),
                "geography_tags": parsed.get("geography_tags", []),
                "actors": parsed.get("actors", []),
                "why_it_matters": parsed.get("why_it_matters", ""),
                "linkedin_angle": parsed.get("linkedin_angle", ""),
                "confidence": float(parsed.get("confidence", 0.65)),
            }
        except Exception:
            return None
