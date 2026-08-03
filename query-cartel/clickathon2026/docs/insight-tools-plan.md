# Stored Insights Tools Plan

> **Status:** Plan only — not implemented.
>
> **Audience:** Implementers of MCP tools (`Atlys/service/mcp_server.py`), insight persistence (`Atlys/service/agents/analytics.py`, DDL in `app.py`), REST (`Atlys/service/api.py`), agent prompt + provisioning (`Atlys/agents/atlys_pm.md`, `Atlys/scripts/provision_agent.py`), and optionally the Insights dashboard (`Atlys/ui/src/components/dashboard/**`).
>
> **Depends on:** Existing pipeline insights (`meta.insights`, `get_insight` / `list_insights`) and safe DB reads (`db_schema`, `table_stats`, `aggregate`, `sample_rows`). Orthogonal to chat viz (`docs/chat-viz-plan.md`) and chat history persistence.
>
> **North star:** Chat becomes a **working memory for analytics** — the agent can find prior insights, save new findings from live exploration, and record human review — so PMs accumulate durable, citable knowledge instead of one-off answers that disappear when the tab closes.

---

## 0. Problem

Today the agent can:

| Capability | How |
|---|---|
| Run the spec → schema → insight pipeline | `run_spec` / `approve_schema` → AnalyticsAgent writes `meta.insights` |
| Narrate a frozen pipeline card | `get_insight`, `list_insights` |
| Explore live ClickHouse | `db_schema` / `aggregate` / … |

What it **cannot** do:

1. **Save an ad-hoc finding** — after `aggregate` answers “conversion by destination,” nothing durable is written unless the full pipeline runs again.
2. **Review / annotate** — no status, owner note, or “looks right / stale / needs follow-up” on a card.
3. **Search / filter insights** — `list_insights` dumps every row (summary fields only); no filter by feature, source, confidence, date, or review status.
4. **Distinguish provenance** — pipeline playbook cards and agent-authored notes share one shape; the UI and prompt cannot say which is which.
5. **Close the chat ↔ dashboard loop** — Insights tab only shows REST reads; chat cannot pin or refresh a card into that surface intentionally.

**User-facing target:**

| Situation | Agent does |
|---|---|
| “What insights do we have on express checkout?” | Filtered `list_insights` / `get_insight` with clear titles + confidence |
| “Save that destination breakdown as an insight” | `create_insight` (or `save_insight`) with evidence from the last aggregate |
| “Mark the latest card as reviewed — numbers look good” | `review_insight` with status + note |
| “Is this still current?” | Fetch card + optional fresh `aggregate` against the same table; narrate delta (MVP: manual; later: `refresh_insight`) |
| “Show me unreviewed / agent-saved cards” | Filtered list by `source` / `review_status` |

---

## 1. Current state

| Layer | Today | Gap |
|---|---|---|
| DDL | `meta.insights (spec, title, summary, confidence, evidence, trace_id, created_at)` append-only MergeTree | No `insight_id`, `source`, `tags`, review fields |
| Write path | AnalyticsAgent `_upsert_insight` after playbook only | No MCP / REST create |
| Read MCP | `get_insight(feature)` LIKE match latest; `list_insights()` all, thin columns | No filters; no get-by-id; summary omits body |
| REST | `GET /api/insights`, `GET /api/insights/{feature}` | No POST / review endpoints |
| Prompt | Prefer stored insight vs fresh aggregate; summarize cards | No save / review workflows |
| UI | `InsightCard.jsx` on dashboard | No review badge, source badge, or chat deep-link |
| Events | `insight.created` from pipeline | No `insight.reviewed` / agent-authored create event |

**Key files**

- `Atlys/service/mcp_server.py` — `_get_insight`, `_list_insights`, TOOLS
- `Atlys/service/agents/analytics.py` — `_upsert_insight`, evidence shape
- `Atlys/service/app.py` — DDL
- `Atlys/service/api.py` — REST list/get
- `Atlys/agents/atlys_pm.md` — prompt
- `Atlys/scripts/provision_agent.py` — tool allowlist
- `Atlys/ui/src/components/dashboard/InsightCard.jsx` — card UI

---

## 2. Design principles

