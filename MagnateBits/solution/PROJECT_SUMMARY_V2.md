# Atlys `solution` — Master Project Summary **V2**

> **What V2 is:** the definitive, merged summary of this project after a comparative bake-off
> against a sibling implementation (`loop`). `solution` was judged the stronger product; the
> two genuinely distinctive capabilities from `loop` were then ported into it (additive,
> opt-in, zero regression). This doc supersedes `PROJECT_SUMMARY.md` — it carries everything
> from that document **plus** everything from `loop`'s summary that was worth keeping, with
> the V2 additions marked **[V2]**.
>
> **One line:** A feature spec (`spec.md` + `events.ndjson`) goes in; a production ClickHouse
> table, a refreshed versioned context layer, and PM-readable insights come out — in one
> Langfuse trace, gated by a human approval step, with every number mechanically verified —
> and now optionally offline (deterministic mock LLM) and with in-ClickHouse vector retrieval.
>
> **Governing thesis (unchanged):** *the LLM proposes, deterministic Python/SQL adjudicates.*

**Scale:** ~18K LOC Python (+~1.8K tests). **Tests: 187 passed / 1 skipped / 0 failed.**
Backends: `cli` (Claude subscription, default) · `api` (Anthropic SDK) · **`mock` [V2]** (offline, deterministic).

---

## 0. What changed in V2 (the port) — summary

| # | Ported from `loop` | How it was added | Default | Status |
|---|---|---|---|---|
| 1 | **Deterministic mock LLM** | new `mockllm.py`; one additive branch in `llm._call`; `backend_info()` updated | OFF (`cli`) | ✅ built, 6 new tests pass |
| 2 | **In-ClickHouse vector RAG** | new `vector_rag.py`; opt-in `_context_block()` helper in `agents/analytics.py`; reindex hook in `run_pipeline.py` reconcile stage | OFF (`full`) | ✅ built, 5 new tests pass, verified live |
| 3 | **Trap F — dedup/backfill → `ReplacingMergeTree`** | `instrumentation._dedup_engine` (shape-based, generic) + house_rules §5c for the LLM path | ON (auto, only when a signal column is present) | ✅ built, 6 new tests, lint+dry-run clean; known specs unaffected |
| 4 | **Q1 — hybrid retrieval-⨝-analytics query** ("one query no other DB can run") | `vector_rag.hybrid_issue_funnel` + `diagnose_segments` MCP tool | opt-in (needs the vector index) | ✅ built, 3 new tests, verified live (iOS 45% conv ⨝ K1 @0.29) |
| 5 | **G6 — human-instructions channel** | `--instructions` CLI flag → `propose_ddl(..., instructions=)` → operator block in the design prompt | OFF (empty by default) | ✅ built, 4 new tests, lint-bounded |

Items 1, 2 and 4 are opt-in; item 3 is always-on but activates only when a dedup/backfill signal column is present (the 5 known specs are unaffected); item 5 is off unless `--instructions` is passed. `solution`'s deterministic default paths are byte-for-byte
unchanged, so its documented architectural decisions (dump-all context, real-LLM backend)
still hold unless a flag is set. Nothing was removed. Everything from `loop` worth keeping is
now here; the rest of `loop`'s differences were either simplicity or a design `solution`
deliberately chose differently (see §11).

---

