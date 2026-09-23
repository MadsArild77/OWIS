# Matching news across languages

OWIS uses OpenAI embeddings (`text-embedding-3-small` by default) to retrieve possible matches, then the configured chat model (`gpt-4o-mini` by default) to classify each pair. Embedding similarity is not treated as proof that two articles describe the same event.

The review queue distinguishes `same_event`, `update`, and `uncertain`. Shared topics and unrelated articles are not offered for merging. Accepting an update creates a link between separate events; accepting a same-event suggestion merges all members of existing manual groups. Original article rows and URLs remain intact. Decisions are applied transactionally and cannot be replayed. Linked updates appear in Review.

## Configuration

The server must receive these environment variables (the application does not load `.env` automatically):

```text
OPENAI_API_KEY=<configure through your environment or secret manager>
OWI_AI_ENABLED=true
OWI_AI_PROVIDER=openai_compatible
OWI_AI_BASE_URL=https://api.openai.com/v1
OWI_AI_MODEL=gpt-4o-mini
OWI_AI_EMBEDDING_MODEL=text-embedding-3-small
OWI_MATCH_MAX_PAIRS=100
```

Restart the server after changing its environment. Setting a GitHub Actions secret does not automatically configure the local application or a Railway service. Never commit keys.

The existing local preview was started with AI disabled. As of 2026-09-23 no key was found in its process/user environment, and no repository-level GitHub Actions secrets were listed. GitHub deployment records point to Railway; the local Railway login is expired. Deployment credentials were not changed.

## Cost and behavior

- Default search window: 30 days; at most 350 recent articles, configurable up to 1,000.
- Embeddings are batched in groups of 32 and cached by content, model, provider endpoint and version.
- Pair assessments are cached, including negative results. Changed text/date or model settings invalidate them.
- Each run assesses at most `OWI_MATCH_MAX_PAIRS` pairs. Unassessed pairs take priority on the next run. Prior human decisions are respected.
- Article A and B get equal prompt budgets. The model compares entities, project, event type, location, date and numbers; article text is explicitly treated as untrusted data.
- API failures are not stored as negative matches. Missing configuration returns an explicit error.
- The 0.55 candidate-similarity threshold and 0.70 review confidence threshold are provisional, not measured probabilities.
- Existing automatic title-based grouping is unchanged; whole-group expansion applies to saved manual groups. An update link is undirected, not a verified chronological timeline.

## Validation

Run `python -m pytest owis/tests -q`. The suite includes deterministic tests for cross-language candidate routing with stub embeddings, cache invalidation, API responses, transaction rollback, preservation of group members and update links. These tests do not establish real model accuracy.

For a small live check, configure the environment above and run:

```powershell
.\.venv\Scripts\python.exe -m owis.scripts.evaluate_matching --live
```

This sends 12 short synthetic articles and makes six pair assessments, using a temporary database. The cases cover Norwegian/English paraphrases, different contracts at one project, a subsequent development, similar announcements at different projects, unrelated stories and insufficient evidence. It exits nonzero if a case fails. The live check has not been run because credentials are unavailable.

A manually curated set of real articles and measured candidate recall/false-merge rate are still needed before automatic merging is considered. All merging currently requires human confirmation.

Reference: [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings).
