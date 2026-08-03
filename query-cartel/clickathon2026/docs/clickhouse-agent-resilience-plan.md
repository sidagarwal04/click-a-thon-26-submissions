# ClickHouse Agent Resilience Plan

> **Status:** Living plan for making Atlys Copilot’s Instrumentation / Context / Analytics agents
> safe and correct across ClickHouse versions, data shapes, scale, errors, and schema lifecycle.
>
> **Audience:** Implementers of the FastAPI pipeline (`Atlys/service/**`).
>
> **Relationship to ENGINEERING.md:** ENGINEERING.md remains the product SoT (D1–D14, event bus,
> agents, judging). This doc owns the **ClickHouse operational contract** that ENGINEERING §3
> sketches but the code only partially implements. Where they conflict, prefer this doc for
> migration / safety behavior, and update ENGINEERING §3.4 after the corresponding milestone lands.
>
> **MVP north star (hackathon):** Spec → approved schema → load → context → insight, traced,
> robust on the unseen Day-2 spec. Production-grade CH ops are staged so they **protect the demo
> path first**, then deepen.

---

## 0. Current state (as of this plan)

| Area | ENGINEERING intent | Code today | Risk to MVP |
|---|---|---|---|
| Schema create | `CREATE TABLE IF NOT EXISTS` | Implemented | Low |
| Schema evolution | Additive `ADD COLUMN` / widen-only | **DROP + recreate** on any drift (`instrumentation._ensure_schema`) | Medium — destroys data; OK for synthetic specs, wrong message for “production schema” |
| Types | bool/int/float/String + LowCardinality | Implemented; arrays → JSON String; no Array/Map/JSON/Decimal/UUID/DateTime64 | Medium for Day-2 weird shapes |
| Idempotent re-run | Skip reload when schema+rows match | Partial for feature tables; `meta.*` appends duplicates; funnel loaders can duplicate | Medium |
| Mutations | — | `mutations_sync=1` on `pending_runs` UPDATE only | Low for demo size; High if scaled |
| Error handling | Loud empty NDJSON; String fallback | Broad `except Exception` + 3 retries; no CH error taxonomy | Medium |
| Huge tables | MV rollups “earn their keep” | Funnel MV bootstrapped; playbook still scans raw; P6 dumps per-user rows | Medium at 2.5M; High if larger |
| Feature retirement | — | None (hard DROP only on drift rebuild) | Low for hackathon |
| Multi-version CH | — | Assumes one ClickHouse Cloud service | Low for demo; High if judges/local differ |
| Docs grounding | Static rules in `schema.py` | No version-aware docs retrieval | Low for MVP; needed for defensible rationale |

**Key files:** `schema.py`, `agents/instrumentation.py`, `store.py`, `agents/mv.py`,
`agents/analytics.py`, `app.py` (DDL bootstrap), `data/ddl.sql`, `data/load_python.py`.

---

## 1. Design principles (locked for this plan)

1. **Deterministic-first (D6).** Schema, migration plan, and error classification are Python rules —
   not LLM guesses. LibreChat narrates; FastAPI decides.
2. **Human gate (D10).** Every mutating plan (`CREATE` / `ALTER` / deferred `DROP`) ships as a
   schema card → `approve_schema` before execution.
3. **Additive by default.** Prefer `ADD COLUMN IF NOT EXISTS` and widen-only type changes.
   Destructive ops require an explicit `rebuild` or `retire` action in the card.
4. **Idempotency in state, not in the log.** `event_log` is append-only (at-least-once). Safety
   lives in migration journals + `IF NOT EXISTS` / content hashes / row-count gates.
5. **Fail loud, classify, don’t invent.** Unknown types → documented fallback + rationale.
   Unknown CH errors → surface code + message in evidence/trace; retry only when classified safe.
6. **MVP slice first.** Anything that does not change Day-2 unseen-spec success or demo reliability
   is P2/P3 unless it unblocks a P0/P1 item.

---

## 2. Capability areas

### 2.1 ClickHouse version matrix

**Problem.** DDL/settings differ across OSS 23.x–25.x and ClickHouse Cloud. Features like
`JSON` type, `Variant`/`Dynamic`, certain `ALTER` behaviors, and default settings drift.

