from pydantic import BaseModel


class NewsItem(BaseModel):
    id: int
    raw_item_id: int
    title: str
    summary: str
    theme_tags: str
    geography_tags: str
    actors: str
    why_it_matters: str
    signal_score: int
    confidence: float
    linkedin_angle: str
    linkedin_candidate: int
    source_name: str
    article_url: str
    published_at: str | None = None
