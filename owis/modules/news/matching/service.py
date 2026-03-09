from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from owis.core.llm.client import AIClient


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _tokenize(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]{3,}", str(text or "").lower())}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / max(union, 1)


def _domain_compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    pair = {a, b}
    return pair == {"offshore_wind", "adjacent_energy"}


def build_candidate_pairs(items: list[dict[str, Any]], days_window: int = 7, top_k: int = 8) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    by_id = {int(x.get("id") or 0): x for x in items if int(x.get("id") or 0) > 0}
    rows = [x for x in by_id.values()]

    pairs: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for i, left in enumerate(rows):
        left_id = int(left.get("id") or 0)
        left_dt = _parse_dt(left.get("published_at") or left.get("processed_at"))
        left_bucket = str(left.get("domain_bucket") or "other_energy")
        left_tokens = _tokenize(f"{left.get('title','')} {left.get('summary','')}")
        left_actors = _tokenize(str(left.get("actors") or ""))

        scored: list[tuple[dict[str, Any], float]] = []
        for right in rows[i + 1 :]:
            right_id = int(right.get("id") or 0)
            if right_id <= 0 or right_id == left_id:
                continue

            right_bucket = str(right.get("domain_bucket") or "other_energy")
            if not _domain_compatible(left_bucket, right_bucket):
                continue

            right_dt = _parse_dt(right.get("published_at") or right.get("processed_at"))
            if left_dt and right_dt:
                if abs((left_dt - right_dt).days) > max(days_window, 1):
                    continue

            right_tokens = _tokenize(f"{right.get('title','')} {right.get('summary','')}")
            right_actors = _tokenize(str(right.get("actors") or ""))

            title_sim = _jaccard(left_tokens, right_tokens)
            actor_sim = _jaccard(left_actors, right_actors)
            heuristic = (0.75 * title_sim) + (0.25 * actor_sim)

            if heuristic < 0.14:
                continue
            scored.append((right, heuristic))

        scored.sort(key=lambda x: x[1], reverse=True)
        for right, score in scored[: max(top_k, 1)]:
            pairs.append((left, right, score))

    return pairs


def judge_pair(ai: AIClient, item_a: dict[str, Any], item_b: dict[str, Any], heuristic_score: float) -> dict[str, Any]:
    ai_result = ai.judge_news_match(item_a=item_a, item_b=item_b)
    if ai_result is None:
        return {
            "same_story": "no",
            "confidence": min(max(0.2 + heuristic_score, 0.0), 0.49),
            "reason_short": "ai_unavailable_or_invalid",
            "overlap_entities": [],
            "overlap_timeframe": "",
            "fallback": True,
        }

    return {
        "same_story": str(ai_result.get("same_story") or "no"),
        "confidence": float(ai_result.get("confidence") or 0.0),
        "reason_short": str(ai_result.get("reason_short") or ""),
        "overlap_entities": ai_result.get("overlap_entities") or [],
        "overlap_timeframe": str(ai_result.get("overlap_timeframe") or ""),
        "fallback": False,
    }


def should_enqueue_review(judgement: dict[str, Any]) -> bool:
    same_story = str(judgement.get("same_story") or "no").lower()
    confidence = float(judgement.get("confidence") or 0.0)
    if judgement.get("fallback"):
        return confidence >= 0.35
    return same_story == "yes" and confidence >= 0.70


def make_manual_collection_key() -> str:
    return f"manual:review:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def window_start_iso(days_window: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=max(days_window, 1))
    return dt.isoformat()
