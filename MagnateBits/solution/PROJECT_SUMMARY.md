# Atlys `solution` — Master Project Summary

> **One line:** A feature spec (`spec.md` + `events.ndjson`) goes in; a production ClickHouse table, a refreshed versioned context layer, and PM-readable insights come out — in one Langfuse trace, gated by a human approval step, with every number mechanically verified.
>
> **Governing thesis (stated everywhere):** *the LLM proposes, deterministic Python/SQL adjudicates.* Every LLM output is gated (lint, dry-run, grounding, evidence reconciliation, metric policy); every stage has a deterministic fallback so the pipeline degrades in quality, never in availability.

~18K LOC Python (excl. tests), ~1.5K LOC tests (103 test functions across 11 files). Runs on a Claude subscription via the `claude` CLI (no API key) by default; `ATLYS_LLM_BACKEND=api` swaps in the Anthropic SDK.

---

## 1. Architecture — three agents, one trace

```
spec.md + events.ndjson
      │
   profile.py  ── deterministic: field types, entity key, funnel order (NO LLM)
      │
 agents/instrumentation.py ── propose_ddl (LLM) → ddl.lint → ddl.dry_run
      │
   ┌── APPROVAL GATE (pipeline_approvals table: CLI stdin / UI button / --yes) ──┐
   │   rejected/timed-out → nothing executed, EXIT_DECLINED (3)                   │
   └── approved → apply(): execute DDL → load → bakeoff (measure ORDER BY) ───────┘
      │
 agents/context_agent.py ── reconcile(): 6 contradiction checks vs the new table → version N→N+1
      │
 agents/analytics.py ── plan_queries (LLM picks templates) → execute (SQL, aggregates only)
      │                  → interpret (LLM writes Findings) → confidence.py → grounding.py
      │
   report.py → artifacts/runs/<run_id>/*  +  Langfuse trace URL
```

Five stages (`context.load → instrumentation → context.reconcile → analytics → report`) in **one Langfuse trace**; every stage's status written live to `pipeline_runs`. Exit codes are meaningful: **0** clean, **1** hard failure (nothing written), **2** degraded (partial artifacts written), **3** declined.

**The freshness proof is mechanical:** analytics deliberately reads the context snapshot taken *after* reconciliation (vN+1), newer than the vN instrumentation read. `llm.complete_json()` **cannot be called without a `context_version` argument**, so every LLM span in the trace records which snapshot fed it — freshness is enforced by a function signature, not asserted.

---

## 2. The three agents

### 2.1 Instrumentation Agent (`agents/instrumentation.py`, `ddl.py`, `profile.py`, `mapping.py`, `bakeoff.py`, `house_rules.md`)
Spec → production ClickHouse table. **LLM used for judgment only** (entity-key choice, which rollup to materialize, rationale wording); everything mechanical is deterministic.

- **Profiling is deterministic, no LLM** (`profile.py`, over raw NDJSON in Python — pre-load): field types/nullability/cardinality; nested objects flattened via dotted paths (`payment.amount` → `payment_amount`).
- **Entity-key derivation** — a **7-level lexicographic priority tuple** (event-type coverage, row coverage, id-shaped name, named-in-spec-bullets, per-entity multi-step coherence, first-mention order, name length). Row-unique ids excluded. Emits a *confidence + English rationale* (`share_id`@0.95 on the dual-sided sharing spec, `group_id`@0.80, not blindly `user_id`).
- **Funnel-order derivation, three independent ways cross-checked**: spec-bullet order, descending volume, and **Copeland pairwise ranking** over per-entity timestamp precedence; agreement measured by **Kendall-tau**; disagreement is a first-class always-recorded output.
- **DDL house rules** (`house_rules.md`, fed verbatim into the prompt): ONE wide table per feature (`event` discriminator + union of fields); `ORDER BY (event, timestamp, <entity_key>)` — never id-first; `PARTITION BY toYYYYMM(timestamp)`; `LowCardinality` enums / plain `String` ids / `id` as **String not UUID** (32-char hex would fail load) / `DateTime64(3)` / `Decimal(18,4)` money; **no `Nullable` on hot columns**; `CODEC(Delta, ZSTD)` timestamps; **18-month TTL paired with a longer-lived rollup MV**; explicit sparse-serialization tuning `ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1))` with the arithmetic shown in the rationale.
- **Lint + dry-run before execution** (`ddl.py`): 15+ numbered house-rule checks (L1 no id-leading ORDER BY, L2 no Nullable on hot cols, …) fed back verbatim to the model on repair; `dry_run()` renders into a scratch db and returns the *verbatim ClickHouse error* as the repair signal. Bounded repair loops (2 lint + 2 DDL), then mechanical `_coerce_to_rules()`, then a full **no-LLM `build_fallback_proposal()`** — the availability floor.
- **Bake-off** (`bakeoff.py`): after load, measures the chosen `ORDER BY` vs a timestamp-first straw-man on the same funnel query using real `read_bytes` from `system.query_log`; appends the ratio to the rationale; drops the straw-man either way (honest even when equal at sample volume).
- **MV keep/drop gate**: measures `reduction_factor = source/target` after load; drops the MV with recorded evidence if <5×. AggregatingMergeTree + `uniqState` for distinct rollups.
- **`_disconnected_events` / `_partial_identity_columns`**: detects anonymous events (no entity/user id) and identity columns with <100% coverage → the **`uniq('')` empty-string trap**.

