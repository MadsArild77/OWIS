import logging
from typing import Any
from fastapi import HTTPException
from owis.core.llm.client import AIClient
from types import SimpleNamespace
from owis.modules.news.processing.collections import _cased_collections
from owis.modules.news.processing.match_review import _run_match_review


def run_case_accounts_after_fetch(deadline: float | None = None) -> dict[str, Any]:
    """Write accounts for cases that gained a development; never breaks a fetch."""
    try:
        from owis.modules.news.processing import cases
        return cases.write_accounts(_cased_collections("core"), deadline=deadline)
    except Exception:
        logging.getLogger(__name__).exception("Case accounts failed")
        return {"skipped": "case accounts failed"}


def run_coverage_after_fetch(deadline: float | None = None) -> dict[str, Any]:
    """Search for extra coverage of important single-source stories; never breaks a fetch."""
    try:
        from owis.modules.news.processing.coverage import fill_coverage_gaps
        return fill_coverage_gaps(deadline=deadline)
    except Exception:
        logging.getLogger(__name__).exception("Coverage search failed")
        return {"skipped": "coverage search failed"}


def run_matching_after_fetch(deadline: float | None = None) -> dict[str, Any]:
    """Group new coverage automatically; failures never break a fetch."""
    if not AIClient().enabled:
        return {"skipped": "AI is not enabled"}
    try:
        return _run_match_review(SimpleNamespace(lookback_items=350, days_window=14, top_k=8, domain_bucket="core", auto_apply=True), deadline=deadline)
    except HTTPException as exc:
        return {"skipped": str(exc.detail)}
    except Exception:
        logging.getLogger(__name__).exception("Automatic story matching failed")
        return {"skipped": "matching failed"}
