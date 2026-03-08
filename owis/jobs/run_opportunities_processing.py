from owis.core.config.settings import OPPORTUNITIES_ACTIVE_PROFILES
from owis.core.storage.db import init_db
from owis.modules.opportunities.processing.pipeline import process_raw_item
from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
from owis.modules.opportunities.storage.repository import OpportunitiesRepository


def main() -> None:
    init_db()
    repo = OpportunitiesRepository()

    active_profiles = [p.strip().upper() for p in OPPORTUNITIES_ACTIVE_PROFILES if p.strip()]
    profile_bundle = load_profile_bundle(active_profiles=active_profiles)
    if not profile_bundle.get("by_company"):
        print("No active opportunities profiles loaded. Nothing to process.")
        return

    raws = repo.list_unprocessed_raw(limit=300)
    processed_count = 0
    rejected_count = 0

    for raw in raws:
        processed = process_raw_item(
            raw,
            profile_bundle=profile_bundle,
            active_profiles=active_profiles,
        )
        if processed is None:
            repo.mark_raw_rejected(raw["id"])
            rejected_count += 1
            continue

        repo.save_processed_item(processed)
        repo.mark_raw_processed(raw["id"])
        processed_count += 1

    print(f"Processed {processed_count} opportunities and rejected {rejected_count} notices.")


if __name__ == "__main__":
    main()