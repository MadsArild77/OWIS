from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsRawItem:
    id: int
    source_name: str
    article_url: str
    title_raw: str
    summary_raw: str
    content_raw: str
    content_hash: str
    published_at: str | None
    fetched_at: str
    status: str


@dataclass
class NewsProcessedItem:
    id: int
    raw_item_id: int
    title: str
    cleaned_text: str
    summary: str
    theme_tags: str
    geography_tags: str
    actors: str
    why_it_matters: str
    signal_score: int
    confidence: float
    linkedin_angle: str
    linkedin_candidate: int
    processed_at: str