**Target behavior**

| Concern | Behavior |
|---|---|
| Detection | On connect: `SELECT version()`, `SELECT cloudMode` / settings snapshot → `meta.ch_capabilities` (or in-memory CapabilityProfile) |
| Feature gates | Capability flags: `supports_json_type`, `supports_add_column_if_not_exists`, `supports_lightweight_delete`, `max_mutation_timeout_default`, etc. |
| DDL emission | `schema.py` / migration planner pick the **safest dialect** for the live profile; never emit Cloud-only syntax against local OSS without a gate |
| Rationale | Schema card includes `clickhouse_version` + which rule path was chosen |
| Docs | Map profile → pinned doc set (see §2.2) |

**MVP minimum:** Detect version once at bootstrap; log it on every run; refuse unsupported engines
with a clear error (do not silently emit broken DDL).

**Stretch:** Capability matrix table + unit tests that stub profiles (23.8 / 24.8 / Cloud).

---

### 2.2 Documentation grounding

**Problem.** Schema rationale today is hardcoded prose. Judges (and Day-2) reward *why* ORDER BY /
partition / types. Version-aware docs keep rationale honest when rules change.

**Target behavior**

| Layer | What | Who uses it |
|---|---|---|
| **Static rulebook** (shipped in repo) | `docs/clickhouse-schema-rules.md` — our locked decision table (ORDER BY, partition, TTL, LowCardinality, Nullable honesty) | Instrumentation always |
| **Version pin** | `CLICKHOUSE_DOCS_PIN` env (e.g. `24.8`) + short excerpts for ALTER semantics, MergeTree keys, mutation settings | Migration planner |
| **Retrieval (optional)** | Offline snippet index keyed by topic (`alter_add_column`, `mutations_sync`, `ttl`, `array_type`) — **not** live web crawl in the demo path | Rationale enrichment |
| **Context agent** | When CH version or schema rules change, append a context changelog finding | Context |

**MVP minimum:** Extract the ENGINEERING §3.2 table into a single rulebook file the agent cites by
id (`R-ORDER-BY-01`, …) in the schema card. No live web dependency for the judged path.

**Do not:** Block schema proposal on external doc fetch.

---

### 2.3 Data types

**Problem.** Day-2 unseen specs may include arrays, nested objects, decimals, timestamps with ms,
UUIDs, mixed nullability, heterogeneous columns across events.

**Inference ladder** (deterministic, ordered):

```
null-only           → String (document “all-null; widen later”)
bool                → UInt8
uint by magnitude   → UInt8 / UInt16 / UInt32 / UInt64
signed int          → Int32 / Int64 (if negatives appear)
float / money       → Float64  (MVP); Decimal(P,S) when all values parse as fixed-scale
datetime-like str   → DateTime or DateTime64(3) if fractional seconds
uuid-like str       → String (MVP, matches existing funnel); UUID only if capability + all valid
enum-ish string     → LowCardinality(String) if distinct/total ≤ threshold
list of scalars     → Array(T) if homogeneous + capability; else String(JSON)
list of objects     → String(JSON) (MVP); nested/JSON type only behind capability gate
map-like            → String(JSON) (MVP); Map(K,V) behind gate
mixed scalar types  → String (never silent cast that loses data)
```

**Nullability:** `Nullable` only when nulls observed **or** column absent on some event types in
the same table (discriminator-aware). Envelope non-nullables stay non-null (`id`, `timestamp`,
`event`, `user_id`) — if `user_id` missing, use empty string bucket (ENGINEERING risk matrix), not
Nullable in ORDER BY.

**Widen-only graph (for ALTER):**

```
UInt8 → UInt16 → UInt32 → UInt64
Int32 → Int64
Float32 → Float64
T → Nullable(T)
String stays String (no “upgrade” to LowCardinality on existing data without rebuild plan)
LowCardinality(T) → T  (allowed; reverse needs rebuild)
```

Narrowing / rename / drop column → **not** auto-ALTER; propose `rebuild` or leave unused column
(deferred removal, §2.7).

**Todos:** type matrix tests (`tests/test_schema.py` expand); fixture NDJSON for arrays / mixed /
ms timestamps / missing user_id.

