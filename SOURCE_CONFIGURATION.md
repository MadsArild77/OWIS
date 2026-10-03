# Source configuration

Settings → Regulatory → Jurisdictions, organisations and sources manages a shared registry.
Settings → News contains the existing news source tools and fetch/processing controls.
EU is a separate jurisdiction from each of its 27 member countries. Norway,
Iceland and the UK are also available initially; more jurisdictions can be added.
Groups such as Nordics and Europe are display metadata, not legal jurisdictions.

Create organisations under a jurisdiction, optionally with a parent, then add
sources under them. For example: Norway → Stortinget → Energi- og miljøkomiteen
→ source. Choose content types separately from the fetch method. Organisation
priorities support all, topic matches or off, plus named person overrides.

Pause/resume retains configuration and article history. Pausing a jurisdiction
or organisation also pauses collection for its descendants. The editor does not
permanently delete records. Countries without a source ready for the existing
news pipeline are labelled “Not monitored”. This describes configured collection
capability, not successful collection or complete coverage.

## What runs now

- RSS/Atom and HTML-list sources containing the news content type feed the
  existing news collectors. Existing scheduling and extraction still apply.
- Source tests fetch public URLs and show up to five feed entries or HTML links,
  or a text excerpt for a single HTML page. Advanced CSS selectors limit previews.
- Tests do not create articles or run AI. They use bounded requests, validate
  redirects, and return explicit errors, empty results or unsupported status.
- ICS/API preview adapters, structured legal/calendar parsing, per-source
  scheduling, selectors in collection, and topic/person filtering are pending
  steps 2–3. Their settings can already be saved. Existing morning-report policy
  searches are not yet driven by this registry; integration is step 4.

HTML previews are generic extraction, not evidence that a calendar adapter works.
For example, Stortinget's calendar overview currently returns navigation and
programme links; a dedicated adapter must identify actual events in step 3.

## Storage and migration

On first access, the database registry is migrated transactionally into
`source_jurisdictions`, `source_organisations` and `configured_sources`.
`source_config_meta` records initialization and a configuration revision.
Existing names, URLs, enabled states and opaque legacy options (including auth)
are retained. Existing sources start under Unassigned; countries are not guessed.
Migration is idempotent and does not reintroduce previously deleted defaults.

After migration, the shared registry is authoritative. Legacy news tools read and
write a compatible projection through the existing registry module. Removing a
source in those tools pauses it and hides it from that projection; it remains
available in the new editor. Stable IDs distinguish sources sharing a host.
The old database table remains migration history, not an independently edited copy.

Custom YAML registry mode remains supported by the legacy tools. Shared settings
return a clear conflict in that mode and leave the external YAML unchanged.
Use the default database registry to enable shared configuration.

## Export, import and API

Export produces version 1 JSON with stable IDs. Legacy authentication settings
are excluded; source URLs and notes are exported as entered. Import merges by ID,
preserves absent records and existing legacy options, and validates the whole
hierarchy before saving atomically. Every imported record needs a stable ID.
Use the editor to create new records, or supply unique IDs in a hand-written file.

`GET /api/source-config` returns the snapshot and revision. Writes require that
revision and return HTTP 409 if it is stale. Reload before retrying.

- `POST /api/source-config/{jurisdictions|organisations|sources}`: `{revision, item}`
- `GET /api/source-config/export`
- `POST /api/source-config/import`: `{revision, configuration}`
- `POST /api/source-config/test`: source model, including optional stable ID

A saved source's last test is updated only when the tested configuration matches
the saved record. Unsaved draft previews do not overwrite saved test status.

## Validation

166 tests pass, including 23 configuration tests covering migration, compatibility,
parent pauses, graph validation, stale writes, atomic imports, previews and API
errors. Browser verification used an isolated database and created Norway →
Stortinget → Energi- og miljøkomiteen → calendar source, fetched a real HTML preview,
saved/reloaded the hierarchy and checked jurisdiction pause/resume propagation.
Production source configuration was not modified for this verification.
