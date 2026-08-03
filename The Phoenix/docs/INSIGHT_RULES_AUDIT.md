# Insight layer: ClickHouse best-practices audit

This audit, dated 2026-08-01, evaluates the four insight tables in `phoenix_next` against
clickhouse-best-practices v0.1.0 (31 rules). The earlier `clickhouse_rules_audit` artifact
covered the original concurrency engine; this one covers the layer built on top of it.
Every number below was measured, not estimated.

## What changed as a result

| Rule | Finding | Fix | Status |
|------|---------|-----|--------|
| `schema-pk-cardinality-order` | `session_insight_facts` led with content_id at 3,366 cardinality and put platform at 15 and country at 5 behind session_start at 25,967, so neither could prune | Re-keyed to `(toDate(session_start), country, platform, content_id, session_start, video_session_id)` with a four-column PRIMARY KEY prefix | Done |
| `schema-pk-cardinality-order` | `content_entry_cohorts` had the same inversion | Re-keyed to `(video_type, country, platform, app_version, content_id, cohort_minute)` | Done |
| `query-join-use-any` | Five `LEFT JOIN content` sites could fan out: `content` is a ReplacingMergeTree and duplicate keys exist between a reload and the merge that collapses them | `LEFT ANY JOIN` at all five | Done |
| `agent-query-safety` | Ten shipped queries carried read budgets and no execution-time cap | Added `max_execution_time = 30` and `timeout_before_checking_execution_speed = 0` | Done |
| `schema-types-enum` | `lateness_class` was `LowCardinality(String)` with exactly four values fixed at schema time | Changed to `Enum8`, which validates at insert time | Done |
| (TTL setting) | `docs/RETENTION.md` did not mention `ttl_only_drop_parts` | Documented: without it TTL expiry becomes the `ALTER TABLE DELETE` mutation path | Done |
| `query-index-skipping-indices` | No skip index on any insight table | Deferred deliberately: the rule says consider skip indices after types, keys and materialized views, and the key was the actual problem. Re-measure at Stage 5 volume | Deferred |

## A correctness hazard the audit found by accident

`content_entry_cohorts` and `playback_health_minute` are ReplacingMergeTree tables, so ORDER BY
IS the dedup key. Both refreshes write at a grain that includes `video_type`, and neither ORDER
BY contained it. Two rows differing only by `video_type` shared a key and one would have been
discarded silently. Measured 0 collisions today because `video_type` is functionally determined
by `content_id` with 0 exceptions out of 3,366, but that invariant was undeclared and unchecked,
so nothing would have caught it changing. `video_type` is now in both keys.

## Measured effect of the re-key

| Query | Before | After |
|-------|--------|-------|
| `session_facts_app_version_health` worst shape rows read | 21,732 | 10,866 |
| `session_facts_app_version_health` worst shape bytes read | 2,243,290 | 1,121,645 |
| `session_facts_app_version_health` granules | 3 of 3 | 1 of 1 |
| Committed row budget | 65,199 | 32,598 |

The halving is NOT all attributable to the key. The earlier measurement carried two stored
versions per session and the new one carries one, because the table was rebuilt. The clean
signal for the key is the granule count: 3 of 3 down to 1 of 1. A benchmark claiming a 2x win
it did not earn is worse than one claiming nothing.

## The Enum actually validates, and that was checked

`schema-types-enum` promises insert-time validation. Promised is not the same as working, so it
was tested: inserting `lateness_class = 'late_ish'` into `late_event_audit` is now rejected with
`Code: 691, Unknown element 'late_ish' for enum`. Before the change that row would have been
stored, and a fifth class would have appeared in a dashboard with nothing to flag it.
`scripts/test_lateness_classifier.sh` still passes 8 of 8 against the Enum column, including the
assertion that an on-time event is ABSENT from the audit rather than merely uncounted.

## Rules that were considered and deliberately not followed

### query-join-consider-alternatives

This rule recommends a dictionary for a small dimension table. The repository already tried this
and `sql/schema/02_content.sql` records the measured reason it was rejected: `dictGet` returned
empty string for keys that provably exist on this Cloud service, because dictionaries load per
replica, so the answer depended on which node served the query. Rule overridden by a local
measurement.

### query-mv-incremental

This rule prefers incremental materialized views for real-time aggregation. The four insight
refreshes are batch `INSERT ... SELECT` instead, because an insert-trigger materialized view
sees one block and cannot express an aggregate over a session's lifetime. The same reason
`sql/pipeline/01_derive_intervals.sql` is not a materialized view, documented in that file.

### schema-types-minimize-bitwidth

The rule applies to `active_seconds`, which is `UInt32` against a measured maximum of 7,309,
which `UInt16` would hold. Left as `UInt32` because a 24-hour session is 86,400 seconds, past
the `UInt16` ceiling of 65,535. The rule asks for the smallest type that accommodates the
range, and the range is the plausible one and not only the observed one.

## Still open, and owned by the concurrency engine rather than this layer

`sql/pipeline/01_derive_intervals.sql` and `sql/pipeline/03_derive_incremental.sql` carry the
same `LEFT JOIN content` fan-out hazard, at line 89 and line 145 respectively, and
`sql/pipeline/03b_derive_incremental_atomic.sql` line 121 does too. These were NOT changed, on
purpose, for two reasons: they are the validated concurrency engine, and the project rule is
that its logic is not modified without explicit team approval; and a teammate is actively
working in those files. The fix is one word, `ANY`, and it needs the engine owner's approval
rather than a silent edit.

## Reproduce

```bash
CH_DATABASE=phoenix_next ./scripts/rebuild_insights.sh    # recreate with the current keys
CH_DATABASE=phoenix_next ./scripts/validate_insights.sh   # Gate A, all four, zero diffs
CH_DATABASE=phoenix_next ./scripts/bench_insights.sh      # Gate B, budgets and raw_events check
./scripts/test_lateness_classifier.sh                     # the Enum8 classifier, four classes
PROBES_ONLY=1 ./scripts/ingest_10x.sh                     # ingestion path, batch-size gate, probes
```

`scripts/ingest_10x.sh` is the Stage 5 ingestion path and was written against the insert rules
rather than audited afterwards: it sizes batches from the corpus at run time and REFUSES to run
outside the 1,000 to 100,000 row band in either direction, it uses server-side `INSERT ... SELECT`
so `insert-format-native` is satisfied by no data crossing the wire at all, and it issues no
`OPTIMIZE FINAL`.
