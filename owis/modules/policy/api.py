from fastapi import APIRouter, Query
from datetime import datetime, timezone

from owis.core.sources import registry
from owis.modules.policy import storage

router = APIRouter(prefix='/api/policy', tags=['policy'])


@router.get('/items')
def items(region: str = '', content_type: str = '', offset: int = Query(0, ge=0)):
    data = registry.snapshot()
    rows = [r for r in storage.items(snapshot=data) if (not region or r['region'] == region)
            and (not content_type or r['content_type'] == content_type)]
    if content_type == 'consultation':
        now = datetime.now(timezone.utc).isoformat()
        rows.sort(key=lambda r: (not bool(r.get('deadline') and r['deadline'] > now), r.get('deadline') or '9999'))
    return {'items': rows[offset:offset + 100], 'total': len(rows), 'sources': storage.source_status(data)}
