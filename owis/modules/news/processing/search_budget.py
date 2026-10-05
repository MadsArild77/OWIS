"""One monthly budget for all web searches (Tavily free plan: 1,000 basic searches a month).

Priorities when the month's searches run short:
1. research the reader starts (may use the whole quota),
2. the morning report's policy outlook (stops at the reserve kept for research),
3. automatic searches - open versions of paywalled stories and extra coverage - paced
   evenly over the rest of the month so the quota is not spent in the first week.

Counts are OWIS's own; searches made with the same key elsewhere are not seen.
"""
from __future__ import annotations

import calendar
import math
import os
from datetime import datetime, timedelta, timezone

from owis.core.storage.db import get_conn

AUTOMATIC = {"alternative", "coverage"}
PURPOSES = {"research", "policy", *AUTOMATIC}


class SearchBudgetExceeded(RuntimeError):
    pass


def _number(name: str, default: str) -> int:
    try:
        return max(0, int(os.getenv(name, default)))
    except ValueError:
        return int(default)


def status(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    limit = _number("OWI_SEARCH_MONTHLY_LIMIT", "1000")
    reserve = min(_number("OWI_SEARCH_RESEARCH_RESERVE", "100"), limit)
    with get_conn() as conn:
        rows = conn.execute("SELECT purpose, used_at FROM news_search_usage WHERE used_at >= ?",
                            (month_start.isoformat(),)).fetchall()
    used = len(rows)
    before_today = sum(1 for r in rows if r["used_at"] < day_start.isoformat())
    automatic_today = sum(1 for r in rows if r["used_at"] >= day_start.isoformat() and r["purpose"] in AUTOMATIC)
    days_left = calendar.monthrange(now.year, now.month)[1] - now.day + 1
    automatic_per_day = max(0, math.floor((limit - reserve - before_today) / days_left))
    by_purpose = {p: sum(1 for r in rows if r["purpose"] == p) for p in sorted(PURPOSES)}
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {"used": used, "limit": limit, "research_reserve": reserve, "by_purpose": by_purpose,
            "automatic_today": automatic_today, "automatic_per_day": automatic_per_day,
            "resets_on": next_month.date().isoformat()}


def allowed(purpose: str, now: datetime | None = None) -> bool:
    s = status(now)
    if purpose == "research":
        return s["used"] < s["limit"]
    if s["used"] >= s["limit"] - s["research_reserve"]:
        return False
    if purpose in AUTOMATIC:
        return s["automatic_today"] < s["automatic_per_day"]
    return True


def spend(purpose: str, now: datetime | None = None) -> None:
    """Reserve one search before it is made (providers charge for the request, even if it fails)."""
    if purpose not in PURPOSES:
        raise ValueError(f"Unknown search purpose: {purpose}")
    if not allowed(purpose, now):
        raise SearchBudgetExceeded("This month's web-search quota is used up for this kind of search.")
    with get_conn() as conn:
        conn.execute("INSERT INTO news_search_usage(purpose, used_at) VALUES(?, ?)",
                     (purpose, (now or datetime.now(timezone.utc)).isoformat()))
