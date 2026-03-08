from platform.core.storage.db import init_db
from platform.modules.news.collectors.rss_fetcher import fetch_rss_items
from platform.modules.news.collectors.scrape_fetcher import fetch_scrape_items
from platform.modules.news.storage.repository import NewsRepository


def main() -> None:
    init_db()
    repo = NewsRepository()
    new_count = 0

    fetched_items = [*fetch_rss_items(), *fetch_scrape_items()]
    for item in fetched_items:
        if repo.upsert_raw_item(item):
            new_count += 1

    print(f"Fetched {len(fetched_items)} candidates and stored {new_count} new raw items.")


if __name__ == "__main__":
    main()