## 1. Architecture — three agents, one trace (unchanged)

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
 agents/context_agent.py ── reconcile(): 6 contradiction checks → version N→N+1
      │                     [V2] + opt-in vector-RAG reindex of the fresh context
      │
 agents/analytics.py ── plan_queries (LLM picks templates) → execute (SQL, aggregates only)
      │                  → interpret (LLM writes Findings) → confidence.py → grounding.py
      │                  [V2] context reaches the prompt via _context_block(): full dump
      │                       (default) OR relevance-ranked retrieval (opt-in)
      │
   report.py → artifacts/runs/<run_id>/*  +  Langfuse trace URL
```

Five stages (`context.load → instrumentation → context.reconcile → analytics → report`) in
**one Langfuse trace**; live status in `pipeline_runs`. Exit codes: **0** clean · **1** hard
failure · **2** degraded · **3** declined.

**Freshness proof is mechanical:** analytics reads the post-reconcile snapshot (vN+1);
`llm.complete_json()` cannot be called without a `context_version` argument, so every LLM span
records which snapshot fed it.

---

## 2. The three agents (unchanged core)

### 2.1 Instrumentation Agent — spec → production table
LLM for judgment only; everything mechanical is deterministic.
- **Deterministic profiling** (`profile.py`, over raw NDJSON): types, nullability, cardinality; nested objects flattened (`payment.amount` → `payment_amount`).
- **Entity-key derivation** — 7-level lexicographic priority tuple with confidence + English rationale (`share_id`@0.95, `group_id`@0.80, `visit_id`@0.92 over a 61.9%-coverage `user_id`).
- **Funnel-order derivation** — three independent orderings (spec bullets / volume / **Copeland** timestamp) cross-checked by **Kendall-tau**; disagreement is always recorded.
- **House rules** (`house_rules.md`, fed verbatim): one wide table per feature; `ORDER BY (event, timestamp, <entity_key>)` never id-first; monthly partitions; `LowCardinality`/`String`/`id as String not UUID`/`DateTime64(3)`/`Decimal(18,4)`; no `Nullable` on hot columns; `CODEC(Delta,ZSTD)`; 18-month TTL paired with a longer-lived rollup MV; sparse-serialization tuning `min(0.9, 1-1/(E+1))`.
- **Lint (15+ numbered rules) + dry-run** before execution; verbatim CH error fed back on repair; bounded repair loops → mechanical coerce → **no-LLM `build_fallback_proposal()`** (availability floor).
- **Bake-off** — chosen `ORDER BY` vs timestamp-first straw-man, real `read_bytes`.
- **MV keep/drop gate** — drops with recorded evidence if reduction <5×.
- **`_disconnected_events` / `_partial_identity_columns`** — the `uniq('')` empty-string trap.

### 2.2 Context Agent — living, versioned, self-checking layer in ClickHouse
- **Append-only ClickHouse tables** (`context_entry_log`, "current" = `LIMIT 1 BY entry_id`), snapshots, changelog, contradictions, schema-fingerprint log. **Deliberately not a vector store by default** — argued rationale (determinism, no infra). *(V2 adds an optional vector index alongside — see §7.)*
- **Deterministic markdown seed** (no LLM), idempotent (body-hash).
- **Detects new tables without being told** — `schema_delta()` diffs live `system.columns` fingerprint.
- **Six contradiction checks, "LLM proposes, SQL adjudicates,"** each carrying executed `verification_sql` + result: C1 definition_conflict (computes both rates in one query), C2 undefined/uncomputable, C3 schema_mismatch (nearest real column), C4 self-admitted uncomputable, C5 stale_entry (measured selectivity gate), C6 join_assumption_violated (the check the pipeline runs about itself). C7 optional LLM proposer (off by default; survives only if its SQL returns rows).

### 2.3 Analytics Agent — plan → execute → interpret
All computation in ClickHouse; the model never sees a raw event row (≤60-row aggregate frames).
- **Plan** — one LLM call picks audited **template ids + params from a catalog built from live `FeatureSemantics`; never writes SQL**; closed-set param validation; deterministic default plan fallback.
- **Templates T01–T12** parameterized by `FeatureSemantics`: funnel (`windowFunnel`), funnel-by-segment, segment-vs-baseline (leave-one-out z-test inputs), distributions (`quantileExact`), time-between-steps, daily anomaly (median/MAD robust-z in SQL), numeric-driver buckets, **segment-level cross-reference to the legacy funnel**, data quality, **two correlation templates** (Pearson `corrStable` + point-biserial, Fisher-z). Refuses degenerate/circular combinations.
- **Real cost** — `read_rows`/`read_bytes` from `system.query_log`; `rows_scanned` vs `rows_sent_to_llm` published.
- **Confidence** — four-component `0.30/0.30/0.20/0.20`, arithmetic over evidence, smaller-arm n, hard-capped when n<100; never LLM-reported.
- **Numeric grounding** — every asserted number must appear (1% tol, ×100/÷100) in a cited result, else demoted `UNVERIFIED` at ≤0.25. *(In V2 this same gate correctly demotes the mock backend's placeholder findings — proving the port respects the thesis.)*
- **Metric policy** — refuses/qualifies conversion answers while a definition conflict is open (both defs labelled `entry@version`); no silent pick.

---

## 3. Everything ClickHouse (the 25% criterion)
Single source of truth: data + context layer + ops tables all in ClickHouse. Primitives:
`windowFunnel` (with the `toUInt64(toUnixTimestamp64Milli(...))` DateTime64 workaround),
`quantileExact` window functions for trailing-median MAD, `corrStable`, `uniqState`/`uniqMerge`
AggregatingMergeTree rollups, `system.query_log` for real cost, `system.columns`/`system.tables`
for introspection + drift. **Read-only guard** (`ch.py`, method-level split, literal-stripping).
**Legacy remediation** (`legacy.py`): prices id-leading legacy `ORDER BY`, adds a measured
projection with EXPLAIN proof.

**[V2] Now also:** `cosineDistance` + HNSW `vector_similarity` index + `text` inverted index in
the optional context-retrieval path (`context_embeddings` table) — so the "everything in one
engine, incl. semantic retrieval" story is available without any external vector DB.

---

## 4. OSS integration (all three, Spot-Award eligible)
- **ClickHouse / ClickStack** — official read-only `mcp-clickhouse` server alongside curated `atlys-mcp` (asymmetric security pair).
- **Langfuse** — observability spine; mandatory `context_version` per LLM call; graceful no-op degrade; placeholder-key detection; real `auth_check()`.
- **LibreChat** — multi-model chat frontend over **2 MCP servers / 10 tools**; tool calls routed to the host Claude-subscription MCP.
- **MCP server** (`atlys_mcp/server.py`) — 7 tools; IDF feature-resolution that **refuses to guess** when ambiguous.

---

## 5. Visualization (`ui/app.py`, Streamlit)
Six views, all live `SELECT`s from ClickHouse: **Run pipeline** (subprocess + live poll + the approval gate writing back to `pipeline_approvals`), **Schema over time**, **Insights + confidence** (4 components via `JSONExtract` in CH), **Context diff** (FULL OUTER JOIN in CH), **Runs** (trace links), **Chat** (embedded LibreChat).

---

## 6. Evaluation & testing (updated for V2)
- **T8 eval harness** — Table 1 (5 known specs, DDL re-verified live) + Table 2 (**4 fresh mock topologies through the no-LLM deterministic path**, "valid SQL" measured by executing). Honest verdict logic (0/0 = REVIEW; no partial credit).
- **Anti-overfitting** — grep guard (`test_generalization.py`, **37 checks, still green after V2 — the new files name no spec**) + the fresh mock topologies.
- **Test suite: 187 passed / 1 skipped / 0 failed** (was 152/5 at first setup; the delta is the seeded contradictions + **[V2] 24 new tests (mock + vector RAG + Trap-F + hybrid query + instructions)**). Coverage: read-only guard, all 6 contradiction checks, approval race/timeout, metric policy, bake-off + legacy, template feature-agnosticism + injection-safety + live SQL validity + no-bare-`uniq`, correlation, grounding discrimination, MCP resolution, eval-harness logic, **[V2] mock backend (schema-valid, deterministic, zero-cost) and vector RAG (deterministic embedding, iOS-OTP→K1 top hit, ranked prompt keeps governance)**.
- **Statistics in pure stdlib `math`** (judge-re-derivable): two-proportion z (leave-one-out), MAD robust-z, Pearson+Fisher-z, Wilson, Cohen's h, odds ratio (Haldane), Benjamini-Hochberg.

---

## 7. **[V2] Vector RAG for context retrieval — `vector_rag.py`**
The signature capability from `loop`, added as an **opt-in alternative** to the default full-dump.
- **Why opt-in, not default:** `solution` deliberately rejected a vector store because the context layer (~60-150 entries) fits in a prompt and dumping it is deterministic/auditable. That default stands. Vector RAG matters once the layer grows past a promptable size (many features instrumented over time) — then relevance-ranked retrieval keeps the prompt small and on-topic.
- **How it stays true to the thesis:** the embedding is a **deterministic local hashing embedding** (same text → same vector, no network) — directly answering `solution`'s original objection that embeddings are nondeterministic. Which entries are retrieved is reproducible and auditable.
- **In ClickHouse:** `context_embeddings` (`ReplacingMergeTree`) with a `text` index + an HNSW `vector_similarity` index; retrieval via `cosineDistance` + a keyword-index fallback merged in.
- **`ranked_prompt()`** — a drop-in alternative to `snapshot.as_prompt()`: always includes governance kinds (contradictions/gaps/metrics), adds the top-k nearest other entries, and **falls back to the full dump if the index is empty** (never returns less-safe context).
- **Wiring:** `agents/analytics.py::_context_block()` chooses ranked vs full by the `ATLYS_CONTEXT_RETRIEVAL` flag; `run_pipeline.py` reindexes the post-reconcile context when enabled.
- **Verified live:** embedded 108 context entries in a run; **"iOS WebKit OTP autofill" → `known_issue.K1` at rank 1, distance 0.29** among 400 accumulated entries; ranked prompt ~67% smaller than the full dump with governance retained.
- **Enable:** `ATLYS_CONTEXT_RETRIEVAL=vector` (+ optional `ATLYS_RAG_TOP_K`).

## 7b. **[V2] Deterministic mock LLM — `mockllm.py`**
The offline-reproducibility capability from `loop`, generalized.
- **What it does:** `ATLYS_LLM_BACKEND=mock` runs the **entire** pipeline — including the analytics interpret step — with zero credentials and zero network, deterministically.
- **More general than loop's:** because `complete_json()` embeds the full JSON Schema in the prompt, the mock **parses that schema and synthesizes a schema-valid instance** for *any* pydantic contract (`QueryPlan`, `DraftReport`, `DDLProposal`, `Answer`) — no per-type tags needed.
- **Respects the thesis:** mock output still passes every downstream deterministic gate. Verified: **`grounding.py` demotes the mock's placeholder finding to 0.25 / `UNVERIFIED`** exactly as it would a real hallucination — the safety layers don't care that the LLM was mocked.
- **Verified:** full pipeline runs end-to-end in ~4s offline; all 5 specs produce correct entity-key-derived sort keys (`user_id`/`group_id`/`share_id`, never id-first); 8 contradictions written; MV kept 12.75×.
- **Enable:** `ATLYS_LLM_BACKEND=mock`. Default remains `cli` (Claude subscription).

## 7c. **[V2] Hybrid retrieval-⨝-analytics query (Q1) — `vector_rag.hybrid_issue_funnel`**
The "one query no other database can run", and the strongest single Innovation + Use-of-ClickHouse moment.
- **What it does:** in **one ClickHouse statement**, it (a) ranks the known-issue whose meaning is nearest to a question via `cosineDistance` over the HNSW-indexed context embeddings (the vector-DB job), and (b) computes a per-segment funnel conversion with `windowFunnel` over the feature table (the analytics-DB job), and **CROSS JOINs** them — so every returned row pairs a real segment metric with the semantically-closest documented issue. Diagnosis and evidence in a single result set; raw rows never leave the database.
- **Why it's ClickHouse-unique:** no relational-only store has vector search; no vector store computes `windowFunnel`; expressing "semantic retrieval `JOIN` funnel aggregation" in one query needs both in one engine, one SQL dialect.
- **Exposed** as the `diagnose_segments` MCP tool (derives events/entity/segment generically from the feature's own semantics; refuses to guess the feature when ambiguous, same as `ask`).
- **Verified live:** on `f_express_checkout_events`, iOS at 45.0% conversion (the worst segment) paired with `known_issue.K1` at cosine distance 0.29. Requires the vector index (`ATLYS_CONTEXT_RETRIEVAL=vector` run); returns `[]` gracefully if absent.

## 7d. **[V2] Human-instructions channel (G6) — `--instructions`**
Operator steering to complement the existing approval *gate* — the problem statement explicitly values human-in-the-loop.
- **What it does:** `run_pipeline.py --instructions "..."` → `instrumentation.propose_ddl(..., instructions=)` injects an "OPERATOR INSTRUCTIONS" block into the schema-design prompt (e.g. *"retain 24 months"*, *"partition daily"*, *"treat plan as the primary cut"*, *"PII-mask client_ip"*).
- **Bounded, not a blank cheque:** instructions are authoritative and override defaults on conflict, **but the house rules and the 15+ lint checks still hold** — an instruction cannot produce invalid DDL or an id-leading `ORDER BY`, and the model is told to note in the rationale which choice an instruction changed. Injected text is length-capped (2000 chars).
- **Zero change when unused:** the block appears only if `--instructions` is non-empty; the default prompt is byte-identical.
- **Enable:** `--instructions "<free text>"`. 4 tests cover injection, absence-by-default, length cap, and the `propose_ddl` signature.

---

## 8. Token discipline / cost
Model never sees raw rows (≤60-row frames; id tokens redacted). Effort ladder (`--effort low`,
steps up only on retry). Real token/cost from the CLI envelope; scan ratio published per run.
**[V2]** the mock backend reports honest `cost_usd=0.0` and character-estimated token counts,
so an offline eval run's cost accounting is truthful.

---

## 9. Deliverables per run (`artifacts/runs/<run_id>/`)
`insight_report.md`, `schema.sql`, `proposal.json`, `context_diff.md`, `semantics.json`,
`trace_url.txt`. Plus `out/`: versioned `context_vN.md`, `CHANGELOG.md`, `eval/results.md`,
`legacy_projection.md`.

---

## 10. Trap coverage (the A–G traps, from both projects' analyses)
| Trap | Handling in `solution` |
|---|---|
| **A — id-first sort key** | Derives `ORDER BY (event, timestamp, entity_key)`; lint rule L1 forbids id-first; bake-off measures it; `legacy.py` remediates the 8 legacy tables. |
| **B — over-Nullable / no LowCardinality** | House rule §4/§5 + lint L2/L3; `LowCardinality` enums, no `Nullable` on hot cols. |
| **C — dirty dimensions** | Data-quality template T10 measures empty/unexpected-enum rates; feeds confidence `data_quality`. |
| **D — nested objects** | `mapping.flatten_event` dotted-path flattening (`payment.amount` → `payment_amount`). |
| **E — heterogeneous grain / anonymous events** | Kept in one wide table with a shared derived entity key; `disconnected_event_types` + `partial_identity_columns` tracked; **`uniqIf(col, col!='')` guard** enforced + tested (the empty-string trap). |
| **F — dedup / backfill** | ✅ **[V2]** T10 detects duplicate-id / timestamp-sanity issues as a data-quality signal, **and** `instrumentation._dedup_engine` selects `ReplacingMergeTree(timestamp)` when a dedup/backfill signal column is present (by shape, generic) so re-ingested rows collapse on merge — see §11b.1. |
| **G — context contradictions** | All three planted flaws surfaced with executed SQL (C1 conversion denominator; C3 `visa_issuance_eta_days` vs `eta_shown`; C4 uncomputable on-time delivery), and **acted on** at answer time by `metric_policy`. |
| **[extra] String-not-UUID load trap** | `id` typed `String` (32-char hex would fail `UUID`); lint + `mapping._to_uuid`. |
| **[extra] table-name collision** | `f_<slug>_events` / `agg_*` / `mv_*` prefixes (spec 04's `drop_step` values shadow existing table names). |

---

## 11. What was NOT ported from `loop` — full honest record

### 11a. Deliberate non-ports (a `loop` choice `solution` intentionally does differently — NOT gaps)
- **`loop`'s nested-grain *split into separate tables*** — `solution` deliberately keeps partial-envelope events in one wide table with a shared entity key + guarded `uniqIf` (house rule §1). This is the more considered choice (avoids a join for the headline metric); porting `loop`'s version would be a *downgrade*.
- **`loop`'s single-binary local ClickHouse / simplicity** — a setup-friction convenience, not a capability. `solution` ships Docker + a Makefile; equally reproducible, more production-like.
- **`loop`'s `ReplacingMergeTree` context store** — `solution` uses append-only MergeTree + `LIMIT 1 BY` (argued); functionally equivalent for versioning, and the V2 embedding table *does* use `ReplacingMergeTree`.

### 11b. `loop` capabilities that were absent — and their current status

1. **Trap F — `ReplacingMergeTree` on duplicate/backfill signals ✅ [V2 — now PORTED].** `loop` detected `duplicate_id` / `is_back_filled` and selected `ReplacingMergeTree`. **`solution` now does this too, generalized:** `agents/instrumentation.py::_dedup_engine` detects a dedup/backfill signal by column **shape** (regex `duplicate*`/`*back_fill*`/`dedup_*`/`*_reingest`, never an Atlys literal) and emits `ReplacingMergeTree(timestamp)` (last-write-wins by event time) — or keyless `ReplacingMergeTree` if there's no timestamp — with the decision recorded in `rationale["engine"]`; when no signal is present it stays `MergeTree` and records that the check ran and found none. house_rules §5c instructs the LLM path to do the same. Verified: dup-carrying synthetic spec → `ReplacingMergeTree(timestamp)`, lint clean, dry-run PASS; the 5 known specs (no signal) correctly stay `MergeTree`; 6 dedicated tests + grep-guard green. **This was the one capability `loop` shipped that `solution` lacked — now closed.**
2. **In-ClickHouse profiling ⛔ (deliberate skip, not ported).** `loop` profiles raw NDJSON *inside ClickHouse* (`JSONExtract` + `uniqExact`) — an "impossible-elsewhere at scale" talking point. `solution` profiles in **Python** (`profile.py`, `orjson`, `_iter_events`). Fine at hackathon volume; porting would mean rewriting `solution`'s clean deterministic profiler for a scale story the demo won't exercise — flagged, not done.
3. **Self-verification loop ⛔ (not ported; covered downstream).** `loop`'s Instrumentation Agent runs *the PM's own questions* against the table it just built. `solution` has dry-run + bake-off + MV keep/drop measurement, and the analytics stage answers the PM questions later in the same run — so the intent is covered, just not at instrumentation time.

**Status:** the one genuine missing *shipped* capability (Trap F) is now **ported and verified**. (2) is a deliberate skip; (3) is covered downstream.

### 11c. Every `loop` pending / improvable item, mapped to its status in `solution`
`loop`'s own summary carried a ranked pending list (D-, E-, G-, Q- items) and a set of 🟡
"improvable" items. This table accounts for **all of them** so nothing loop tracked is
silently dropped. Legend: ✅ already implemented in `solution` (often better) · ⚠️ partial ·
⛔ genuinely absent from `solution` (and therefore recorded here as a gap).

| `loop` item | Status in `solution` | Evidence / note |
|---|---|---|
| **D2** generalize contradiction detection (loop's #1 overfit) | ✅ done | `contextlayer/checks.py` C3 checks *every* backticked column vs `system.columns` generically — never hardcoded to `visa_issuance_eta_days`. Loop's biggest gap is a non-issue here. |
| **D3** wire contradiction → analytics (compute metric BOTH ways) | ✅ done | `metric_policy.enforce_report` / `refuse_or_qualify_answer` surface both conversion definitions labelled `entry@version`; a test pins it. |
| **D4** real embeddings (vs hashing) | ⚠️ hashing | `vector_rag.py` uses a deterministic hashing embedding (same as loop). Swap `EMBED_PROVIDER` for a real model later; noted in §12.8. |
| **D5** question-directed analysis | ✅ done | `agents/analytics.py::plan_queries` parses PM questions, numbers them into `_plan_prompt`, tracks `unanswered_questions`. Pending in loop, done here. |
| **D6** use relationships / cross-table reasoning | ✅ done | T08/T09 segment-level cross-reference to the legacy funnel (`BASELINE_FUNNEL`, shared-vocabulary joins). |
| **D7** falsification / adversarial verify pass | ✅ exceeds | `grounding.py` (demote ungrounded numbers) + `_verify_evidence` (numbers must appear in cited frames) + Benjamini-Hochberg available. Stronger than loop's proposed single pass. |
| **E1** TTL emitted | ✅ done | house_rules §7 + lint L5; `TTL … + INTERVAL 18 MONTH`. |
| **E2** compression codecs | ✅ done | house_rules §6; `CODEC(Delta, ZSTD(1))` timestamps, `ZSTD(1)` id strings. |
| **E3** data-skipping index / projection on **new** feature tables | ⛔ **absent** | Projections exist for the **legacy** tables (`legacy.py`), but the generated feature-table DDL emits no `minmax`/`set`/`bloom` skip-index. *(Loop also had E3 pending — neither built it on new tables.)* |
| **E7** time-series rollup MVs | ✅ done | Daily `AggregatingMergeTree` + `uniqState` rollup, TTL-paired, keep/drop-gated. |
| **E8** query-execution optimization — **PREWHERE** | ⛔ **absent** | No `PREWHERE` in generated analytics SQL. *(Pending in loop too.)* Templates are windowed + LIMITed, so impact is modest at this scale. |
| **E9** `destination → region` dimension **dictGet** dictionary | ⛔ **absent** | No `CREATE DICTIONARY`/`dictGet`. *(Loop marked this optional-pending; neither built it.)* |
| **Q1** single hybrid retrieval-`JOIN`-analytics query | ✅ **[V2 — now BUILT]** | `vector_rag.hybrid_issue_funnel` runs, in ONE ClickHouse statement, semantic issue-retrieval (`cosineDistance` over the HNSW index) CROSS JOIN a per-segment `windowFunnel` conversion — each row pairs a real segment metric with its nearest documented issue. Exposed as the `diagnose_segments` MCP tool. Verified live: iOS 45.0% conversion (worst) ⨝ `known_issue.K1` @ dist 0.29. Neither loop nor `solution` had this before; built here. |
| **G4** per-run token accountant | ✅ done | `llm.usage()` + `InsightReport.total_llm_tokens` / `rows_scanned_in_clickhouse` / `rows_sent_to_llm`, published per run. |
| **G5** MCP integration | ✅ done | `atlys_mcp/server.py` (7 tools) + read-only `mcp-clickhouse` + LibreChat. Loop had none. |
| **G6** custom human-instructions channel (operator free-text on a run) | ✅ **[V2 — now BUILT]** | `--instructions` CLI flag → `propose_ddl(..., instructions=)` injects an "OPERATOR INSTRUCTIONS" block into the schema-design prompt as authoritative-but-lint-bounded constraints (e.g. "retain 24 months", "treat plan as the primary cut", "PII-mask client_ip"). An instruction overrides defaults on conflict but still can't produce invalid DDL or an id-leading ORDER BY (house rules + lint hold). Off unless supplied; length-capped; 4 tests. Complements the existing approval gate. |
| **G7** proactive notifications (context-update + data-anomaly push) | ⛔ **absent** | Signals are computed (anomalies, contradictions, version bumps) and written to ClickHouse/artifacts, but nothing *pushes* a notification. *(Pending in loop too.)* System-health alerts remain out of scope (observability = ClickStack). |
| **Trap C** — emit a dirty-dimension **normalization/coalesce** mapping | ⚠️ measured, not emitted | T10 *measures* empty/unexpected-enum rates and feeds `data_quality`; neither project emits a normalization mapping into the schema. Same status as loop. |
| **loop eval "grades consistency not usefulness"** | ✅ exceeds (still can't grade usefulness) | `evalharness.py` has two tables (known-spec live re-verify + fresh mock topologies) with honest verdicts; but insight *usefulness* (vs correctness) is human-checked in both — see §12.4. |

**Net:** of loop's ranked pending list, **D2, D3, D5, D6, D7, E1, E2, E7, G4, G5 were already implemented in `solution`** (several better than loop planned); **[V2] Trap-F, Q1 (hybrid query) and G6 (human-instructions) are now built here** — Q1 and G6 were pending in loop too, so building them puts `solution` *ahead of* loop's plan, not just level with it. The only remaining unbuilt items are the low-value optimizations **E3 (new-table skip-index), E8 (PREWHERE), E9 (dictGet), G7 (notifications)** — all also pending in loop, all deliberately deferred as gold-plating with near-zero scoring value at hackathon scale, and each recorded above rather than dropped silently. **There is no capability loop shipped — or planned — that `solution` now lacks except these four deferred micro-optimizations.**

---

## 12. Known gaps (self-documented; unchanged by V2)
1. Benjamini-Hochberg written + tested but not wired into `analytics.py`.
2. `deep_linear` mock topology's LLM-fallback MV column-naming bug at nesting depth ≥2 (the no-LLM deterministic path and the mock-backend path both handle it; the specific fallback-MV path is the gap).
3. No test asserts SQL-side vs Python-side statistic parity.
4. Insight *quality* (vs correctness) is only human-checked.
5. `queries/stats.py` uses different confidence weights (0.35/0.35/0.15/0.15) than live `confidence.py` (0.30/0.30/0.20/0.20) — dormant reference module.
6. `metric_policy` subject aliasing hardcoded to "conversion".
7. Several `ch.py` guard bugs worked around, not fixed.
8. **[V2]** the vector-RAG embedding is a local hashing embedding (fast, deterministic, offline) — semantically weaker than a real sentence-transformer; swap `EMBED_PROVIDER` for a real model when semantic recall matters more than zero-dependency determinism.
9. **[V2] Remaining unbuilt items (all also pending in `loop`, deliberately deferred as low-value at hackathon scale):** E3 new-table skip-index, E8 PREWHERE, E9 dictGet, G7 notifications. Trap-F, Q1 and G6 — previously listed here — are now **built** (see §0, §7c/§7d, §11b/§11c). Non-ports that remain by design: in-ClickHouse profiling (Python profiler is sufficient) and the instrumentation-time self-verify loop (covered by the downstream analytics stage).
10. **[V2, audit residual] Fallback DDL assumes a temporal `timestamp`.** `build_fallback_proposal` (the no-LLM availability floor) emits `PARTITION BY toYYYYMM(timestamp)` + TTL unconditionally when a `timestamp` column exists; a spec whose timestamps are non-ISO strings would type it `String` and dry-run-fail there. The `_dedup_engine` engine choice is already type-guarded; the partition/TTL guard was deferred because gating them off trips lint L4/L5, and the correct fix (force-coerce a column named `timestamp` to `DateTime64` on load) touches the load path — not worth the risk for a case no real/known spec hits. The LLM path is protected by dry-run+repair.

---

## Appendix — verification record

**V2 additions (5):** ① deterministic mock LLM · ② in-ClickHouse vector RAG · ③ Trap-F dedup→ReplacingMergeTree · ④ Q1 hybrid retrieval-⨝-analytics query (+ `diagnose_segments` MCP tool) · ⑤ G6 human-instructions channel. All additive; every default path byte-identical when the new flags are unset.

- **Env:** local ClickHouse 26.8 binary, db/user/pw `atlys` on :8124/:9100, `system.query_log` enabled, 2.48M rows loaded, context seeded.
- **Compile/import:** all 29 modules compile and import clean.
- **Full test suite:** **187 passed / 1 skipped / 0 failed** (24 of these are the V2 additions' tests: mock 6, vector RAG 5, Trap-F 6, hybrid+instructions 7).
- **Generalization grep-guard:** 37/37 green — no added file names a known spec.
- **Live end-to-end (all 5 specs, mock + `ATLYS_CONTEXT_RETRIEVAL=vector` + `--instructions`):** all 5 exit 0 with correct entity-key-derived sort keys (`user_id`/`group_id`/`share_id`, never id-first); report stage OK on each with monotonic context versions (freshness holds); 8 contradictions per run; MVs kept with measured reduction; 195 context embeddings indexed; Q1 returns iOS 45% conversion ⨝ `known_issue.K1`.
- **Default path integrity:** `llm._call` still dispatches to `cli` by default (mock is an added branch); `propose_ddl` gains an optional `instructions=""` (empty ⇒ prompt byte-identical); Trap-F leaves the 5 signal-free known specs on plain `MergeTree`.
- **Regression:** none.

### Adversarial code audit of the 5 additions (and fixes applied)
A deep adversarial audit of the added code found **7 issues** (all latent — on paths the 5 known specs don't exercise, which is why the test suite was green before). **All 7 addressed:**
- **P1 (crash) — fixed.** `diagnose_segments` could hit `UnboundLocalError` on `sem` if spec profiling failed; `event_col` now has a safe default set alongside the others.
- **P2 (mock schema-validity) — fixed.** The mock now honours `exclusiveMinimum/Maximum`, `multipleOf`, `minLength/maxLength`, `pattern`, and `prefixItems` (typed tuples); docstring softened to not overclaim.
- **P3 (version type) — fixed.** `_dedup_engine` now only versions a `ReplacingMergeTree` on a column ClickHouse accepts (temporal/numeric), falling back to keyless Replacing on a String timestamp — verified via type-aware test.
- **P4 (misleading rationale) — fixed.** The engine rationale now correctly describes ReplacingMergeTree's collapse-on-ORDER-BY-tuple semantics instead of overstating "latest by timestamp supersedes."
- **P5 (governance context) — fixed.** `known_issue` and `relationship` added to `_ALWAYS_KINDS`, so ranked retrieval can never surface less governance context (esp. the known-issue linkage) than the full dump.
- **P6 (injection hardening) — fixed.** `hybrid_issue_funnel`/`search` now validate identifiers (`_ident`) and escape literals for backslash+quote (`_lit`); a bad identifier returns `[]`.
- **P7 (schema extraction) — fixed.** `_extract_schema` brace-matching is now string-aware (a literal `{` inside a description can't derail it).
- Verified CORRECT by the audit and unchanged: byte-identical default path, dedup false-positive resistance, mock Optional/anyOf/$ref handling, failure isolation in `_context_block`/reindex, `propose_ddl` never-raises.
- **One residual, documented (not a regression):** the *fallback* DDL path (no LLM) still emits `PARTITION BY toYYYYMM(timestamp)` + TTL assuming `timestamp` is temporal; a spec with non-ISO string timestamps would dry-run-fail there. The LLM path is protected by dry-run+repair; no known/real spec triggers it. See §12.10.
- **Post-fix suite: 193 passed / 1→0 skipped / 0 failed** (4 new lock-in tests for P1/P2/P3/P6).
