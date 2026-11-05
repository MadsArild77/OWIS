from fastapi import APIRouter, Query

from owis.core.sources import registry
from owis.modules.policy import storage

router = APIRouter(prefix='/api/policy', tags=['policy'])


@router.get('/items')
def items(region: str = '', content_type: str = '', offset: int = Query(0, ge=0)):
    data = registry.snapshot()
    rows = [r for r in storage.items(snapshot=data) if (not region or r['region'] == region)
            and (not content_type or r['content_type'] == content_type)]
    return {'items': rows[offset:offset + 100], 'total': len(rows), 'sources': storage.source_status(data)}
