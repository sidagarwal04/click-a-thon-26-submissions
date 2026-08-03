# Atlys Click-a-thon — Build Plan (3 people, 10 hours)

## Architecture (final)

```
                    ┌─────────────────────────┐
   chat questions   │  LibreChat (as-is UI)   │  spec ingestion (upload/paste)
   ───────────────► │  chat + agent tool-calls│ ◄────────────────────────────
                    └───────────┬─────────────┘
                                │ calls
                    ┌───────────▼─────────────┐
                    │   Agent server           │
                    │  - Instrumentation Agent │──► perf_tool (deterministic)
                    │  - Analytics Agent       │
                    │  - Context Agent         │
                    └───────────┬─────────────┘
                     writes │        │ traces
                    ┌────────▼───┐  ┌▼────────────┐
                    │ ClickHouse │  │ Langfuse     │
                    │ atlys (evt)│  │ Cloud        │
                    │ agent_meta │  └──────────────┘
                    │ (schemas,  │
                    │  insights, │
                    │  context)  │
                    └────────┬───┘
                             │ reads
                    ┌────────▼───────────────┐
                    │ Lightweight custom      │
                    │ dashboard (separate app)│
                    │ - schema changes        │
                    │ - insights + confidence │
                    │ - context diff/changelog│
                    │ - "view full trace →"   │
                    └─────────────────────────┘
```

**Key decisions already made:**

