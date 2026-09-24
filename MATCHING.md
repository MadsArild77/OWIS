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

The local preview remains AI-disabled. Railway login is active and its existing OpenAI configuration was used for the isolated evaluation below. No production environment settings were changed.

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

This sends 60 short synthetic articles and makes 30 pair assessments, using a temporary database. It covers Norwegian/English paraphrases, different contracts/suppliers/permits at one project, subsequent developments, different projects, unrelated stories and insufficient evidence. It exits nonzero if a case fails. Use `--max-usd 0.10` to set the evaluation-only conservative request budget and `--output` to select the JSON report. Unknown model pricing/endpoints are rejected. Failed requests retain their reserved cost; this is not a provider billing cap or a production-wide limit.

Live result on 2026-09-23: **30/30 passed**, including candidate retrieval for all same-event/update examples; **0 false same-event labels**. Model: `gpt-4o-mini`, embeddings: `text-embedding-3-small`. Actual API token usage priced at standard rates totals approximately **$0.00418107** (no cached-input discount assumed). Prices used: chat input $0.15/M, output $0.60/M; embeddings $0.02/M. See the checked-in `owis/tests/fixtures/news_match_evaluation.json` report. These are short synthetic development examples, not an independent benchmark or a production accuracy estimate.

The prompt requires concrete agreement on action/object and distinguishes suppliers and contract packages before assigning same-event. Cache version was advanced so old judgments are not reused. The earlier six-case prompt evaluation passed 4/6; the new prompt also passes those original six cases, but this single run does not establish repeatability.

Pricing references: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [embeddings](https://developers.openai.com/api/docs/models/text-embedding-3-small).

A manually curated set of real articles and measured candidate recall/false-merge rate are still needed before automatic merging is considered. All merging currently requires human confirmation.

Reference: [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings).


## Real-source spot check (2026-09-23)

A separate, pre-labeled 12-pair spot check used 55 stored feed records and six original publisher headlines (61 documents total). Retrieval ran against the whole corpus with the normal top-8 setting, yielding 97 candidate pairs; only the 12 labeled pairs were judged. Six same-event and two update pairs were all retrieved and correctly classified. Exact-label agreement was 11/12, with zero false same-event labels among the six non-same-event pairs. The one discrepancy was unrelated versus related_topic for different wind farms, so neither label suggests merging. Estimated usage cost: $0.00194319.

See `owis/tests/fixtures/real_news_match_evaluation.json` for source URLs, labels, results and limitations. Labels were assigned by the coding agent before the call, not independently by a domain expert. Three positive pairs are publisher language editions. The new multilingual sources are English/German/Danish; Norwegian remains synthetic-only. Most stored feed articles have roughly 140-character excerpts; added sources use original headlines after direct full-text retrieval failed. This is not a full-text or representative production benchmark. Full-corpus precision remains unknown. Keep human review and improve source text coverage before deployment.

The evaluator accepts `--cases path/to/labeled-cases.json --corpus path/to/articles.json --output work/result.json`. Real source texts and local databases are excluded from Git. The default synthetic evaluator now also measures retrieval within its complete input corpus rather than isolated pairs; the earlier checked-in synthetic result predates that evaluator change.
