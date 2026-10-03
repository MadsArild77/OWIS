import ipaddress
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

Follow = Literal['all', 'topics', 'off']


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str | None = Field(default=None, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1, max_length=160)
    enabled: bool = True


class Jurisdiction(Record):
    code: str = Field(min_length=2, max_length=12, pattern=r'^[A-Z0-9_-]+$')
    kind: Literal['country', 'supranational'] = 'country'
    groups: list[str] = Field(default_factory=list, max_length=10)


class PersonOverride(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    person: str = Field(min_length=1, max_length=160)
    follow: Follow


class Organisation(Record):
    jurisdiction_id: str = Field(min_length=1, max_length=80)
    parent_id: str | None = None
    kind: Literal['government', 'ministry', 'parliament', 'committee', 'authority', 'other'] = 'other'
    follow: Follow = 'topics'
    topics: list[str] = Field(default_factory=list, max_length=20)
    people: list[PersonOverride] = Field(default_factory=list, max_length=50)


class Source(Record):
    jurisdiction_id: str | None = None
    organisation_id: str | None = None
    url: str = Field(min_length=1, max_length=2048)
    content_types: list[Literal['news', 'regulation', 'consultation', 'calendar']] = Field(min_length=1, max_length=4)
    method: Literal['rss', 'html_list', 'html_page', 'ics', 'api'] = 'rss'
    topics: list[str] = Field(default_factory=list, max_length=20)
    follow: Literal['inherit', 'all', 'topics', 'off'] = 'inherit'
    interval_minutes: int = Field(default=360, ge=15, le=43200)
    selector: str = Field(default='', max_length=500)
    notes: str = Field(default='', max_length=2000)

    @field_validator('url')
    @classmethod
    def public_http_url(cls, value):
        try:
            parsed = urlsplit(value)
            if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username
                    or parsed.password or parsed.port not in {None, 80, 443}):
                raise ValueError('Use a public HTTP(S) URL without credentials and with a standard port.')
            host = parsed.hostname.lower()
            if host == 'localhost' or host.endswith(('.localhost', '.local')):
                raise ValueError('Local addresses are not supported.')
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address and not address.is_global:
                raise ValueError('Private network addresses are not supported.')
        except (ValueError, TypeError) as error:
            raise ValueError(str(error)) from error
        return value

    @field_validator('selector')
    @classmethod
    def css_selector(cls, value):
        if value:
            import soupsieve
            try:
                soupsieve.compile(value)
            except Exception as error:
                raise ValueError('Invalid CSS selector.') from error
        return value


class ConfigBundle(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    jurisdictions: list[Jurisdiction] = Field(default_factory=list, max_length=250)
    organisations: list[Organisation] = Field(default_factory=list, max_length=1000)
    sources: list[Source] = Field(default_factory=list, max_length=2000)
