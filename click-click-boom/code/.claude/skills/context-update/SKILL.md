---
name: context-update
description: Use this skill whenever you've verified something new about Atlys (a contradiction, a confirmation, a new table/entity/metric, a resolved open question) and need to write it into the living context layer — the same append-only path this repo's Chronicler agent and orchestrator use. Covers the `agent_meta.context_versions` schema, the required JSON content shape, confidence calibration, how the real orchestrator writes it (`orchestrator/pipeline.py::_write_context_sections`), and how this differs from writing to `agent_meta.insights`. Triggers on: "update the context", "fix the context", "add this finding to context", "chronicler", "record this in agent_meta", "context agent".
---

# Context Update — writing to the Atlys context layer (Chronicler mode)

Read the `context-engine` skill first if you haven't — it covers connecting and the existing taxonomy. This skill covers *writing*.

## The one rule that matters: never edit, only append

`agent_meta.current_context` is a **view**: `argMax(after, ts) GROUP BY section` over `agent_meta.context_versions`. You never `ALTER`/`UPDATE` a row and you never delete history. To change what a section says, `INSERT` a new row into `context_versions` with a later `ts` — the view resolves to it automatically. This gives every correction a permanent, inspectable audit trail (`before` → `after`, with `rationale` and `trigger`).

Full DDL: `atlys-agents/sql/agent_meta_ddl.sql`:
```sql
CREATE TABLE agent_meta.context_versions
(
    version_id UUID,
    ts DateTime DEFAULT now(),
    section String,        -- 'category:name', e.g. 'issue:K1', 'table:express_checkout_events'
    before String,          -- the PREVIOUS content JSON (empty string if net-new section)
    after String,           -- the NEW content JSON — this is what current_context will serve
    diff_summary String,    -- one line: what changed (usually == after.summary)
    rationale String,       -- WHY, citing the specific evidence/query
    trigger String,         -- what caused this update, e.g. 'eda_verification', 'chronicle', 'new_spec:instant_forex'
    confidence Float32,
    trace_url String        -- Langfuse trace link if you have one; '' is fine otherwise
)
```

## How this repo's real Chronicler writes it — mirror this, don't diverge

The `context_chronicler` agent (`agents/prompts.py::CONTEXT_CHRONICLER`) does **not** write to ClickHouse itself — it only has read tools (`list_context_sections`/`lookup_context`) and outputs a JSON `{"sections": [...]}` payload. The actual `INSERT` happens in `orchestrator/pipeline.py::_write_context_sections()`, which is worth reading before you hand-write rows, because it has two behaviors you should replicate manually:

1. **`after` is whitelisted to exactly 5 keys** — `title, summary, body, fields, sources`. Anything else the agent puts at the top level of a section gets silently dropped (`{k: s.get(k) for k in (...)}`). Don't rely on extra top-level fields surviving.
2. **`before`/`diff_summary`/`rationale` are coerced to strings defensively** (`_as_text`) — if you pass a dict, it gets `json.dumps`'d rather than erroring. Still write them as strings yourself; don't depend on the coercion.

The Chronicler's own trigger for automated pipeline runs is the literal string `"chronicle"`. For a manual EDA-driven correction (like a Claude Code session running ad-hoc verification queries), use a descriptive trigger instead — `"eda_verification"` is the established convention from prior sessions — so it's clear in the audit trail which updates came from the automated post-execute flow vs. a manual pass.

## `content` (i.e. `before`/`after`) JSON shape — keep it consistent

```json
{
  "title": "Short human title",
  "summary": "One or two sentences — the verdict, up front, not buried in body.",
  "body": "The full reasoning: what was checked, the actual numbers, what it means, what's still open.",
  "fields": { "...": "machine-readable numbers/formulas other agents will grep for" },
  "sources": ["base_context.md#N", "atlys EDA <date>: <what query/comparison was run>"]
}
```
Never write free prose directly into `after` — always this shape, and only these 5 keys (see above). `fields` is what a downstream agent will actually parse; don't bury the number that matters in `body` only.

For `issue:*` sections specifically, lead `summary` with a verdict tag so a scan of `current_context` alone tells the story: **CONFIRMED** / **CONTRADICTED** / **DIRECTIONALLY CONFIRMED** / **UNTESTED**. Match `fields.status` to the same word, lowercase-with-underscores.

