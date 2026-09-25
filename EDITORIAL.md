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

Source RSS/scrape fetch and health requests have a 5-second connection timeout and 15-second network inactivity timeout, with at most three retries (four attempts total). Only transient network errors and HTTP 408/429/500/502/503/504 retry, with 1/2/4-second backoff. Long Retry-After values stop the request instead of holding up the job. Failed attempts are logged separately. Article fulltext retains its existing 12-second timeout and no retries. These are network timeouts, not a hard deadline for the entire multi-source job.

Story collections now sort by newest publication date first, then score and article count, so older high-scoring groups cannot crowd out recent news.


### Open-source expansion and case descriptions
Interesting feedback queues article enrichment. Otherwise, automatic alternative lookup requires a matching interest area and signal score at least `OWI_OPEN_SOURCE_MIN_SCORE` (default 70). New raw articles use a cheap preliminary signal score; existing articles use their stored score. Thin evidence (<800 readable characters), restricted and blocked sources qualify. Searches check at most three distinct candidates in total, keep up to two verified open same-event sources, and reserve/cache attempts for seven days, including no-result searches. Existing verified alternative evidence survives rechecks. Broad web discovery still requires BRAVE_SEARCH_API_KEY; without it, only collected sources are searched.

Case descriptions aim for 150–250 Norwegian words when the evidence supports it; short excerpts remain shorter with uncertainty disclosed. Cards show 340-character previews; detail views retain the full text. A background backfill button updates at most five eligible older articles per run, preserving IDs and human feedback. News and settings are mutually exclusive views, including source tables and status controls.
