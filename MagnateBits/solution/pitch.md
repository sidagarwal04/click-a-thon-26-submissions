# Pitch — why this submission scores

Atlys track: *"agents that instrument, analyze, and explain."* A feature spec goes in; a
production ClickHouse table, a refreshed versioned context layer, and PM-readable insights come
out — in one traced run, gated by a human approval step, with **every number mechanically
verified**. This doc maps **everything we built** — major and minor — to the judging rubric, so
no point is left on the table.

**Governing idea (say it once, it explains every design choice):** *the LLM proposes,
deterministic Python/SQL adjudicates.* Every LLM output passes a code/SQL gate; every stage has a
deterministic fallback, so the system degrades in quality, never in availability.

**At a glance (all verifiable in-repo):** ~18.7K LOC · **193 tests / 0 failures** across 15 files
· 8 curated MCP tools · 7 SQL-adjudicated contradiction checks · 12 parameterized query templates
· 15 numbered DDL lint rules (L1–L15) · 3 LLM backends · 2.48M rows over 8 base tables · 5 feature
tables built end-to-end.

---

## The rubric and where we win

| Criterion | Weight | Our headline |
|---|---|---|
| Use of ClickHouse & OSS | **25%** | ClickHouse is the *only* datastore — data, context layer, vector RAG, full-text, ops tables, versioning; all 3 OSS products wired (Langfuse/ClickStack/LibreChat). |
| Problem Fit | 20% | Solves the exact 3-agent loop; handles every planted trap; the unseen-spec generalization is *enforced by a test*. |
| Technical Implementation | 20% | Lint→dry-run→approval→execute→measure; grounding; 193 tests; degraded-mode + exit codes; would run in production. |
| Innovation | 20% | "One query no other DB can run" (semantic retrieval ⨝ funnel); contradiction detection where SQL adjudicates the LLM; mechanical context-freshness. |
| Scalability & Impact | 10% | Compute pushed into ClickHouse; token cost flat with data size; rollup MVs kept/dropped on measured reduction; projection remediation priced with real bytes. |
| Presentation | 5% | Every claim is backed by a number or a query a judge can rerun; artifacts per run. |

---

## 1. Use of ClickHouse & OSS (25%)

**ClickHouse is genuinely central — remove it and you rebuild the system as four services.**
- **One engine for everything:** the event data, the **versioned context layer** (`context_entry_log`, append-only, "current" = `LIMIT 1 BY entry_id`), the **vector RAG** (`cosineDistance` + HNSW `vector_similarity` index), **full-text** (`text` inverted index / `hasToken`), and all **ops tables** (`pipeline_runs`, `pipeline_approvals`, `insights_log`, `schema_snapshot_log`) live in ClickHouse. No Postgres, no Pinecone, no Elasticsearch, no Redis.
- **Primitives used deliberately, not decoratively:** `windowFunnel` (with the `toUInt64(toUnixTimestamp64Milli(...))` DateTime64 workaround — every funnel would fail without it), `quantileExact` window functions for a trailing-median/MAD anomaly computed *in SQL*, `corrStable` for correlations (raw rows never leave the DB), `AggregatingMergeTree` + `uniqState`/`uniqMerge` rollups, `ReplacingMergeTree` for versioning **and** dedup, `system.query_log` for real cost, `system.columns` for schema introspection & drift.
- **All three OSS products, load-bearing:** **Langfuse** traces every run and every LLM call (with a *mandatory* `context_version` argument — freshness is a function signature, not a claim); **ClickStack** = the official read-only `mcp-clickhouse` server running alongside our curated MCP (an asymmetric read-only/curated security pair); **LibreChat** = a multi-model chat front end over **2 MCP servers / 10 tools**. Spot-Award-eligible (all four).
- **8 curated MCP tools** expose the whole system agent-natively: `ask`, `list_features`, `run_pipeline`, `get_context`, `list_contradictions`, `explain_metric`, `context_diff`, and **`diagnose_segments`** (the hybrid query).

**Minor points that still count here:** `LowCardinality(String)` on enums / plain `String` on high-card ids; `id` typed `String` not `UUID` (the 32-char dashless hex would fail the load outright — the single most likely load failure, handled); `DateTime64(3)` to preserve millisecond precision; `Decimal(18,4)` for summed money vs `Float64` for approximate rates; per-type `CODEC(Delta, ZSTD)` / `ZSTD`; explicit sparse-serialization tuning `ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1))` with the arithmetic shown in the rationale.

