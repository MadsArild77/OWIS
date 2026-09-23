from owis.modules.news.presentation.api import _build_collections


def test_fresh_story_precedes_old_high_scoring_group():
    rows = [dict(id=1, title='Old', published_at='2026-06-01T00:00:00Z', signal_score=99),
            dict(id=2, title='Old followup', published_at='2026-06-02T00:00:00Z', signal_score=99),
            dict(id=3, title='Fresh', published_at='2026-09-23T00:00:00Z', signal_score=20)]
    overrides = {1: {'collection_key': 'manual:old'}, 2: {'collection_key': 'manual:old'}, 3: {'collection_key': 'manual:new'}}
    result = _build_collections(rows, overrides, limit=3, items_per_collection=3)
    assert result[0]['collection_key'] == 'manual:new'
