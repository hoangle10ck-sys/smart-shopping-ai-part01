# Phase 4: History and search cache

## History

- `GET /api/history?limit=50&offset=0` returns recent sessions, newest first.
  Limit is 1–100; offset is non-negative. The response includes `items`, `total`,
  `limit`, and `offset`. Timestamps include the UTC offset.
- Items contain session ID, query, status, creation/completion time and the number
  of saved recommendations. The count comes from the snapshot when available,
  otherwise from existing recommendation rows.
- `GET /api/history/{session_id}` adds `result`, using the existing search read
  path. Snapshot and legacy semantics are unchanged. A session without a parsed
  requirement has `result: null`; a missing session returns 404.
- `/history` displays the latest 50 sessions, including failed attempts, with
  loading, empty, error/retry states and links to `/results/{session_id}`.
- This local single-user MVP lists the same sessions already accessible through
  the existing APIs. It does not add authentication or user-level access control.

## Database and cache

`search_cache_entries` is an additive table with a SHA-256 key, source session FK,
source snapshot timestamp, creation time, and indexed expiry time. It references
existing data instead of storing another catalog/result payload. Existing
`init_db()` registers and creates the table without altering old tables.

The `SearchCache` protocol separates storage from search orchestration;
`DatabaseSearchCache` implements it with the project's SQLAlchemy database.
No Redis or new dependencies are required.

Keys normalize case, Vietnamese accents, whitespace and list ordering. They
include category, budget bounds, currency, purposes, brands, requirement values
and priorities, exclusions and sorting. Significant quantity punctuation is
preserved. Key version and output-affecting search/LLM configuration are included;
keys never include credentials. Analysis confidence is not a scoring input.

TTL uses `cache_ttl_seconds` (`CACHE_TTL_SECONDS`, default 1800 seconds). Values
at or below zero disable caching. Expired entries are ignored, not deleted. Hits
do not extend expiry. A changed source snapshot or a source session that is not
COMPLETED invalidates the reference. No scheduled cleanup is introduced.

## Hit, miss and failure semantics

- Caching applies to Live Mode. Demo always executes the local provider and
  deterministic explanation, preserving its offline behavior.
- A fresh session first checks cache. On miss it runs the existing search,
  extraction, filtering, Python scoring and explanation pipeline. Only successful
  runs without search/enrichment warnings populate the cache.
- A hit creates only the destination session's raw records, recommendation rows
  and independent snapshot. Price, score, evidence, rank and original data time
  stay together. Shared Product/Offer records are never replayed or updated by a
  hit. A persisted warning identifies cached data and its timestamp.
- Successful reruns continue to search fresh, rather than use cache. Sessions
  with a previous successful result or existing raw rows cannot be replaced by
  a cache hit/fallback.
- After a provider failure on a fresh session, cache is checked again, allowing
  a valid result populated by another request while search was in flight. The
  response is COMPLETED with cached results and explicit failure/cache warnings.
  If no valid cache exists, the existing 503/FAILED handling applies.
- A failed refresh of a successful session keeps its own snapshot and stored
  results, even if another valid cache entry exists. Cache failures do not cause
  the old successful session to be marked COMPLETED.
- Cache publication and copied recommendation snapshots use the caller's
  transaction. Failed searches and partial results do not overwrite healthy cache.

No production database backfill, History duplication, scoring-weight change,
Docker, Voice, filter UI, expanded evidence UI or score-breakdown UI is included.