### 2.2 Context Agent (`agents/context_agent.py`, `contextlayer/*`)
A living, versioned, self-checking knowledge base **in ClickHouse**.

- **Storage = append-only ClickHouse tables** (`context_entry_log` MergeTree; "current" = `ORDER BY version DESC LIMIT 1 BY entry_id`), plus `context_snapshot`, `context_changelog`, `contradiction`, `schema_snapshot_log`. **Deliberately NOT a vector store** — the argued rationale: ~60–150 entries fit in a prompt under 20k chars; embeddings would add infra and make *which* context fed a decision nondeterministic. **No embeddings, no ANN index, no text index.**
- **Seeding is deterministic markdown parsing, no LLM** (`bootstrap.py`) — 43 entries from `base_context.md`; idempotent (body-hash based). A blockquote restating a metric differently is promoted to its own entry so the conflict is directly comparable.
- **Detects new tables without being told** — `schema_delta()` diffs the live `system.columns` fingerprint against the last run's captured fingerprint.
- **Six contradiction checks, "LLM proposes, SQL adjudicates"** (`checks.py`), each carrying `verification_sql` + executed result + `verified=1`:
  - **C1 definition_conflict** — two conversion definitions with different denominators; computes *both rates in one query* to show they disagree (measured 0.16× apart).
  - **C2 undefined_term / uncomputable_metric** — a formula term resolving to no table/column; if in a denominator → metric disputed.
  - **C3 schema_mismatch** — every backticked column checked vs `system.columns`; reports nearest real column + type (`visa_issuance_eta_days` documented but absent → nearest `eta_shown`).
  - **C4 self-admitted uncomputable** — regex on the body ("not computable", "handled by other systems").
  - **C5 stale_entry** — a documented `ORDER BY` whose lead key the queries never use — gated by a **measured selectivity probe**, so a genuine low-card discriminator is *not* flagged.
  - **C6 join_assumption_violated** — *the check the pipeline generates about itself*: measures that the new feature table can't identity-join the 8 legacy tables (0 joinable rows) and writes back a `gap` + a segment-level `relationship` entry that downstream findings cite.
  - **C7 (optional, off by default)** — LLM proposes candidate contradictions; each survives only if its verification SQL runs *and* returns rows.

### 2.3 Analytics Agent (`agents/analytics.py`, `queries/*`, `confidence.py`, `grounding.py`, `metric_policy.py`)
Plan → execute → interpret. **All computation in ClickHouse; the model never sees a raw event row** (only ≤60-row aggregate frames).