## 2. Problem Fit (20%)

**The exact three agents, plus the thing the problem is really testing.**
- **Instrumentation Agent** — spec → production table: derives types, entity key, funnel order, engine, partitioning, TTL, MVs; lints + dry-runs before executing.
- **Analytics Agent** — plan → execute → interpret: computes everything in ClickHouse, LLM only interprets ≤60-row aggregate frames.
- **Context Agent** — a living, versioned, self-checking knowledge base with 7 contradiction checks.
- **Build for the unseen spec** — *enforced, not asserted*: `tests/test_generalization.py` is a grep guard that **fails if any source file names a known spec or a spec-unique column**, and the eval harness runs 4 fresh synthetic topologies through the no-LLM path. Nothing is tuned to the 5 practice specs.

**Every planted trap is handled (each is a scored moment):**
- **Poisoned sort key** (`ORDER BY (id, …)`): we *derive* `ORDER BY (event, timestamp, entity_key)`, lint-forbid id-first, and `legacy.py` remediates the 8 legacy tables with a measured projection.
- **Over-`Nullable`/no `LowCardinality`**: house rules + lint L2/L3.
- **Nested objects**: `payment.amount` → `payment_amount` flattening.
- **Heterogeneous / anonymous events**: one wide table with a **derived** shared entity key (`share_id`@0.95 on the dual-sided sharing spec, `group_id`@0.80, `visit_id`@0.92 over a 61.9%-coverage `user_id`), `disconnected_event_types` + `partial_identity_columns` tracked, **`uniqIf(col,col!='')` guard** enforced against the empty-string trap.
- **Dedup/backfill signals** *(Trap F, [V2])*: `_dedup_engine` picks `ReplacingMergeTree(<temporal version>)` by column *shape* so re-ingested rows collapse — generalizes to an unseen spec.
- **Context contradictions**: all three planted flaws surfaced *with executed SQL* — conversion-denominator conflict, `visa_issuance_eta_days` documented-but-absent, "on-time delivery" uncomputable — **and acted on** by the metric policy at answer time.
- **Table-name collision**: `f_<slug>_events`/`agg_*`/`mv_*` prefixes (spec 04's `drop_step` values literally shadow existing table names).

## 3. Technical Implementation (20%)

**Would it run in production? Yes — and here's the evidence.**
- **Schema pipeline with real guards:** `propose_ddl` (LLM) → **15 numbered lint rules (L1–L15)** → `dry_run()` in a scratch DB (returns the *verbatim* ClickHouse error) → bounded repair loops → mechanical coerce → **no-LLM `build_fallback_proposal`** (availability floor). The model never emits SQL that runs unchecked.
- **Human-in-the-loop, done right:** an **approval gate** on an append-only `pipeline_approvals` table, resolvable from CLI / the Streamlit console / `--yes`, with a terminal `timed_out` row so an abandoned run never looks "pending" — plus *([V2])* a **`--instructions` steering channel** (retention / partition grain / primary cut / PII-mask) injected as authoritative-but-lint-bounded constraints.
- **Numeric grounding:** every asserted number in a finding must appear (1% tol) in a cited query result, or it's demoted to `UNVERIFIED` at ≤0.25 — built to catch a real fluent-but-false "$0 median" hallucination.
- **Statistics in pure stdlib** a judge can re-derive by hand: two-proportion z-test (leave-one-out), MAD robust-z, Pearson + Fisher-z, Wilson interval, Cohen's h, odds ratio (Haldane), Benjamini-Hochberg.
- **Resilience:** degraded-mode writes partial artifacts; meaningful **exit codes** (0 clean / 1 hard fail / 2 degraded / 3 declined); a **read-only ClickHouse guard** blocks writes on the analytics path (verified it also doesn't over-block `SHOW CREATE`/`system.*`).
- **193 tests / 0 failures** across 15 files — including an adversarial audit that found **7 latent bugs in our own recent additions, all fixed and locked with tests** (crash, injection hardening, mock schema-validity, version-type guard, governance-context retention). We test our own code skeptically.

## 4. Innovation (20%)

- **"One query no other database can run"** *([V2], `diagnose_segments`)*: a single ClickHouse statement that CROSS JOINs **semantic issue-retrieval** (`cosineDistance` over the HNSW index) with a **per-segment `windowFunnel` conversion** — each row pairs a real metric with its likeliest documented cause. Live: iOS at 45% conversion (worst) ⨝ `known_issue.K1` at distance 0.29. No relational-only or vector-only store can express this.
- **"The LLM proposes, SQL adjudicates"** contradiction engine: 7 checks, each carrying its **executed `verification_sql` + result** — including **C6**, the check the pipeline runs *about itself* (it measures that a new feature table can't identity-join the 8 legacy tables — 0 joinable rows — and writes the segment-only join rule back as a caveat).
- **Mechanical context freshness:** analytics deliberately reads the *post-reconcile* snapshot (vN+1), and `complete_json` can't be called without a `context_version` — so the trace *proves* analytics reasoned on newer context than instrumentation saw.
- **Evidence-carrying derivations:** entity key via a 7-level lexicographic score with a legible rationale; funnel order via a three-way (spec/volume/**Copeland** timestamp) cross-check with Kendall-tau agreement, and disagreement is a first-class output.
- **Offline determinism** *([V2])*: a mock LLM backend runs the *entire* pipeline with zero credentials, deterministically — reproducible eval, and a live demonstration that the safety gates catch mock hallucinations exactly as real ones.

## 5. Scalability & Impact (10%)

- **Token cost is flat with data size:** the model only ever sees ≤60-row aggregate frames; the report header publishes real `rows_scanned_in_clickhouse` vs `rows_sent_to_llm` (e.g. 231K → 154) from `system.query_log` — *measured, not estimated*.
- **MVs earn their keep or get dropped, with evidence:** a rollup is kept only above a measured 5× reduction; dropped otherwise with the number recorded ("dropped WITH evidence beats kept on faith").
- **Legacy remediation is priced:** `legacy.py` adds a projection to the id-leading legacy tables and reports before/after `read_bytes` + the EXPLAIN.
- **Vector RAG scales the context layer:** when it grows past a promptable size, ranked retrieval keeps the prompt small while governance context (contradictions/gaps/metrics/known-issues) is *always* included.

## 6. Presentation (5%)

- **Everything is backed by a rerunnable number or query** — the antithesis of a hand-wave. Per-run artifacts land in `artifacts/runs/<run_id>/`: `insight_report.md`, `schema.sql` (executable, rationale as SQL comments), `proposal.json`, `context_diff.md`, `semantics.json`, `trace_url.txt`.
- **A Streamlit console** with 6 live views (schema-over-time, findings + the 4 confidence components extracted *in ClickHouse*, context diff via a FULL OUTER JOIN, runs with trace links, embedded chat) — all reading only from ClickHouse.
- **Docs a judge can navigate:** `README.md`, `docs/ARCHITECTURE.md`, `docs/EVALUATION.md` (every statistical formula + a real eval run), `PROJECT_SUMMARY_V2.md`, `new_additions.md`.

---

## The 90-second demo script
1. **Paste a spec, hit run.** Watch the 5 stages stream into `pipeline_runs` live; the run **pauses for schema approval** — show the DDL + rationale (`ORDER BY (event, timestamp, entity_key)`, the id-first anti-pattern rejected, sparse-serialization math). Approve.
2. **Context reconciles → version bumps.** Show a contradiction with its **executed proof SQL** (conversion computed *both* ways, 0.16× apart).
3. **Analytics.** Show an insight card with its 4 confidence components and the **"scanned 231K rows → sent 154 to the model"** header. Show grounding demoting a number that isn't in its cited query.
4. **The kill shot:** run `diagnose_segments` — **one query** returns iOS's 45% conversion paired with `known_issue.K1`. "No other database can run this."
5. **Prove it's not tuned:** run the **grep-guard test** live (fails if any file names a spec) and a **fresh mock topology** through the pipeline.

## Honest edges (state them before a judge finds them — it builds trust)
- Insight *usefulness* (vs correctness) is human-checked; everything else is mechanical.
- Benjamini-Hochberg is implemented + tested but not yet wired into the analytics loop.
- Four low-value optimizations are deliberately deferred (skip-index on new tables, PREWHERE, a `dictGet` region dimension, push notifications) — documented, not hidden.
- One audit residual: the *no-LLM fallback* DDL assumes a temporal `timestamp`; no real/known spec hits it and the LLM path is protected by dry-run+repair.
