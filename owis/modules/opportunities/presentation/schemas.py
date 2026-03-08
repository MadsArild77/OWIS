from pydantic import BaseModel


class OpportunityItem(BaseModel):
    id: int
    raw_item_id: int
    title: str
    source_name: str
    source_url: str
    buyer: str
    country: str
    summary: str
    opportunity_family: str
    mechanism_type: str
    deadline: str | None = None
    strategic_fit: str
    competition_level: str
    matched_services: str
    matched_qualifiers: str
    recommended_action: str
    why_it_matters: str
    signal_score: int
    confidence: float
    profile_name: str
    processed_at: str
    notice_id: str
    publication_date: str | None = None