---

### 2.4 Huge tables & query scale

**Problem.** ~2.5M funnel rows already; feature tables grow; analytics P6 and raw scans timeout
(`send_receive_timeout=60`). Inserts batch 1000 with no backpressure.

**Strategies (layer cake)**

| Layer | Tactic | When |
|---|---|---|
| **Schema** | Correct ORDER BY + monthly partition + TTL 180d | Always |
| **Ingest** | Adaptive batch (1k→10k), optional async insert settings when capability allows | Feature load > 50k rows |
| **Skip** | If `matched && row_count >= expected` → no re-insert | Already partial |
| **MV** | Wire `create_feature_rollup` into approve path when event_order length ≥ 2 | P1 |
| **Analytics** | Prefer MV / `uniqMerge` for P1–P3; cap P6 with `LIMIT` + sampling; never dump unbounded per-user | P0/P1 |
| **Timeouts** | Per-query class: interactive 30s, analytics 120s, DDL/mutation poll separate | P1 |
| **Progress** | Emit `schema.load.progress` events (rows inserted / total) for chat UX | P2 |

**Hard limits for MVP demo**

- Refuse playbook queries estimated to scan > N partitions without a time filter (log + degrade
  confidence).
- On timeout: record `{error, code, classified_as: timeout}` in evidence; continue other playbook
  steps (already partially true).

---

### 2.5 Error taxonomy

**Problem.** All failures look the same; retries may worsen mutation pile-ups; insights hide root cause.

**Classification model** (`store.py` + thin `ch_errors.py`):

| Class | Examples (CH codes / patterns) | Retry? | Agent action |
|---|---|---|---|
| `transient_network` | connection reset, timeout before server | Yes (bounded) | Retry with backoff |
| `timeout_query` | receive timeout, `TIMEOUT_EXCEEDED` | No auto-retry of same SQL | Shorten / sample / use MV; record evidence error |
| `unknown_table` / `unknown_column` | 60, 47 | No | Context/schema reconcile finding |
| `type_mismatch` | 53, insert type errors | No | Trigger schema drift plan (additive or rebuild) |
| `readonly` / `auth` | 164, 497 | No | Abort run; loud chat message |
| `quota` / `memory` | 241, 252 | Maybe once with lighter query | Degrade playbook step |
| `mutation_stuck` | long-running `system.mutations` `is_done=0` | N/A | See §2.8 |
| `duplicate_insert` | — (app-level) | N/A | Idempotency gate |
| `syntax` / `unsupported` | 62, capability miss | No | Fix DDL via capability profile |
| `unknown` | everything else | No (unless explicitly marked) | Surface raw message + code in Langfuse |

**Contract:** Every failed `query`/`command`/`insert` returns a structured
`ClickHouseOpError(class, code, message, sql_digest, retryable)`. Analytics evidence and
instrumentation spans store the class, not just `str(e)`.

---

### 2.6 Choosing the right schema

**Problem.** One rigid template wins most funnel specs but can be wrong for sparse additive events,
high-cardinality user filters, or non-time-series shapes.

**Decision procedure** (emit in schema card `rationale` + `schema_strategy`):

```
IF events look like a mini-funnel (≥2 event types, shared user_id, time-ordered)
  → strategy = funnel_events
  → ORDER BY (event, timestamp, user_id)
  → PARTITION BY toYYYYMM(timestamp)
  → consider feature rollup MV

ELSE IF single event type, high volume append
  → strategy = append_log
  → ORDER BY (timestamp, user_id)  or (user_id, timestamp) if user-centric queries dominate
  → same monthly partition + TTL

ELSE IF no reliable timestamp
  → strategy = degenerate
  → ORDER BY tuple of available keys; loud rationale; analytics confidence capped

ALWAYS
  → MergeTree (MVP); no Replacing/Collapsing unless spec proves need + human approves
  → TTL 180 DAY default (override only via explicit spec hint later)
  → one table `<feature>_events` (D-locked for hackathon)
```

**Judging alignment:** Prefer explainable defaults over exotic engines. Document rejected
alternatives briefly (`why_not_order_by_user_first`) when inference considered them.

