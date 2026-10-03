from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from owis.core.sources import registry, probe
from owis.core.sources.models import ConfigBundle, Source

router = APIRouter(prefix='/api/source-config', tags=['source configuration'])


class Change(BaseModel):
    revision: int = Field(ge=0)
    item: dict


class Import(BaseModel):
    revision: int = Field(ge=0)
    configuration: ConfigBundle


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except registry.Conflict as error:
        raise HTTPException(409, str(error)) from error
    except ValidationError as error:
        raise HTTPException(422, '; '.join(e['msg'] for e in error.errors())) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get('')
def read_configuration():
    return call(registry.snapshot)


@router.get('/export')
def export_configuration():
    return call(registry.export_config)


@router.post('/import')
def import_configuration(payload: Import):
    return call(registry.import_config, payload.configuration, payload.revision)


@router.post('/test')
def test_configuration_source(payload: Source):
    call(registry.ensure)
    return call(probe.test_source, payload.model_dump())


@router.post('/{kind}')
def change_configuration(kind: Literal['jurisdictions', 'organisations', 'sources'], payload: Change):
    return call(registry.apply, payload.revision, {kind: [payload.item]})
