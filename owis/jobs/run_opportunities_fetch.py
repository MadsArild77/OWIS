from datetime import datetime, timezone

from owis.core.config.settings import (
    OPPORTUNITIES_ACTIVE_PROFILES,
    OPPORTUNITIES_DAYS_BACK,
    OPPORTUNITIES_ENABLED_SOURCES,
    TED_API_KEY,
)
from owis.core.storage.db import init_db
from owis.modules.opportunities.collectors.dealengine_fetchers import (
    fetch_dealengine_style_notices_with_report,
)
from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
from owis.modules.opportunities.storage.repository import OpportunitiesRepository


def main() -> None:
    init_db()

    profiles = [p.strip().upper() for p in OPPORTUNITIES_ACTIVE_PROFILES if p.strip()]
    profile_bundle = load_profile_bundle(active_profiles=profiles)
    if not profile_bundle.get("by_company"):
        print("No active opportunities profiles found. Nothing to fetch.")
        return

    repo = OpportunitiesRepository()
    fetched_items, source_report = fetch_dealengine_style_notices_with_report(
        profile_bundle=profile_bundle,
        enabled_sources=OPPORTUNITIES_ENABLED_SOURCES,
        days_back=OPPORTUNITIES_DAYS_BACK,
        ted_api_key=TED_API_KEY,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for item in fetched_items:
        if not item.get("fetched_at"):
            item["fetched_at"] = now_iso
        if repo.upsert_raw_item(item):
            inserted += 1

    print(f"Fetched {len(fetched_items)} candidates and stored {inserted} new opportunity raw items.")
    print(f"Source report: {source_report}")


if __name__ == "__main__":
    main()