**Gap to close vs ENGINEERING §3.4:** Implement additive evolution so “choosing right schema”
includes **evolution plan**, not only first CREATE.

---

### 2.7 Deferred removal (old features / columns)

**Problem.** Hard `DROP TABLE` / drop-column is irreversible and blocks if mutations pending.
“Prefer deferred removal” means soft-retire first, hard-delete later.

**Lifecycle for a feature table**

```
active ──(retire requested)──► retiring ──(TTL / grace elapsed)──► dropped
                │
                └── catalog: status=retired, retired_at, drop_after
```

| Step | Action | Notes |
|---|---|---|
| Soft retire | `meta.schema_catalog` mark `status=retired`; stop new analytics playbooks from selecting it by default | Context agent changelog `retire` |
| Detach dependents | Drop / detach feature MVs first | Avoid orphan MVs |
| Optional TTL tighten | `ALTER … MODIFY TTL timestamp + INTERVAL 7 DAY` to drain data | Capability-aware |
| Hard drop | `DROP TABLE IF EXISTS` only after `drop_after` and no open runs | Requires approval card `action=hard_drop` |
| Columns | Never `DROP COLUMN` in MVP auto-path; leave unused columns; rebuild only if approved | Matches additive philosophy |

**MVP:** Implement catalog `status` + context “retired feature” finding. Hard drop can remain
manual/ops. Drift path must **stop** using silent DROP+recreate as the default evolution tool
(replace with additive plan; rebuild only when widen graph cannot reconcile).

---

### 2.8 Migrations that must not get stuck

**Problem.** ClickHouse `ALTER UPDATE/DELETE` are mutations; `mutations_sync=1` can block the
request until done — fine for tiny `pending_runs`, dangerous for large tables.

**Rules**

1. **Never** run heavyweight mutations (`UPDATE`/`DELETE` on large feature/funnel tables) in the
   request path of `approve_schema`.
2. Prefer **DDL that is metadata-light**: `ADD COLUMN IF NOT EXISTS` (usually fast), `CREATE`,
   `DROP` of empty/small tables.
3. For state machines (`pending_runs`), keep rows tiny **or** replace mutation with
   **append-only state** + `argMax(state, created_at)` read (avoids mutations entirely) — preferred
   long-term.
4. If a mutation is unavoidable:
   - Submit **without** `mutations_sync=1` on large tables
   - Poll `system.mutations` with timeout budget (e.g. 30s demo / configurable)
   - On timeout: mark run `migration_pending`, emit event, return chat-visible status; **do not**
     hold MCP tool call for minutes
5. Stuck detection: `is_done=0` AND `latest_fail_reason != ''` OR age > budget → classify
   `mutation_stuck`; offer `KILL MUTATION` only behind explicit human approval tool
6. Concurrent migrations: one mutating plan per `table_name` (lock row in `meta.migration_journal`)

---

### 2.9 Running the same migration twice (idempotency)

**Problem.** At-least-once bus + double approve + re-run loaders create duplicates.

**Migration journal** (`meta.migration_journal` — new):

```sql
CREATE TABLE IF NOT EXISTS meta.migration_journal (
    migration_id String,          -- hash(plan_canonical_json)
    table_name String,
    action LowCardinality(String), -- create_table|add_column|widen_type|rebuild|retire|hard_drop|load_snapshot
    plan_hash String,
    status LowCardinality(String), -- planned|approved|applied|skipped_idempotent|failed
    run_id String,
    trace_id String,
    error String,
    created_at DateTime DEFAULT now(),
    applied_at Nullable(DateTime)
) ENGINE = MergeTree ORDER BY (table_name, migration_id, created_at);
```

**Idempotency keys**

| Operation | Key | Second execution |
|---|---|---|
| CREATE TABLE | `table_name` + ddl hash | `IF NOT EXISTS` → `skipped_idempotent` |
| ADD COLUMN | `table + column + type` | `IF NOT EXISTS` / live columns match → skip |
| Widen type | `table + column + from→to` | Live already ≥ target → skip |
| LOAD snapshot | `table + content_hash(events) + row_count` | If rows ≥ expected and hash recorded → skip |
| Catalog upsert | Use `ReplacingMergeTree` **or** delete+insert pattern via journal, not blind append | Latest wins for readers |
| Approve gate | `run_id` state ≠ `proposed` → ignore (already implemented) | Keep |