1. **Durable over ephemeral.** Anything the PM would want next week should land in `meta.insights` (or a sibling table), not only in LibreChat transcript.
2. **Provenance always explicit.** Every card records `source` ∈ `pipeline` \| `agent` \| `human` and a `trace_id` when available. Narration must say whether numbers came from a stored card vs a fresh query.
3. **Evidence is structured, not free prose only.** Saved insights should carry replayable evidence (SQL and/or structured aggregate args + rows), matching the spirit of pipeline cards — truncated safely for MCP.
4. **Append-friendly review.** Prefer new review rows or append-only columns over in-place UPDATE semantics that fight ClickHouse MergeTree. Latest review wins for “current status.”
5. **Human intent for writes.** Creating or reviewing an insight requires clear user intent (“save this”, “mark reviewed”). Do not auto-persist every aggregate.
6. **Pipeline tools stay authoritative for feature runs.** Agent-saved cards do **not** replace `run_spec` / AnalyticsAgent playbooks; they complement them for exploratory analysis.
7. **Bound payloads.** Reuse `truncate_for_mcp` / evidence size caps; reject oversized evidence with a clear error rather than silent truncation that looks like full data.
8. **Thin UI in MVP.** Tools + prompt first; dashboard badges and refresh hooks can follow in a later wave.

---

## 3. Schema evolution

### 3.1 Extend `meta.insights` (additive)

Keep existing columns for backward compatibility. Add via `ALTER … ADD COLUMN IF NOT EXISTS` in `app.py` DDL bootstrap (same pattern as `pending_runs.runner_token`).

| Column | Type | Default | Meaning |
|---|---|---|---|
| `insight_id` | String | `generateUUIDv4()` or app-generated UUID | Stable id for get / review |
| `source` | LowCardinality(String) | `'pipeline'` | `pipeline` \| `agent` \| `human` |
| `feature` | String | `''` | Normalized feature key (spec basename or free tag) |
| `tags` | String | `'[]'` | JSON string array |
| `query_spec` | String | `'{}'` | Optional structured args that produced evidence (e.g. last `aggregate` args) |
| `created_by` | LowCardinality(String) | `'analytics_agent'` | `analytics_agent` \| `mcp` \| `api` |

**Backfill rule:** Existing rows → `source='pipeline'`, `insight_id` assigned on read if empty (or one-shot migration insert). Prefer generating `insight_id` in application code on every new insert so CH version differences do not matter.

**Ordering:** Consider `ORDER BY (created_at, insight_id)` only for *new* installs if we recreate the table; do **not** require a heavy recreate for MVP — filter in SQL is enough.

### 3.2 Review store — `meta.insight_reviews` (new)

Append-only reviews, one row per review action:

```sql
CREATE TABLE IF NOT EXISTS meta.insight_reviews (
    insight_id String,
    status LowCardinality(String),   -- approved | flagged | stale | needs_followup
    note String,
    reviewer LowCardinality(String), -- user | agent | system
    trace_id String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree ORDER BY (insight_id, created_at)
```

**Current status** for list/get = latest review for that `insight_id`, or `unreviewed` if none.

Alternative considered and rejected for MVP: mutating columns on `meta.insights` via ReplacingMergeTree — harder to reason about with existing append inserts from AnalyticsAgent.

---

## 4. Proposed tools

Enhance two existing tools; add three new ones. Names bikeshed-ok; keep short.

### 4.1 `list_insights` (enhance)

| Arg | Type | Default | Meaning |
|---|---|---|---|
| `feature` | string | omit | Substring / exact match on `spec` or `feature` |
| `source` | string | omit | Filter `pipeline` \| `agent` \| `human` |
| `review_status` | string | omit | `unreviewed` \| `approved` \| `flagged` \| `stale` \| `needs_followup` |
| `confidence` | string | omit | Exact match on confidence label if present |
| `limit` | int | `20` | Cap (hard max e.g. 50) |
| `offset` | int | `0` | Pagination |

**Response sketch:**

```json
{
  "insights": [
    {
      "insight_id": "…",
      "spec": "…",
      "feature": "…",
      "title": "…",
      "confidence": "…",
      "source": "pipeline",
      "review_status": "unreviewed",
      "trace_id": "…",
      "created_at": "…"
    }
  ],
  "count": 12,
  "truncated": false
}
```

Omit full `summary` / `evidence` here (keep list cheap).

### 4.2 `get_insight` (enhance)

| Arg | Type | Default | Meaning |
|---|---|---|---|
| `insight_id` | string | omit | Preferred exact fetch |
| `feature` | string | omit | Legacy LIKE latest (keep for prompt compat) |
| `include_evidence` | bool | `true` | Allow summary-only fetch |
| `include_reviews` | bool | `false` | Attach recent review history |

Prefer `insight_id` when both set. Return `review_status` + latest note. Truncate evidence via existing MCP caps; set `truncated: true` when cut.

### 4.3 `create_insight` (new)

Persist an agent- or human-authored card.

