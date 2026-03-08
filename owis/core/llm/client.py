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

    def _build_payload(self, text: str) -> dict[str, Any]:
        prompt = (
            "Return compact JSON only: summary,theme_tags,geography_tags,actors,why_it_matters,linkedin_angle,confidence. "
            "Keep summary short (max 3 sentences) and keep tags minimal."
        )
        return {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:AI_INPUT_MAX_CHARS]},
            ],
            "temperature": 0.1,
            "max_tokens": AI_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

    def enrich_news(self, text: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        if AI_PROVIDER not in {"openai_compatible", "openai", "mistral", "deepseek"}:
            return None

        try:
            with httpx.Client(timeout=25) as client:
                response = client.post(
                    f"{AI_BASE_URL.rstrip('/')}{AI_ENDPOINT}",
                    headers=self._build_headers(),
                    json=self._build_payload(text),
                )
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