**Canonical plan hashing:** Sort columns, normalize types, ignore ephemeral fields. Same plan
bytes → same `migration_id`.

**Funnel loaders:** Make `load_python.py` / `load.sh` check `row_count` or use a staging table +
swap; document “run once” is insufficient for agents.

---

## 3. Target architecture (pipeline additions)

```
spec.ingested
    → SchemaInferencer (types + strategy)
    → MigrationPlanner (diff live vs desired → Plan[])
    → schema.proposed  { schema_card, migration_plan, ch_version, rule_ids }
         ⏸ approve_schema
    → MigrationExecutor (journal + capability gates + timeouts)
         → per step: apply | skip_idempotent | fail(classified)
    → Loader (hash-gated insert, progress events)
    → schema.created
    → Context + Analytics (error-class-aware evidence, MV-preferring SQL)
```

**New / extended modules (suggested)**

| Module | Responsibility |
|---|---|
| `service/ch_capabilities.py` | version → flags |
| `service/ch_errors.py` | classify exceptions |
| `service/migration_plan.py` | diff + widen graph + rebuild detection |
| `service/migration_exec.py` | journal, apply, poll, kill-gate |
| `service/schema.py` | keep inference; call planner for evolution |
| `service/store.py` | typed errors, timeout classes, optional mutation helpers |
| `docs/clickhouse-schema-rules.md` | cited rulebook |

Preserve D6: planner/executor remain pure Python.

---

## 4. Prioritized TODO list

Priorities:

- **P0 — Demo / Day-2 blockers** (do before unseen spec)
- **P1 — Schema quality & correctness judges care about**
- **P2 — Operational hardening** (stuck migrations, retire, scale)
- **P3 — Post-MVP / nice-to-have**

### P0 — Must land for a trustworthy MVP

| ID | Todo | Outcome | Primary files |
|---|---|---|---|
| **P0.1** | Replace silent DROP+recreate default with **additive migration plan** (ADD COLUMN / widen-only); rebuild only when plan says `rebuild` and card shows it | Aligns with ENGINEERING §3.4; no accidental data loss on re-approve | `instrumentation.py`, new `migration_plan.py` |
| **P0.2** | **Idempotent load gate** hardened: schema match + row_count + optional events content hash; double approve never doubles rows | M1 acceptance; safe re-runs | `instrumentation.py` |
| **P0.3** | **ClickHouse error classifier** + store structured errors in analytics evidence / Langfuse spans | Debuggable Day-2 failures | `ch_errors.py`, `store.py`, `analytics.py` |
| **P0.4** | Expand **type inference fixtures** for arrays, mixed types, missing `user_id`, fractional timestamps, nested objects | Unseen-spec robustness | `schema.py`, `tests/test_schema.py`, fake fixtures |
| **P0.5** | Analytics **timeout / scan safety**: cap P6; continue playbook on step failure; prefer existing `mv_funnel_daily` where applicable | Avoid 60s hung demo | `analytics.py`, `mv.py` |
| **P0.6** | Bootstrap **version detection** logged on every run (`version()`, host) | Support triage; no dialect surprises | `store.py` / `app.py` |

### P1 — Schema quality & evolution (judging + re-runs)

| ID | Todo | Outcome | Primary files |
|---|---|---|---|
| **P1.1** | Implement `MigrationPlanner` + journal table; record `add_column` / `alter_type` / `create_table` / `rebuild` in `meta.schema_changelog` with real versions | True evolution audit trail | `migration_*.py`, `app.py` DDL |
| **P1.2** | Schema strategy selector (`funnel_events` vs `append_log`) with rationale rule IDs | Better ORDER BY stories | `schema.py` |
| **P1.3** | Wire **per-feature rollup MV** when funnel-like; changelog rationale | “MVs that earn their keep” | `mv.py`, `instrumentation.py` |
| **P1.4** | Ship `docs/clickhouse-schema-rules.md` and cite `R-*` ids from schema cards | Defensible, consistent rationale | `docs/`, `schema.py` |
| **P1.5** | Catalog read path uses **latest row per table_name** (argMax / subquery) so appends don’t confuse agents | Fix meta append ambiguity | instrumentation, context, REST |
| **P1.6** | Replace `pending_runs` `ALTER UPDATE` with **append-only state** + latest-read **or** keep mutation only for tiny rows + document | Avoid mutation dependency for gate | `instrumentation.py`, DDL |
| **P1.7** | Capability flags for `ADD COLUMN IF NOT EXISTS` / JSON / Array; degrade gracefully | Multi-version safety (local vs Cloud) | `ch_capabilities.py` |