| Arg | Type | Required | Meaning |
|---|---|---|---|
| `title` | string | yes | PM-readable title |
| `summary` | string | yes | Short narrative |
| `confidence` | string | yes | e.g. `high` \| `medium` \| `low` \| `unknown` (align with pipeline labels if fixed set exists) |
| `evidence` | object \| array | yes | Structured evidence; prefer list of `{label, kind?, sql?, rows?, query_spec?}` |
| `feature` / `spec` | string | one recommended | Grouping key; default `ad_hoc` if omitted |
| `tags` | string[] | no | Free tags |
| `query_spec` | object | no | Replay hint (aggregate args, table, filters) |
| `trace_id` | string | no | Langfuse / session id if known |

**Behavior:**

1. Validate title/summary non-empty; evidence non-empty and under size budget.
2. Generate `insight_id`; set `source='agent'` (or `human` if flagged via arg later).
3. Insert into `meta.insights`; emit `insight.created` (extend payload with `source`, `insight_id`).
4. Optionally write `generated/<feature>/insight-<id>.md` (nice-to-have; skip if feature is `ad_hoc`).
5. Return `{ insight_id, created_at, source, message }`.

**Safety:** Read-only DB tools stay read-only; this tool writes **only** to `meta.insights` (+ event log), never to analytics feature tables.

**Prompt gate:** Call only when the user asks to save / pin / remember a finding, or confirms a proposal (“Want me to save this?” → yes).

### 4.4 `review_insight` (new)

| Arg | Type | Required | Meaning |
|---|---|---|---|
| `insight_id` | string | yes | Target card |
| `status` | string | yes | `approved` \| `flagged` \| `stale` \| `needs_followup` |
| `note` | string | no | Free-text rationale |

**Behavior:** Verify insight exists → insert `meta.insight_reviews` → emit `insight.reviewed` → return latest status.

### 4.5 `compare_insight` (optional, Wave 3)

Re-run `query_spec` / stored SQL under readonly settings and return `{ stored, fresh, delta_summary_hint }`. Model narrates the delta; do not auto-overwrite the card. If `query_spec` missing, return `UNSUPPORTED` and suggest manual `aggregate`.

---

## 5. REST & UI (thin)

### 5.1 REST (Wave 2)

| Method | Path | Role |
|---|---|---|
| `GET /api/insights` | Add query params mirroring `list_insights` filters |
| `GET /api/insights/id/{insight_id}` | Exact get |
| `POST /api/insights` | Mirror `create_insight` (dashboard / tests) |
| `POST /api/insights/{insight_id}/reviews` | Mirror `review_insight` |

Keep `GET /api/insights/{feature}` for backward compat (feature LIKE).

### 5.2 Dashboard (Wave 3, optional)

- Source badge: Pipeline / Agent / Human
- Review status chip on `InsightCard`
- Filter controls on Insights tab
- Optional: after chat save, poll or event so the tab refreshes (out of scope unless chat emits a client hint)

No requirement to render full evidence charts in MVP (see `docs/chat-viz-plan.md`).

---

## 6. Prompt & provisioning

Update `atlys_pm.md` + `_ATLYS_TOOLS`:

**Tools line:** add `create_insight`, `review_insight`; document enhanced `list_insights` / `get_insight`.

**New workflows:**

```
Workflow (explore → save):
1. Answer with db_schema / aggregate as today.
2. If the user asks to save / pin / remember, call create_insight with
   title, summary, confidence, and evidence copied from tool results
   (include sql / query_spec when available). Confirm insight_id.
3. Do not create_insight unprompted.

Workflow (review library):
1. list_insights with filters; get_insight for the chosen id.
2. On explicit review (“approve”, “flag as stale”, …), call review_insight.
3. Always say whether figures are from a stored card vs a fresh aggregate.
```

Re-provision LibreChat agent after allowlist change.

---

## 7. Events

Extend `Atlys/service/events.py`:

| Event | When |
|---|---|
| `insight.created` | Already exists — enrich payload with `insight_id`, `source` |
| `insight.reviewed` | New — after successful `review_insight` |

Actors: `ACTOR_MCP` / `ACTOR_USER` as appropriate. Keep AnalyticsAgent pipeline emit path working (same event, `source=pipeline`).

---

## 8. Implementation waves

### Wave 0 — Spike / contract

1. Freeze confidence enum and review status enum against current pipeline labels.
2. Decide app-generated `insight_id` vs CH default.
3. Sketch evidence JSON for agent saves (map from `aggregate` response → evidence item).
4. Confirm MergeTree append + “latest review wins” is acceptable for demo scale.

### Wave 1 — Read path quality (unblocks “review the library”)

