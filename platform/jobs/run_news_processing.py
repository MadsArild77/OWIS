from platform.core.storage.db import init_db
from platform.modules.news.processing.pipeline import process_raw_item
from platform.modules.news.storage.repository import NewsRepository


def main() -> None:
    init_db()
    repo = NewsRepository()
    raws = repo.list_unprocessed_raw(limit=100)
    processed_count = 0

    for raw in raws:
        processed = process_raw_item(raw)
        repo.save_processed_item(processed)
        repo.mark_raw_processed(raw["id"])
        processed_count += 1

    print(f"Processed {processed_count} raw items.")


if __name__ == "__main__":
    main()