- **Plan** — one LLM call picks **audited template ids + params from a catalog built from live `FeatureSemantics`; it never writes SQL.** `_sanitize_params()` does closed-set validation (drops invented columns/params). Deterministic `default_plan()` fallback.
- **Template library T01–T12** (`queries/templates.py`, parameterized by `FeatureSemantics`, never a feature name): funnel (`windowFunnel`), funnel-by-segment, segment-vs-baseline (leave-one-out two-proportion inputs), measure distribution (`quantileExact`), time-between-steps, **daily anomaly (median/MAD robust-z computed in SQL via window functions)**, numeric driver buckets, **cross-reference to the legacy funnel at segment+day level only**, data quality, and **two correlation templates** (Pearson `corrStable` + point-biserial, with Fisher-z significance). Templates *refuse* degenerate/circular combinations (`TemplateError`) rather than return a meaningless number.
- **Real cost measurement** — each query stamped with a `query_id`; real `read_rows`/`read_bytes` read back from `system.query_log`. Report header publishes `rows_scanned_in_clickhouse` vs `rows_sent_to_llm` (e.g. 188,440 → 300) — measured, not claimed.
- **Confidence** (`confidence.py`) — a four-component score `0.30·sample_adequacy + 0.30·statistical_strength + 0.20·context_support + 0.20·data_quality`, arithmetic over evidence the LLM supplied, never LLM-self-reported. `sample_adequacy` uses the **smaller arm's n** and hard-caps at 0.40 when n<100. Statistical strength is method-dispatched: two-proportion z-test / MAD robust-z / Fisher-z Pearson / descriptive.
- **Numeric grounding** (`grounding.py`) — every asserted number must appear (within 1% tolerance, incl. ×100/÷100 restatement) in a cited query result, else the finding is **demoted to informational with an `UNVERIFIED` caveat**. Built to catch a real hallucination (a fluent false "$0 median" at 0.77 confidence).
- **Metric policy** (`metric_policy.py`) — while a `definition_conflict` is open, an unqualified conversion number is **refused/rewritten to DISPUTED with both definitions labelled by `entry_id@version`** — no silent pick.
- **Findings** carry `what / why / so_what / recommended_action`, `metric_definition_used` (exact `entry@version`), confidence breakdown, context refs, severity ∈ {info, watch, act_now}.

---

## 3. Everything ClickHouse
- **Single source of truth**: data, the context layer, ops tables (`pipeline_runs`, `pipeline_approvals`, `insights_log`, `schema_snapshot_log`) all live in ClickHouse.
- Primitives used: `windowFunnel` (with the `toUInt64(toUnixTimestamp64Milli(...))` workaround — windowFunnel rejects DateTime64), `quantileExact` window functions for trailing-median MAD, `corrStable` (correlation computed in-DB, raw rows never leave), `uniqState`/`uniqMerge` AggregatingMergeTree rollups, `system.query_log` for real cost, `system.columns`/`system.tables` for introspection and schema-drift.
- **Read-only guard** (`ch.py`): method-level read/write split; `run_select` strips string literals then blocks mutating keywords + multi-statements; narrow `SHOW CREATE` allowance; `system.*` reads permitted.
- **Legacy remediation** (`legacy.py`): prices the 8 production tables' id-leading `ORDER BY` and fixes one with a measured `ADD PROJECTION p_funnel (toDate(timestamp), device_type, user_id)` — before/after `read_bytes` + EXPLAIN proof (1.16× on `destination_card_clicked`).

---

## 4. OSS integration (all three, meaningfully — Spot-Award eligible)
- **ClickHouse / ClickStack** — the official read-only `mcp-clickhouse` server runs alongside the curated `atlys-mcp` (deliberate asymmetric security pair: raw read-only exploration vs. curated tools).
- **Langfuse** — the observability spine; `context_version` propagated through every LLM call; graceful no-op degrade; **placeholder-key detection**; region handling; real `auth_check()` in `verify()`.
- **LibreChat** — multi-model chat frontend (Ollama Cloud/local) consuming **2 MCP servers / 10 tools**; tool calls routed to the host `claude`-subscription MCP via `host.docker.internal`. Verified live per the README.
- **MCP server** (`atlys_mcp/server.py`) exposes `ask`, `list_features`, `run_pipeline`, `get_context`, `list_contradictions`, `explain_metric`, `context_diff`. Feature resolution uses **inverse-document-frequency ranking** and **refuses to guess** when ambiguous (raises `_Ambiguous`).

---

## 5. Visualization (`ui/app.py`, Streamlit)
Six views, all reading **only** from ClickHouse (every view is a live `SELECT`): **Run pipeline** (launches the pipeline as a subprocess, live-polls `pipeline_runs`, renders the **approval gate** with Approve/Reject writing back to `pipeline_approvals`), **Schema changes over time** (from `schema_snapshot_log`), **Insights + confidence** (4 components extracted via `JSONExtract` in ClickHouse), **Context layer diff** (FULL OUTER JOIN in ClickHouse), **Runs** (trace links), **Chat** (embedded LibreChat).