- ClickHouse only — no Postgres. Agent metadata (context versions, schema proposals,
insights) lives in a separate `agent_meta` database on the same Cloud service, as
plain append-only MergeTree tables.
- LibreChat serves two roles: (1) default, unthemed chat UI for the two genuinely
chat-shaped surfaces — asking analytics questions, submitting a new spec; (2) via its
**Agents API** (beta, `POST /api/agents/v1/responses`), the LLM execution backend our
orchestrator calls into for each agent's reasoning turn. See "LibreChat Agents API"
section below — this replaced an earlier plan to hand-roll our own tool-calling loop.
- The dashboard is a **separate, minimal app**, decoupled from LibreChat, reading
directly from `agent_meta`. This is explicitly allowed ("lightweight UI or
structured CLI output") and keeps dashboard work from blocking agent work.
- Langfuse Cloud. Every agent action opens a tagged trace; the resulting `trace_url`
is stored alongside whatever row it produced, so the dashboard can deep-link out
instead of re-rendering trace detail itself.

---

## Shared contracts — lock these in the first hour, before anyone codes agent logic

Everything downstream depends on these. Get rough agreement fast, don't gold-plate.

### 1. `agent_meta` schema (ClickHouse, separate DB from `atlys`)

```sql
CREATE DATABASE IF NOT EXISTS agent_meta;

CREATE TABLE agent_meta.schema_proposals
(
    proposal_id UUID,
    parent_proposal_id Nullable(UUID),  -- set when this is a rework of a prior proposal
    revision UInt8 DEFAULT 0,           -- 0 = first attempt, increments per rework round
    ts DateTime DEFAULT now(),
    spec_name String,               -- e.g. 'express_checkout', 'unseen'
    table_name String,
    ddl String,
    ordering_key String,
    partition_key String,
    materialized_views Array(String),
    perf_report String,             -- JSON blob from perf_tool
    confidence Float32,
    rationale String,
    status Enum8(
        'drafted'=1,          -- Instrumentation Agent produced it, perf-tested
        'pending_review'=2,   -- handed to Context Agent
        'needs_rework'=3,     -- blocked by review findings or failed tests
        'approved'=4,         -- review passed, awaiting test harness
        'executed'=5,         -- DDL is live in atlys
        'rejected'=6          -- abandoned (loop cap hit with unresolved blockers)
    ),
    trace_url String
)
ENGINE = MergeTree ORDER BY (spec_name, ts);

CREATE TABLE agent_meta.schema_reviews
(
    review_id UUID,
    ts DateTime DEFAULT now(),
    proposal_id UUID,
    revision UInt8,
    verdict Enum8('approve'=1,'request_changes'=2,'block'=3),
    findings String,                -- JSON array: [{severity, category, description, suggested_fix}]
    context_sections_used Array(String),  -- which context_versions.section rows the review reasoned over
    reviewer_confidence Float32,
    trace_url String
)
ENGINE = MergeTree ORDER BY (proposal_id, ts);

CREATE TABLE agent_meta.test_cases
(
    test_id UUID,
    ts DateTime DEFAULT now(),
    introduced_by_proposal_id UUID,  -- which proposal first created this test
    table_name String,
    test_type Enum8('schema'=1,'insert_integrity'=2,'query_smoke'=3,'mv_integrity'=4),
    query String,                    -- the actual SQL, where applicable
    expected String,                 -- e.g. 'no_error', 'row_count=input_row_count', 'count()>0'
    description String
)
ENGINE = MergeTree ORDER BY (table_name, ts);

CREATE TABLE agent_meta.test_runs
(
    run_id UUID,
    ts DateTime DEFAULT now(),
    proposal_id UUID,       -- which proposal triggered this run of the *whole* accumulated suite
    test_id UUID,
    passed UInt8,
    actual String,
    duration_ms UInt32,
    trace_url String
)
ENGINE = MergeTree ORDER BY (proposal_id, ts);

CREATE TABLE agent_meta.insights
(
    insight_id UUID,
    ts DateTime DEFAULT now(),
    spec_name String,
    title String,
    summary String,                 -- the PM-facing write-up
    segment_cuts Array(String),
    evidence String,                -- JSON: queries run + key numbers
    related_known_issues Array(String),
    confidence Float32,
    trace_url String
)
ENGINE = MergeTree ORDER BY (spec_name, ts);

CREATE TABLE agent_meta.context_versions
(
    version_id UUID,
    ts DateTime DEFAULT now(),
    section String,                 -- e.g. 'metric:conversion_rate', 'table:express_checkout_events'
    before String,
    after String,
    diff_summary String,
    rationale String,
    trigger String,                 -- what caused this: 'new_table', 'contradiction_found', 'manual'
    confidence Float32,
    trace_url String
)
ENGINE = MergeTree ORDER BY (section, ts);
```

`context_versions` is append-only. "Current context" = latest row per `section`
(`argMax(after, ts) GROUP BY section` or a small `current_context` view on top).

### 2. `perf_tool` interface (owned by Person A, called as a black box by nobody else — just needs to exist)

```
run_perf_test(
  candidates: [{ ddl: str, ordering_key: str, partition_key: str }],
  sample_source: str,        # existing raw table or NDJSON path to load from
  query_patterns: [str]      # parameterized test queries, e.g. time-range + segment groupby
) -> {
  candidates: [{ ordering_key, avg_query_ms, rows_read, compressed_bytes }],
  baseline: {...},           # naive ORDER BY (id, timestamp, user_id), for comparison
  winner: str,
  speedup_vs_baseline: float
}
```

Runs against a scratch DB (`agent_meta_scratch` or `atlys_staging`) so it never
touches production tables. This is what makes the Instrumentation Agent's ordering-key
choice *evidence-based* instead of vibes — this is the single highest-leverage piece
for the "schema quality" judging criterion, so don't cut it under time pressure.

### 3. Langfuse tracing wrapper (owned by Person C, needed by A and B immediately)

A thin helper both agents import:

```python
with traced_run(agent="instrumentation", spec="express_checkout") as trace:
    ...
    trace.log(step="propose_ordering_key", input=..., output=..., reasoning=...)
    ...
trace_url = trace.url   # stored in the row written to agent_meta
```

Tags: `agent:{instrumentation|analytics|context}`, `spec:{slug}`, `run:{date}`.
Ship this by hour 1 — everything else logs through it.

### 4. Instrumentation Agent I/O contract

- **In:** `{ spec_markdown: str, sample_events: list[dict] }`
- **Out:** `{ table_name, ddl, column_mapping, materialized_views, perf_report, confidence, rationale, trace_url }`
- This exact object is both (a) what gets inserted into `schema_proposals` and
(b) what actually gets executed against `atlys`. One artifact, two uses — don't
let these drift into two different representations.

### 5. LibreChat Agents API contract

- Base: `{LIBRECHAT_URL}/api/agents/v1/responses`, auth via `Authorization: Bearer`
  API key (admin account gets full `remoteAgents` permissions by default — use it,
  don't fight per-user permission config under time pressure).
- Four agent IDs (see "LibreChat Agents API" section below): `instrumentation_proposer`,
  `context_reviewer`, `context_chronicler` (mergeable with reviewer if short on time),
  `analytics_agent`.
- Every orchestrator call to `/responses` is one child span inside the spec's parent
  Langfuse trace — never a bare, untraced call.

### 6. Confidence methodology (write this down once, apply everywhere — judges will ask "why 0.8?")

- **Schema proposal confidence:** driven by `perf_tool`'s `speedup_vs_baseline`,
plus % of raw event fields successfully typed/mapped (unmapped fields lower it).
- **Insight confidence:** sample size behind the finding (uniq users/rows) +
effect size (is the segment gap bigger than normal noise, e.g. >2x the
baseline variance) + whether it corroborates or contradicts a known-issues-log
entry (corroborates → higher; contradicts → flagged, not just silently trusted —
see the K1/K6 contradictions found in `Atlys/analysis/`).
- **Context commit confidence:** number of independent signals agreeing (e.g. a
null-rate anomaly seen across multiple tables scores higher than one column
in one table).

---

## LibreChat Agents API — how each agent gets its LLM turn

Decision: **don't hand-roll a tool-calling loop against a raw LLM API.** LibreChat's
Agents API (beta) exposes any agent defined in its UI as an OpenAI-compatible /
Open-Responses endpoint — `model` is just the agent ID. Our orchestrator calls it
exactly like it would call a model provider directly:

```python
resp = requests.post(
    f"{LIBRECHAT_URL}/api/agents/v1/responses",
    headers={"Authorization": f"Bearer {LIBRECHAT_API_KEY}"},
    json={"model": "agent_context_reviewer", "input": review_input_json},
)
```

**Split of responsibility — keep this boundary strict:**

- **Orchestrator (our code):** owns the `schema_proposals` state machine, all
  ClickHouse reads/writes, `perf_tool`, the test harness, the revision cap, and the
  Langfuse parent trace. Also runs `perf_tool`/tests itself and hands the *results* to
  the agent as input — never lets an agent's own tool-calling discretion decide
  whether a deterministic gate ran. This is also just correct per the problem
  statement's own hint: "push computation into ClickHouse and let the LLM interpret
  results, not fetch them."
- **LibreChat agents:** own the actual reasoning turn — interpret pre-computed
  evidence, produce structured output (DDL + rationale, review findings, insight
  text). Attach live tools (e.g. the ClickHouse MCP server) **only** where letting the
  LLM decide when to query is genuinely useful — e.g. the Analytics Agent pulling an
  extra segment cut mid-reasoning. Not on the Instrumentation/Context agents' core
  gated steps.

### Agents to define in LibreChat's UI

| Agent | Input (from orchestrator) | Output (structured) | Attached tools |
|---|---|---|---|
| `instrumentation_proposer` | spec.md + NDJSON sample + `perf_tool` results for 2–3 candidates | table_name, ddl, column_mapping, chosen ordering key + rationale, confidence | none — evidence is pre-computed |
| `context_reviewer` | pending proposal + current context (latest `context_versions` rows) | verdict + findings JSON (severity/category/description/suggested_fix) | none — reasons over provided context only |
| `context_chronicler` | executed proposal (final DDL) + current context | new/updated `context_versions` rows (table/metric/relationship sections) | none |
| `analytics_agent` | question or new-table trigger + current context + pre-aggregated ClickHouse results | PM-facing insight + confidence + evidence citations | ClickHouse MCP server (for follow-up cuts it decides it needs) |

Reviewer and Chronicler can be one LibreChat agent with two different prompts/inputs
if time is short — they're different orchestrator-side calls either way, so merging
them costs nothing structurally.

### Beta risk — mitigate, don't discover at hour 6

This is a beta feature ("endpoints, formats, behavior may change"). **Hour-1 smoke
test, non-negotiable:** enable `remoteAgents` in `librechat.yaml`, create one trivial
agent, call `/api/agents/v1/responses` from a curl/OpenAI-SDK script, confirm
streaming + structured output actually work end to end. Decide the fallback trigger
now: if it's not working cleanly by **hour 1:30**, fall back to calling the underlying
model provider directly with a minimal hand-rolled loop — cheap insurance, and it's
the same input/output contract either way so nothing downstream needs to change.

### Tracing through this boundary

Wrap every call to `/responses` in the existing `traced_run(...)` wrapper — log
input/output as a child span at minimum. The Open Responses format returns
item-level detail (reasoning items, tool-call items, tool-call outputs) when an agent
does use an attached tool (e.g. Analytics Agent's MCP calls) — unpack those into
finer-grained child spans instead of one opaque call. This directly strengthens
"traceability": a judge sees not just "Analytics Agent said X" but which ClickHouse
queries it decided to run to get there.

---

## The propose → review → rework loop (Instrumentation Agent ↔ Context Agent)

This is the core mechanism the whole submission stands or falls on. Two design
principles, up front:

1. **Communicate through ClickHouse state, not messages.** Neither agent calls the
   other directly over some ad-hoc RPC. The Instrumentation Agent writes a row to
   `schema_proposals`; the Context Agent reads proposals in `pending_review` status,
   writes a row to `schema_reviews`; the Instrumentation Agent reads the latest review
   for its proposal. `status` on `schema_proposals` is the single source of truth both
   agents and the dashboard agree on. This means either agent can be re-run, retried,
   or inspected independently — and it's exactly what makes the dashboard's "schema
   changes over time" view trivial (it's just reading the same table).
2. **One trace per spec ingestion, not one trace per agent call.** Orchestrate the
   whole propose→review→[rework]→test→execute→commit sequence as nested spans inside
   a single Langfuse trace (`traced_run(agent="pipeline", spec=...)` at the top,
   with `trace.span("propose")`, `trace.span("review", revision=1)`, etc. underneath).
   A judge opening one trace should see the entire argument — including the rounds
   where Context Agent pushed back — not have to hunt across disconnected traces.
   This is simplest to implement as a **synchronous, in-process orchestration**
   (function calls, not a queue) — no need for real async infra in 10 hours.

### State machine

```
drafted ──► pending_review ──► [Context Agent reviews]
                                      │
                     ┌────────────────┼─────────────────┐
                     ▼                ▼                 ▼
                 approve          request_changes      block
                     │                │                 │
                     ▼                ▼                 ▼
                 approved      needs_rework        needs_rework
                     │           (revision++,       (same, but a
                     │            back to           blocking finding
                     ▼            Instrumentation    — must be fixed,
              [test harness]      Agent to rework)   not just noted)
                     │                │
              ┌──────┴──────┐         │ (Instrumentation Agent revises DDL/
              ▼             ▼         │  mapping/MV, re-submits as new
          tests pass   tests fail ────┘  revision, loop back to pending_review)
              │
              ▼
          executed ──► [Context Agent commits new entity to context_versions]
```

**Loop cap:** max **2 rework rounds** per proposal. If still blocked after that,
auto-resolve rather than dead-end: execute anyway but with the unresolved findings
attached at low confidence and surfaced prominently on the dashboard, or fall back to
a human-approval gate if one's configured. The unseen-spec run on Day 2 must complete
autonomously end-to-end — an infinite or human-blocked loop there means "no trace, no
credit" on the piece that matters most. Decide this cap now; don't discover the need
for it live during the unseen-spec drop.

### Context Agent — two distinct modes

It's tempting to think of "Context Agent" as one job. It's actually two, triggered at
different points in the state machine, and worth building/naming separately:

**Mode 1 — Reviewer (gate before execution).** Runs on `pending_review`. Given the
proposal (DDL, column mapping, rationale, perf_report) and the *current* context
(latest row per `section` in `context_versions`, plus a live look at `system.columns`
for existing tables), it reasons about whether this proposal is safe/consistent to
execute, and writes structured findings — not prose, so the loop and the dashboard can
act on it programmatically:

```json
{
  "severity": "block | warn | info",
  "category": "naming_collision | metric_incompatible | relationship_ambiguous | grain_mismatch | known_issue_interaction | redundant_table | contradicts_context",
  "description": "...",
  "suggested_fix": "..."
}
```

Concrete checks to actually implement (grounded in things we already found by hand —
use these as the seed test cases for the reviewer, not hypotheticals):

- **Naming / identity discrepancy.** Does a proposed column look like a rename or
  duplicate of an existing context concept? Example we already hit: if an agent had
  proposed `eta_shown String` for a spec, and context (from `base_context.md`) still
  asserts a `visa_issuance_eta_days Int` concept exists elsewhere, that's a `block`
  or `warn` — is this the same concept under two names, or two different things?
  Cheap implementation: string/substring match of proposed column names against
  known entity + metric vocabulary in context; flag close-but-not-exact matches for
  LLM judgment rather than silently accepting or silently colliding.
- **Metric incompatibility.** If the spec's "questions the PM will ask" section
  implies a metric (e.g. Abandoned Checkout Recovery's "reconversion rate by
  drop_step"), does the proposed schema actually carry the join keys and grain to
  compute it? If `reconverted` doesn't carry `application_id`, the metric as scoped
  is uncomputable — this must be a `block`, not a footnote.
- **Grain mismatch.** Compare the raw NDJSON sample's actual event cardinality
  (rows per entity) against what the proposed table's `ORDER BY`/primary grain
  implies. We already saw `document_uploaded` collapse multiple capture attempts
  into one summary row with a `retry_count` field — if a new proposal's raw sample
  shows repeat events per entity but the DDL implies 1-row-per-entity, that's a
  `warn`: confirm it's an intentional summarize-on-submit design, not silent data loss.
- **Relationship-graph consistency.** New join keys (e.g. `group_id`, `share_id`)
  need an explicit entity + relationship-edge addition to context, not just a column.
  Missing this is a `warn`, not a `block` — but it must not silently pass through.
- **Known-issue interaction.** Does the new table's domain overlap a K1–K7 entry?
  (Express Checkout's OTP step is squarely K1's territory.) If so: `info`-level
  finding that tells the Analytics Agent to explicitly reconcile that known issue
  against the new table rather than assume it's still true — we already found K1
  doesn't hold up in the existing `pay_now_clicked` aggregate; a new table inheriting
  the same assumption uncritically would be a mistake worth flagging in advance.
- **Redundancy.** Does this proposal duplicate the grain/purpose of an existing
  table? Cheap check: compare proposed column set + join keys against
  `schema_proposals` history and `atlys` table list.

**Mode 2 — Chronicler (commits after execution).** Runs on `executed`. This is the
actual "context layer evolves as schema evolves" mechanic: write one or more
`context_versions` rows —
`table:{table_name}` (new entity: grain, join keys, what it captures),
and if applicable `metric:{name}` (a new or updated formula this table now supports)
and `relationship:{a}-{b}` (a new join edge). This is a different job from the
reviewer — it's not gating anything, it's recording what's now true. Keep the two
code paths separate even if they share the same LLM-prompting scaffolding; conflating
"should this execute" with "what changed" tends to produce mushy output for both.

### Person A / B task table updates for this loop

This replaces the flat "Build Instrumentation Agent" / "Build Context Agent" blocks
above with the state-machine version — same hour budget, more structure:

- **Person A, hours 3–6:** build the proposer half only — draft, perf-test, write
  `pending_review` row, then **stop and wait for a review row to appear**. Also build
  the rework path: read `schema_reviews.findings`, revise the specific thing flagged
  (not a full re-derivation), bump `revision`, re-submit.
- **Person B, hours 1–3:** build Reviewer mode first (it's on the critical path for A
  to test against) — the check categories above, findings JSON, verdict.
- **Person B, hours 3–6:** build Chronicler mode (post-execution context commit) and
  the Analytics Agent as originally planned — Chronicler is a smaller, second function
  in the same Context Agent module, not a separate build.

---

## Test harness subagent (owned by Person A, sits under Instrumentation Agent)

**What it's for:** `perf_tool` proves a schema is *fast*; it says nothing about
whether it's *correct*, and nothing stops a rework round from silently breaking
something that used to work. The test harness is the second execution gate
(`approved` → tests pass → `executed`), and — the actual ask — it **accumulates**:
every proposal that lands adds its own smoke tests to `agent_meta.test_cases`, and
every subsequent proposal re-runs the *entire accumulated suite*, not just its own.
That's what "ensure it breaks nothing" means concretely — regression, not just
validation of the one thing just built.

**Minimum viable set of checks per new proposal** (deterministic, no LLM judgment
needed — this is exactly why it's trustworthy):

1. **DDL applies cleanly** on an empty scratch table (already partially covered by
   `perf_tool`'s scratch execution — reuse that infra, don't rebuild it).
2. **Insert integrity** — load the spec's actual NDJSON sample; assert output row
   count == input row count (nothing silently dropped/truncated by a type mismatch).
3. **Nullability handling** — assert nullable columns actually accept nulls present
   in the sample without erroring.
4. **MV integrity** — if materialized views were declared, assert they populate with
   sane row counts (not 0, not erroring) after the insert.
5. **Query smoke test** — turn each "questions the PM will ask" bullet from the
   spec's `spec.md` into one representative query and assert it executes without
   error against the new table. This is cheap and directly demonstrates the schema
   actually serves the product questions it was built for — a good thing to surface
   on the dashboard next to the schema itself.

**Regression on every run:** before marking `executed`, re-run all tests currently in
`agent_meta.test_cases` (across every table, not just the new one) against the
current state of `atlys`. A rework round that, say, drops a column another table's MV
depends on gets caught here, not discovered later by the Analytics Agent silently
producing wrong numbers.

**Scope for 10 hours — build in this order, stop wherever the clock says stop:**
1. Insert-integrity + query-smoke checks for the table just proposed (this alone
   catches most real breakage and is the highest-value slice).
2. Accumulate into `test_cases` and re-run past tests on every new proposal
   (the actual "regression suite" behavior — do this once #1 is solid).
3. MV integrity checks (stretch — only if MVs are actually in heavy use).

If time is short, cut step 3 first, then even step 2 (falling back to "test only what
was just built") before ever cutting step 1 — a schema with zero correctness checks
undermines "schema quality" and "traceability" more than a schema with no regression
history does.

---

## Task breakdown

### Person A — Instrumentation Agent + `perf_tool`


| Hour | Task                                                                                                                                                                                                                                                                                           |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0–1  | ClickHouse creds confirmed; create `agent_meta` DB + tables; scaffold `perf_tool` function signature and CH connection. Join Person C's hour-1 LibreChat Agents API smoke test — this is a shared blocker, not solo work. |
| 1–3  | Build `perf_tool`: auto-create scratch tables for candidate DDLs, load sample data, run a fixed query battery (time-filter, segment `GROUP BY`, funnel-style join), time it, compare vs. a naive baseline (`ORDER BY (id, timestamp, user_id)` — the legacy pattern already in `ddl.sql`).     |
| 3–6  | Build the proposer half of Instrumentation Agent: spec.md + NDJSON → infer types/nullability → run `perf_tool` on 2–3 ordering-key/partition candidates yourself → call `instrumentation_proposer` via the Agents API with the spec + perf results as input → get back DDL + rationale + confidence → write `pending_review` row → **stop and wait for a `schema_reviews` row** (Person B's Reviewer mode) before executing anything. Build the rework path: read findings, revise the specific flagged thing, bump `revision`, re-submit. |
| 6–7  | Run it for real against 2–3 of the 5 known specs (prioritize **Express Checkout** and **Abandoned Checkout Recovery** — Person B needs real tables to query against). Wire in the test harness gate (`approved` → tests pass → `executed`).                                                   |
| 7–8  | Robustness pass: nested fields (Express Checkout's `payment.amount`/`payment.latency_ms`), missing/optional fields, messy specs.                                                                                                                                                               |
| 8–9  | Unseen-spec dry run (treat one held-back known spec as "unseen"), fix breakage.                                                                                                                                                                                                                |
| 9–10 | Final polish, confirm clean run for the real unseen-spec drop.                                                                                                                                                                                                                                 |


### Person B — Analytics Agent + Context Agent


| Hour | Task                                                                                                                                                                                                                                                                                                             |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0–1  | Seed context from `base_context.md` + the contradictions already found in `Atlys/analysis/00_overview.md` (missing `visa_issuance_eta_days`, K1/K6 not holding up, application_id not always empty). Agree on `context_versions`/`schema_reviews` schema with A/C. Join the hour-1 LibreChat Agents API smoke test. |
| 1–3  | Build **Reviewer mode** first — it's on Person A's critical path. Poll `schema_proposals` for `pending_review`, assemble current context (latest per `section`) + the proposal, call `context_reviewer` via the Agents API, parse verdict + findings JSON, write `schema_reviews` row, log to Langfuse. Implement the check categories from the "Context Agent — two modes" section (naming collision, metric incompatibility, grain mismatch, known-issue interaction, redundancy). |
| 3–6  | Build **Chronicler mode** (post-`executed` context commit — call `context_chronicler`, write new `table:`/`metric:`/`relationship:` sections to `context_versions`) and the **Analytics Agent**: pull current context + push aggregation into ClickHouse (never raw rows — `windowFunnel`, `GROUP BY`, never `SELECT *` into the LLM) → call `analytics_agent` via the Agents API (it may use the ClickHouse MCP tool for follow-up cuts) → cross-reference known-issues log → write `insights` row → log to Langfuse. |
| 6–7  | Implement confidence methodology (sample size, effect size, known-issue cross-match) — apply it, don't just have the LLM state a number.                                                                                                                                                                         |
| 7–8  | Test real analytics questions against Person A's instrumented tables (e.g. "does Express lift checkout conversion, cut by OS" against real generated table).                                                                                                                                                     |
| 8–9  | Unseen-spec dry run: full chain — Instrumentation proposes → Context Agent reviews (possibly reworks) → tests pass → executes → Context Agent commits → Analytics Agent produces insight — all traced.                                                                                                          |
| 9–10 | Prompt polish, graceful handling of thin/ambiguous evidence (don't force false confidence).                                                                                                                                                                                                                      |


### Person C — Tracing, LibreChat wiring, Dashboard


| Hour | Task                                                                                                                                                                                                         |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0–1  | Langfuse Cloud project set up; tagging convention finalized; ship the `traced_run` wrapper — this blocks A and B, do it first. **In parallel: stand up LibreChat, enable `remoteAgents`, generate an API key, create one trivial agent, and run the Agents API smoke test with A and B watching** — confirm `/api/agents/v1/responses` actually streams and returns structured output. If not working cleanly by hour 1:30, trigger the fallback (direct model-provider calls with a minimal loop) and tell A/B immediately. |
| 1–2  | If the smoke test passed: create the 4 real agents in LibreChat's UI (`instrumentation_proposer`, `context_reviewer`, `context_chronicler`, `analytics_agent`) with their system prompts and, for `analytics_agent` only, the ClickHouse MCP server attached. Wire "ask a question" and "submit a spec" chat surfaces to the orchestrator's endpoints. Default UI, no theming. |
| 2–5  | Build the lightweight custom dashboard (separate small app) reading `agent_meta` directly: schema-changes-over-time, insights feed with confidence + "view full trace →" links, context diff/changelog view. |
| 5–7  | Wire LibreChat's ingestion flow end-to-end to the Instrumentation Agent; wire Q&A to the Analytics Agent; confirm `trace_url` flows through to dashboard rows.                                               |
| 7–8  | Polish: confidence badges, diff rendering, filter by spec/agent/date. Smoke-test both surfaces.                                                                                                              |
| 8–9  | Unseen-spec dry run: confirm dashboard reflects new schema + insight + context entries with correct trace links live.                                                                                        |
| 9–10 | Submission prep: README, and a recorded backup walkthrough in case the live demo flakes.                                                                                                                     |


---

## Cross-team checkpoints (all 3, brief sync, don't let these slip)

- **Hour 1:** contracts locked — `agent_meta` schema, `perf_tool` signature, `traced_run` wrapper all exist, even if empty-bodied. **LibreChat Agents API smoke test done, all three watching — go/fallback decision made by hour 1:30, not silently discovered later.**
- **Hour 3:** `perf_tool` and tracing wrapper functional — A and B can now integrate for real.
- **Hour 6:** first true end-to-end pass on one known spec, touched by all three components.
- **Hour 8:** full dry run treating a held-back spec as "unseen" — this is the dress rehearsal for the real Day-2 drop. Non-negotiable, don't skip this to keep building features.
- **Hour 9–10:** buffer only. No new features after hour 9.

## If you're behind schedule, cut in this order

1. Dashboard visual polish → fall back to structured CLI/table output (explicitly allowed).
2. `perf_tool` candidate breadth → drop to exactly 2 candidates (naive baseline vs. proposed), not an exploration sweep.
3. LibreChat spec-ingestion UI → fall back to a script/CLI trigger for the Instrumentation Agent.
4. LibreChat Agents API itself → if the hour-1:30 fallback trigger fires, call the model
   provider directly with a minimal loop. Same input/output contract, so nothing else
   in the plan needs to change — this is exactly why the smoke test happens first.

## Never cut

- Langfuse tracing (directly judged — "no trace, no credit").
- Context versioning with rationale + confidence (directly judged — "context freshness").
- The hour-8 unseen-spec dry run.