### P2 — Scale, stuck migrations, retirement

| ID | Todo | Outcome | Primary files |
|---|---|---|---|
| **P2.1** | Mutation poller + timeout budget + `migration_pending` run state; never block MCP > budget | Migrations don’t “stick” the agent | `migration_exec.py` |
| **P2.2** | `KILL MUTATION` tool behind explicit approval | Escape hatch | MCP + executor |
| **P2.3** | Adaptive insert batching + load progress events | Large NDJSON UX | `store.py`, bus events |
| **P2.4** | Feature **soft-retire** (`status=retired`, context changelog); defer hard DROP | Deferred removal preference | catalog, context agent |
| **P2.5** | Per-query timeout classes; memory/quota degrade path in playbook | Huge-table resilience | `store.py`, `analytics.py` |
| **P2.6** | Funnel loader idempotency (`load_python.py`) | Re-bootstrap safe | `data/load_*.py` |
| **P2.7** | Single-flight lock per `table_name` in journal | No concurrent migrators | `migration_exec.py` |

### P3 — Stretch / post-hackathon

| ID | Todo | Outcome |
|---|---|---|
| **P3.1** | Offline docs snippet index by CH version pin | Richer rationale without live web |
| **P3.2** | Decimal / DateTime64 / Array / Map / JSON type promotion behind flags | Richer schemas |
| **P3.3** | TTL-tighten drain + scheduled hard_drop worker | Full deferred deletion |
| **P3.4** | ReplacingMergeTree / Collapsing only with explicit approve + tests | Advanced engines |
| **P3.5** | Estimate partition scans / `EXPLAIN` before heavy analytics | Cost-aware playbook |
| **P3.6** | Chaos tests: kill mid-migration, double-delivery of `schema.approved` | Proof of idempotency |
| **P3.7** | ClickStack dashboards for mutations / failed queries | Bonus observability (D8) |

---

## 5. Suggested implementation waves

### Wave A — “Safe re-run” (≈ 1 day, P0.1–P0.3, P0.6)

1. Diff live `system.columns` vs card → plan steps.
2. Apply ADD/widen; rebuild only if incompatible.
3. Journal + skip duplicate approve/load.
4. Classify store errors.

**Exit criteria:** Re-approve same spec → no DROP, no duplicate rows, changelog shows
`skipped_idempotent` or no-op. Drift that only adds a column → `ADD COLUMN`, data preserved.

### Wave B — “Day-2 shapes & analytics safety” (P0.4–P0.5, P1.2–P1.3)

1. Fixture battery for weird NDJSON.
2. Cap dangerous playbook steps; use funnel MV.
3. Strategy selector + feature MV when earned.

**Exit criteria:** Fake 6th spec + array-heavy fixture produce schema + insight without hang;
rationale cites rule IDs.

### Wave C — “Ops maturity” (P1.1, P1.5–P1.7, P2.*)

1. Journal DDL in `app.py` bootstrap.
2. Append-only pending state.
3. Mutation timeouts + soft-retire.
4. Capability profile.

**Exit criteria:** Documented runbook for “migration pending” and “retire feature”; double
migration apply is a no-op.

---

## 6. Testing matrix