1. DDL: `insight_id`, `source`, `feature`, … on `meta.insights`; create `meta.insight_reviews`.
2. Backfill / default `source='pipeline'` for inserts from AnalyticsAgent (set `insight_id` on write).
3. Enhance `list_insights` + `get_insight` (filters, id, review_status).
4. Prompt: “browse insights” workflow; re-provision.
5. Tests: filter by feature/source; get by id; empty library.

### Wave 2 — Create + review writes

1. `create_insight` + `review_insight` MCP handlers + event emits.
2. Wire AnalyticsAgent insert to populate new columns.
3. REST mirrors for create/review + filtered list.
4. Prompt gates for save/review; SETUP.md tool list.
5. Tests: create → list → get → review → list shows status; reject empty evidence; size cap.

### Wave 3 — Hardening & UX

1. Optional `compare_insight` / refresh helper.
2. Dashboard badges + filters.
3. Metrics: create/review counts (no PII in notes logs beyond length).
4. Chaos: huge evidence payload → structured error; concurrent reviews append correctly.

---

## 9. Test plan

| # | Case | Expected |
|---|---|---|
| 1 | `list_insights` empty DB | `insights: []`, `count: 0` |
| 2 | Pipeline run creates card | `source=pipeline`, non-empty `insight_id` |
| 3 | `list_insights(feature=…)` | Only matching cards |
| 4 | `get_insight(insight_id=…)` | Full card + `review_status=unreviewed` |
| 5 | `create_insight` with aggregate evidence | Row in `meta.insights`, `source=agent`, event emitted |
| 6 | `create_insight` missing title/evidence | `BAD_ARGUMENT` |
| 7 | Oversized evidence | Error or explicit truncate flag — never silent full accept |
| 8 | `review_insight` approved | Row in `meta.insight_reviews`; list shows `approved` |
| 9 | Review unknown id | `NOT_FOUND` |
| 10 | Chat: explore then “save this” | Two-phase: aggregate then create; returns id |
| 11 | Chat: “flag latest as stale” | list/get → review; narration cites status |
| 12 | Existing `get_insight(feature=)` | Still works (compat) |

---

## 10. Acceptance criteria

- [ ] Agent can filter and open stored insights by feature / source / review status.
- [ ] Agent can persist an exploratory finding as a durable card with structured evidence when the user asks.
- [ ] Agent can record a review status + note against an insight id.
- [ ] Pipeline-generated insights continue to work; new columns populated; no free-form SQL write tool.
- [ ] Provenance (`source`) and review status visible in tool results (and ideally dashboard).
- [ ] Prompt + LibreChat allowlist updated and agent re-provisioned.
- [ ] Caps / validation prevent unbounded meta inserts from MCP.

---

## 11. Effort sketch

| Wave | Effort | Outcome |
|---|---|---|
| Wave 0 | ~1–2h | Enums + evidence contract |
| Wave 1 | ~half–1 day | Filtered list/get + schema |
| Wave 2 | ~1 day | create + review + REST |
| Wave 3 | optional | compare + dashboard polish |

**MVP cut:** Waves 0–2 (`list_insights` / `get_insight` enhanced, `create_insight`, `review_insight`).

---

## 12. Non-goals (MVP)

- Auto-saving every chat answer or every `aggregate` call.
- Full CRDT / collaborative editing of insight text.
- Replacing business context (`propose_context_update`) or known-issues catalog.
- Chat message persistence in Atlys (separate plan if revived).
- Free-form SQL execution as an evidence source.
- Deleting insights (append-only; use `stale` / `flagged` instead).

---

## 13. Appendix — example compositions

| PM ask | Tool sequence |
|---|---|
| What insights exist? | `list_insights(limit=20)` |
| Express-checkout cards only | `list_insights(feature=express)` → `get_insight(insight_id=…)` |
| Unreviewed agent saves | `list_insights(source=agent, review_status=unreviewed)` |
| Save destination breakdown | `aggregate` → (user confirms) → `create_insight` |
| Looks good, ship it | `review_insight(status=approved, note=…)` |
| Numbers feel old | `review_insight(status=stale)` then fresh `aggregate` |
| After a full feature run | Existing pipeline; agent summarizes via `get_insight` / approve response |

---

## 14. Open questions

1. **Confidence labels** — reuse exact pipeline strings or normalize to a small enum at the tool boundary?
2. **Who may create?** — agent-only via MCP vs also human form on dashboard in Wave 2.
3. **Idempotency** — should identical title+query_spec within N minutes return the existing id instead of duplicating?
4. **Evidence from chat prose** — allow summary-only saves with empty SQL, or require at least one tool-backed evidence item?
5. **Feature key** — require `spec` path-like values for pipeline parity, or allow free-form `feature` tags for ad-hoc work?
