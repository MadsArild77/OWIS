from owis.core.config.settings import (
    NOTION_API_KEY,
    NOTION_OPPORTUNITIES_DB_ID,
    NOTION_VERSION,
    OPPORTUNITIES_NOTION_EXPORT_ENABLED,
)
from owis.core.notion.opportunities_export import OpportunitiesNotionExporter
from owis.core.storage.db import init_db
from owis.modules.opportunities.storage.repository import OpportunitiesRepository


def main() -> None:
    init_db()

    if not OPPORTUNITIES_NOTION_EXPORT_ENABLED:
        print("Notion export disabled. Set OWI_OPP_NOTION_EXPORT_ENABLED=true")
        return

    if not NOTION_API_KEY or not NOTION_OPPORTUNITIES_DB_ID:
        print("Missing Notion config: set NOTION_API_KEY and NOTION_OPPORTUNITIES_DB_ID (or OWI_NOTION_OPPORTUNITIES_DB_ID)")
        return

    repo = OpportunitiesRepository()
    items = repo.high_relevance(limit=50)

    exporter = OpportunitiesNotionExporter(
        api_key=NOTION_API_KEY,
        database_id=NOTION_OPPORTUNITIES_DB_ID,
        notion_version=NOTION_VERSION,
    )

    result = exporter.export_items(items=items, max_items=50, dry_run=False)
    print(result)


if __name__ == "__main__":
    main()