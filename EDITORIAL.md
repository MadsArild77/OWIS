# Editorial news workflow

The reading view now presents articles with one-click relevant/not-for-me feedback, optional reasons, undo, interest filters and saved LinkedIn drafts. Review retains manual grouping and same-event/update decisions. Relevance and draft selection are separate signals. Current preference examples are selected by matching title terms within the chosen topic (or all topics); this is retrieval of examples, not fine-tuning. Negative examples cannot by themselves exclude a new article. Historical legacy ratings are not silently converted into new topic preferences.

RSS and scraped index pages discover links first. Known URLs are deduplicated before processing. Relevance rules screen obvious unrelated content; uncertain cases and relevant preference examples can use the configured low-cost model. Relevant/uncertain short feeds then attempt public article extraction. Full feed text is retained without an extra request. Cached outcomes are reused; the explicit Read more/check access action permits retry. Failed extraction preserves feed evidence. Metadata distinguishes open, restricted, blocked and unknown; openness is a retrieval result, not a licensing statement. Extraction is conservative and requires enough text within an article/main page.

Restricted articles trigger a bounded search among up to 350 collected articles. With BRAVE_SEARCH_API_KEY configured, one additional web search supplies at most three candidates. At most three local candidates are fetched, and at most two alternatives are retained after an open-content check and same-event judgment (confidence >=0.8). Without configured AI, candidates cannot be verified as the same event. Broad web search is optional and has separate provider billing. No paywall circumvention is implemented.

Case summaries request Norwegian, concrete facts, explicit uncertainty and source attribution. LinkedIn drafts are generated only on request, saved once and returned from storage thereafter. Evidence snapshots preserve original and alternate URLs, text hashes, retrieval times and the source used for the draft. Drafts are not published automatically.

## Saved scan URLs and preferences

The news_source_registry table is the authoritative scan list in the standard configuration. Source name, scan URL, RSS/scrape type, topic, enabled state and existing options persist. Packaged YAML seeds the first run only; deleting all registered sources no longer resurrects defaults. Alternate configured YAML paths retain the existing file-backed behavior. Topic preferences, undo state, drafts and source evidence are SQLite records. Retention preserves records with editorial feedback or drafts.

Startup creates one integrity-checked database backup per UTC day before migrations. This is a startup backup, not a continuously scheduled off-site backup. Manual backup: `python -m owis.scripts.backup_database --output path/to/backup.db`. Restoring a backup requires stopping the service and replacing its SQLite file. Secure and copy backup files off the volume separately for disaster recovery.

Railway startup requires OWI_DB_PATH to be inside RAILWAY_VOLUME_MOUNT_PATH. Mount a persistent volume at /data and use OWI_DB_PATH=/data/owi.db. The new owis-review environment has its own /data volume. Existing production has no volume and must be migrated before deploying this version there. No production data should be replaced with local test fixtures.

Configuration: OWI_FULLTEXT_ENABLED=true (default), OWI_AI_ENABLED=true and existing OPENAI_API_KEY for real AI features. Keep gpt-4o-mini. The local preview currently has AI disabled; automatic approval review blocked starting an AI-enabled background preview. Railway live validation is tracked in PROJECT_STATUS.md.

Validation: 84 tests pass, including persistence/undo conflicts, backup/source restoration, filtering before network requests, access classification, source attribution, independent draft intent and refusal to start on ephemeral Railway storage. Existing frontend JavaScript passes syntax checking; the new reading view has been inspected in the browser. Tests use simulated AI/network responses; live provider coverage varies by source. Interest expansion currently applies to the existing source corpus; additional scan URLs can be added through Settings.

Live validation completed in owis-review: draft generation, scan-source persistence, feedback persistence and undo, and draft persistence after a service restart. Energiwatch homepage-only import resolved to its RSS feed and passed feed health validation. Production migration remains separate.


### Source diagnostics
Source fetches (web and scheduled collectors) and manual health checks now append persistent `news_source_events` records. Settings → Feilhistorikk shows the latest 100 attempts per URL, including timestamp, operation, error category, HTTP status, message and result count. Successful attempts do not erase older failures; zero results are recorded separately from errors. History starts with this release. Query strings and URL credentials are removed from diagnostic messages and displayed URLs. Data uses the existing persistent SQLite volume and backups.