## Confidence calibration (match the existing scale — don't invent a new one)

- **0.9–0.95** — you ran a specific verifying query against `atlys` yourself and it either confirms or contradicts the claim outright.
- **0.7–0.85** — sourced from the base spec doc or a prior analysis, plausible, not independently re-run this session.
- **≤0.4** — genuinely untested, or tested but inconclusive. Say what specific query/cut would resolve it in `fields.needs`.

## Section naming — reuse the taxonomy, don't fragment it

Use `category:name` matching one of the existing categories (`table`, `metric`, `issue`, `entity`, `convention`, `relationship`, `dataquality`, `overview` — see `context-engine` for current membership, confirmed live not hardcoded). Only mint a new category on purpose — e.g. instrumenting a genuinely new kind of thing — not because you forgot to check what exists.

**Additive sections are additive, not replaceable.** `relationship:join_map` is explicitly cumulative — when a new table lands, `after` must contain the *full* edge list (old edges + the new one), not just the delta, or you silently erase prior joins for anyone reading only the latest version. The real Chronicler is instructed to `lookup_context(["relationship:join_map"])` first for this exact reason — do the same before writing to it.

## This is NOT where insights go

`agent_meta.insights` (`insight_id, spec_name, title, summary, segment_cuts, evidence, related_known_issues, confidence, trace_url`) is the Analytics Agent's PM-facing output — "checkout drop on mobile is 15%, coincides with X." `context_versions` is the shared business/data-context substrate everyone reasons from. A contradiction/confirmation of a known issue (K1, K6, etc.) belongs in `context_versions` under `issue:K*`; a novel, actionable finding for a product audience belongs in `insights`. Check `SELECT count() FROM agent_meta.insights` before assuming this table has anything in it — it has been empty at points in this project despite active `context_versions` traffic, which means findings may be landing in the wrong place or not being surfaced to a PM audience at all.

## Writing the INSERT safely

Content strings contain apostrophes/quotes (`"3-5 days"`, `don't`) — don't hand-escape SQL string literals. Build rows as JSON and POST with `FORMAT JSONEachRow`:

```bash
cd atlys-agents && set -a; source .env; set +a
python3 - <<'PY'
import json, uuid, datetime
row = {
  "version_id": str(uuid.uuid4()),
  "ts": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S"),
  "section": "issue:K7",
  "before": json.dumps({...}),   # pull the CURRENT value from current_context first
  "after": json.dumps({
      "title": "K7 — App 7.45 rollout",
      "summary": "CONTRADICTED. app_version shows a flat ~20% share every month, no rollout curve.",
      "body": "...",
      "fields": {"status": "contradicted"},
      "sources": ["atlys EDA 2026-08-01: app_version share by month"]
  }),
  "diff_summary": "CONTRADICTED. app_version shows a flat ~20% share every month, no rollout curve.",
  "rationale": "Checked app_version share by month directly; flat distribution inconsistent with any rollout.",
  "trigger": "eda_verification",
  "confidence": 0.9,
  "trace_url": ""
}
with open("/tmp/ctx_update.jsonl", "w") as f:
    f.write(json.dumps(row) + "\n")
PY
curl -s -u "$CLICKHOUSE_USER:$CLICKHOUSE_PASSWORD" --data-binary @/tmp/ctx_update.jsonl \
  "https://$CLICKHOUSE_HOST:$CLICKHOUSE_PORT/?query=INSERT%20INTO%20agent_meta.context_versions%20FORMAT%20JSONEachRow"
```

(If working from inside `atlys-agents/.venv` where `clickhouse_connect` connects cleanly, `agent_meta.db.get_client(database="agent_meta").insert(...)` — the same call `_write_context_sections` makes — works too; use whichever path is actually reachable in your shell.)

Always fetch `before` from `current_context` for that exact `section` first (empty string only if the section is genuinely net-new) — that's what makes the diff trail meaningful.

## Before you write: ground it or don't write it

Every `after.rationale`/`sources` must point to a real query or a real spec file you actually looked at this session — `"atlys EDA <date>: <one-line description of the comparison>"` at minimum. Don't upgrade a status (`untested` → `contradicted`, `contradicted_in_aggregate` → `contradicted`) without the specific query that justifies the upgrade.