---

## 6. Evaluation & testing
- **T8 eval harness** (`evalharness.py`) — two tables. **Table 1**: 5 known specs re-verified from run history, *re-running `dry_run()` live*. **Table 2**: 4 fresh synthetic mock topologies (`tools/mock_spec.py`) driven through the **no-LLM deterministic path**, "valid SQL" measured by *executing* each query. Honest verdict logic (0/0 = REVIEW not PASS; no partial credit).
- **Anti-overfitting, two-pronged**: (1) `tests/test_generalization.py` — a **grep guard** that fails if any source file names a known spec slug or a spec-unique column; (2) the fresh mock topologies.
- **103 test functions / 11 files** covering: read-only guard, all 6 contradiction checks, approval-gate race/timeout, metric policy, bake-off + legacy, template feature-agnosticism + injection-safety + live SQL validity + no-bare-`uniq`, correlation, grounding discrimination, MCP feature-resolution refusal, eval-harness verdict logic.
- **Statistics in pure stdlib `math`** (judge can re-derive by hand): two-proportion z-test (leave-one-out), MAD robust-z, Pearson + Fisher-z, Wilson interval, Cohen's h, odds ratio (Haldane), Benjamini-Hochberg FDR.

---

## 7. Token discipline / cost
- Model never sees raw rows — only ≤60-row aggregate frames; high-entropy id tokens redacted from prompts.
- **Effort ladder** (`llm.py`): `--effort low` by default (documented: unset cost ~5× wall-clock and ~3.6× output tokens for no quality gain); steps low→medium→high only on validation retry.
- Real token/cost accounting captured from the CLI envelope; `rows_scanned_in_clickhouse` vs `rows_sent_to_llm` published per run.

---

## 8. Deliverables produced per run (`artifacts/runs/<run_id>/`)
`insight_report.md`, `schema.sql` (executable DDL with rationale as SQL comments), `proposal.json`, `context_diff.md`, `semantics.json`, `trace_url.txt`. Plus `out/`: versioned `context_vN.md`, `CHANGELOG.md` (v1→v15 append-only), `eval/results.md`, `legacy_projection.md`.

---

## 9. Known gaps (self-documented in docs/EVALUATION.md §5)
1. **Benjamini-Hochberg is written + tested but NOT wired into `analytics.py`** — per-segment testing across ~27 destinations can find spurious significance ~once/run.
2. **`deep_linear` mock topology genuinely FAILS** — the no-LLM fallback MV-proposal path mis-names a 2-levels-deep flattened column (`payment.card.network`); reproducible.
3. **No test asserts SQL-side vs Python-side statistic parity** (robust-z computed in both).
4. **Insight *quality* (vs correctness) is only human-checked** — nothing mechanically judges whether a finding is *interesting*.
5. **`queries/stats.py` uses different confidence weights** (0.35/0.35/0.15/0.15) than the live `confidence.py` (0.30/0.30/0.20/0.20) — a dormant footgun; `queries/stats.py` is a reference impl not imported by the live pipeline.
6. **`metric_policy` subject aliasing is hardcoded to "conversion"** (`_SUBJECT_ALIASES`, "sessions"/"application_started") — not generalized to arbitrary metric conflicts.
7. **Several `ch.py` guard bugs are worked around, not fixed** (rejects the word "system"; `max_result_rows` throws) — handled but fragile.
8. **Test count cited inconsistently** (135 in README vs 148 in EVALUATION.md; actual test *functions* ≈103).

---

## Appendix — the design tenets, verbatim
- *The LLM proposes; SQL adjudicates.* Every LLM output passes a deterministic gate.
- *Derived, not assumed.* Entity key, funnel order, types, segment dims all come from the events at runtime — enforced by a grep guard.
- *No trace, no credit.* `context_version` is a mandatory argument; freshness is a function signature.
- *An MV/finding/contradiction with its measurement is stronger than one on faith.* Everything is priced (`read_bytes`, reduction factor, verification SQL result).
- *Degrade in quality, never in availability.* Every LLM site has a deterministic fallback; exit codes distinguish clean/degraded/declined.