| Case | Type | Assert |
|---|---|---|
| Fresh CREATE | unit + e2e | Table exists; catalog row; events loaded |
| Re-approve identical | e2e | No DROP; row_count unchanged; journal skip |
| Add new event field in NDJSON | e2e | ADD COLUMN; old rows intact; nulls for old rows |
| Incompatible type change | e2e | Plan=`rebuild` visible in card; only after approve |
| Double `schema.approved` | e2e | Second ignored (state gate) |
| Empty NDJSON | unit | Loud error, traced |
| Array / mixed column | unit | Fallback + rationale |
| Query timeout | unit (mocked) | Class `timeout_query`; playbook continues |
| Mutation exceeds budget | unit | `migration_pending`; no indefinite block |
| Soft retire | unit | Analytics skips retired by default |
| Version gate | unit | Unsupported type → String path + flag |

Keep dry-run store (`DryRunStore`) able to simulate plan apply for offline demos.

---

## 7. Chat / MCP UX contract

Expose (names illustrative):

| Tool | Purpose |
|---|---|
| `propose_schema` / existing run | Returns card **and** `migration_plan[]` |
| `approve_schema` | Executes plan under timeout budget |
| `migration_status` | Journal + `system.mutations` snapshot for `run_id` / table |
| `retire_feature` | Soft-retire proposal (approve-gated) |

LibreChat prompt (`agents/atlys_pm.md`): teach PM to read plan steps (“will ADD COLUMN X,
will NOT drop data”) before approve.

---

## 8. Explicit non-goals (this plan)

- Multi-primary replication / shard planning
- Streaming ingest / Kafka Connect
- Editing application code to emit events (D9)
- Automatic live crawl of clickhouse.com during judged runs
- Full online schema change for ReplicatedMergeTree clusters beyond Cloud single service

---

## 9. Open decisions (resolve before Wave C)

1. **pending_runs:** keep `mutations_sync=1` (simple, OK for tiny table) vs append-only state
   (cleaner ops)? Recommendation: append-only in P1.6.
2. **Rebuild policy:** auto-propose rebuild on incompatible widen, or refuse and ask PM to
   create `_v2` table? Recommendation: propose rebuild in-card for hackathon synthetic data;
   never auto-rebuild without approval.
3. **Unused columns:** always keep (deferred) vs rebuild to compact? Recommendation: keep until
   explicit retire/rebuild.
4. **Docs location:** `docs/` at repo root (this file) vs `Atlys/docs/`? Recommendation: repo
   `docs/` for cross-cutting CH plan; Atlys-specific runbooks can live under `Atlys/docs/` later.

---

## 10. Success metrics

| Metric | Target |
|---|---|
| Identical re-approve duplicate rows | 0 |
| Drift-only-add path uses DROP | 0 |
| Day-2 pipeline completion without manual SQL | 100% of dry-run fixtures |
| Approve tool wall time when mutation needed | ≤ timeout budget (default 30s) then async status |
| Playbook step failure leaves partial insight | Yes, with classified errors |
| Schema card cites ≥1 rule id + CH version | Always |

---

## 11. Quick reference — priority backlog (checklist)

**P0**
- [x] P0.1 Additive migration plan (no default DROP+recreate)
- [x] P0.2 Hardened idempotent load
- [x] P0.3 Error taxonomy in store/analytics
- [x] P0.4 Type inference fixture expansion
- [x] P0.5 Analytics timeout / scan caps + MV use
- [x] P0.6 Version detection at bootstrap

**P1**
- [x] P1.1 Migration journal + real changelog actions/versions
- [ ] P1.2 Schema strategy selector
- [ ] P1.3 Per-feature MV wiring
- [ ] P1.4 Schema rules doc + R-id citations
- [ ] P1.5 Latest-catalog read semantics
- [ ] P1.6 Append-only pending_runs (or documented exception)
- [ ] P1.7 Capability flags

**P2**
- [ ] P2.1 Mutation poll + non-blocking budget
- [ ] P2.2 Approved KILL MUTATION
- [ ] P2.3 Adaptive insert + progress
- [ ] P2.4 Soft-retire deferred removal
- [ ] P2.5 Query timeout classes
- [ ] P2.6 Idempotent funnel loaders
- [ ] P2.7 Per-table migration single-flight

**P3**
- [ ] P3.1–P3.7 Stretch items as time allows

---

*End of plan. Next concrete step when implementing: Wave A starting at P0.1 against
`Atlys/service/agents/instrumentation.py::_ensure_schema`.*
