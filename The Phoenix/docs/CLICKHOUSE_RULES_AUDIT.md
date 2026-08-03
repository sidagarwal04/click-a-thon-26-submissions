# ClickHouse Rules Audit, the generation-1 concurrency schema

The `phoenix` schema and its serving queries, checked against the 31-rule ClickHouse
best-practice set. Split out of [`database_details.md`](database_details.md), which is now the
data dictionary and nothing else. The equivalent audit for the insight layer is
[`INSIGHT_RULES_AUDIT.md`](INSIGHT_RULES_AUDIT.md).


`[V:clickhouse_rules_audit]` The schema and serving design were checked against the 31-rule
ClickHouse best-practice set. Twelve rules apply to this design. Eleven are compliant; one is
a deviation that was **measured rather than assumed**, and one is a violation that belongs to
the ingest owner.

| Rule | Status | Measured |
|---|---|---|
| `schema-pk-cardinality-order` | **deviation, measured harmless** | see below |
| `schema-pk-prioritize-filters` | compliant | `platform` leads and is the only single-dimension filter that prunes |
| `schema-pk-filter-on-orderby` | compliant | platform-containing shapes read 16,384 rows; all others 30,662 |
| `schema-types-lowcardinality` | compliant | every string dimension is `LowCardinality`; highest cardinality is 65 |
| `schema-types-avoid-nullable` | compliant | **0** `Nullable` columns across the whole database |
| `schema-types-native-types` | compliant | epoch millis converted to `DateTime64(3)` at ingest, not kept as `Int64` |
| `schema-partition-low-cardinality` | compliant | `raw_events` has **8** active partitions against a 100-1,000 guideline |
| `schema-partition-lifecycle` | compliant | partitioning exists to drop or replace a day, not to speed queries |
| `insert-mutation-avoid-update` | compliant | retraction via `CollapsingMergeTree`; zero `ALTER TABLE ... UPDATE` in the repo |
| `insert-optimize-avoid-final` | compliant | no `OPTIMIZE FINAL` anywhere, and no `FINAL` modifier in any serving query |
| `query-mv-incremental` | compliant | three incremental MVs, zero exceptions in `query_views_log` |
| `insert-batch-size` | **violation, not ours** | average **66** rows per insert against a 10,000 minimum |

### The key-order deviation, and why it stays

`schema-pk-cardinality-order` says order sort-key columns low-to-high cardinality. Measured
cardinalities on the frozen slice:

| Column | Distinct values | Position in the shipped key |
|---|---:|---:|
| `country` | **1** | 2 |
| `video_type` | 3 | 3 |
| `platform` | 10 | 1 |
| `app_version` | 65 | 5 |
| `minute` | 1,532 | 6 |
| `content_id` | **3,357** | 4 |

The shipped key violates the rule twice: `country` has a single value and can never prune
anything from position 2, and `content_id` is the highest-cardinality column sitting fourth,
ahead of two lower ones.

**So it was measured instead of argued about.** Three candidate keys, built in a scratch
database on identical data (`sql/experiments/key_order_candidates.sql`,
`./scripts/key_order_experiment.sh`):

| Filter shape | A shipped | B cardinality-ordered | C dead column dropped |
|---|---|---|---|
| unfiltered | 3/3 | 3/3 | 3/3 |
| platform | **2/3** | **2/3** | **2/3** |
| country | 3/3 | 3/3 | 3/3 |
| content | 3/3 | 3/3 | 3/3 |
| video_type | 3/3 | 3/3 | 3/3 |
| app_version | 3/3 | 3/3 | 3/3 |
| platform + country | **2/3** | **2/3** | **2/3** |
| content + platform | **2/3** | **2/3** | **2/3** |
| **on disk** | **55.09 KiB** | **75.08 KiB** | 54.84 KiB |

**Granule pruning is identical across all three keys on every shape, and the rule-compliant
order costs 36 percent more disk.** Moving `content_id` last breaks compression locality:
adjacent rows stop sharing a content id, so the column stops compressing well.

The reason the rule does not bite is that it is a rule about **skipping granules**, and this
table has **three**. There is essentially nothing to skip. `schema-pk-cardinality-order` earns
its CRITICAL rating on tables with thousands of granules, and this serving table is 61 KiB by
design.

**Decision: the key stays as it is.** `[A]` The deviation is harmless at this scale and the
compliant alternative is measurably worse on storage. Revisit if the delta table grows by
two or more orders of magnitude, at which point granule count becomes large enough for
ordering to matter and the measurement should simply be re-run. **Falsified by:** the same
experiment showing different granule counts once the table is large. **Decided by:** the team.

One change that is defensible today and was **not** made: dropping `country` from the key
entirely (candidate C) is marginally smaller and prunes identically. It is not worth an
immutable-key migration for 0.25 KiB, and `country` gains real values the moment the dataset
covers more than one market.

### The insert-batch violation is not ours to fix

`[V:clickhouse_rules_audit]` The replay producer inserts an average of **66 rows** per
statement (minimum 34, maximum 500, across 834 inserts), against a 10,000 to 100,000 guideline.
Each insert makes a part, so this is merge pressure waiting to matter at scale.

Filed as [`issues/ingest-3.md`](issues/ingest-3.md) with two remedies for the ingest owner
rather than fixed here, because changing it means changing the ingest script and that is
outside this work's ownership boundary. It is not hurting anything measurable today: merges
are keeping up, and no benchmark query reads `raw_events` at all.

