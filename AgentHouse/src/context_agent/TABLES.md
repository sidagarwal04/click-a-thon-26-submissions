# Context Agent — Postgres tables & ownership

**Context owns `context_*`. Instrumentation owns `meta_*`.**  
ClickHouse = event facts. Postgres = registry + living business meaning.  
No Agno agent for *writes* — publish stays on seed / Instrumentation.  
A **read-only** Agno Context Agent answers catalog questions (`python -m context_agent`).

| Writer | Tables | DDL |
|--------|--------|-----|
| **Instrumentation** | `meta_features`, `meta_events` | [`../instrumentation_agent/sql/postgres_meta_registry.sql`](../instrumentation_agent/sql/postgres_meta_registry.sql) |
| **Context** | `context_versions`, `context_items` | [`sql/postgres_catalog.sql`](./sql/postgres_catalog.sql) |
| **Conversation** | read-only on both | via Context tools |

```
Instrumentation                          Context
───────────────                          ───────
spec.md + events.ndjson
        │
        ▼
 profile → CH CREATE/load
        │
        ▼
 meta_features
  └── meta_events   ──read──►  reconcile / publish
                                      │
                                      ▼
                               context_versions
                                └── context_items
                                      │
                                      ▼
                               Conversation tools
```

**Rules we agreed:**

- Feature funnels live on **`meta_events.journey_order`** — do **not** copy them into `context_items`.
- Core product funnel only as `context_items` with `kind = 'funnel_step'`.
- New context version = **full copy-forward** of prior items + deltas (not “Express-only” rows).
- Context does **not** write `meta_*`. Instrumentation does **not** write `context_*`.
- Prefer deterministic catalog tools over free-form LLM SQL on the hot path.
- JSONB is fine for flexible payloads (`context_items.payload`, `meta_events.columns`).

---

## What Instrumentation Agent does (done on main)

Pipeline: **profile → ClickHouse DDL/load → Postgres meta**.

| Step | Behavior |
|------|----------|
| **In** | `SPECS_ROOT/{feature_id}/spec.md` + `events.ndjson` |
| **Profile** | Infer journey order from spec; flatten/infer CH column types per event |
| **ClickHouse** | Single Activity Schema (`activity_events`); SQLGlot-validated DDL; load rows |
| **Postgres** | Upsert `meta_features`; replace `meta_events` for that feature |
| **API** | `POST /v1/instrument`, `GET /v1/registry/{feature_id}`, `GET /health` |
| **Init** | `uv run python -m instrumentation_agent.init_db` |

It does **not**: publish living context, seed `base_context`, or own Conversation tools.

### 1. `meta_features`

One row per feature.

| feature_id | journey | spec_path | updated_at |
|------------|---------|-----------|------------|
| `01_express_checkout` | `[{event_name, journey_order, ch_table}, …]` | `…/spec.md` | `2026-06-08…` |

### 2. `meta_events`

Event → per-event ClickHouse table. `feature_id` is a **CSV** of feature ids
(multi-feature). Journey order lives in `meta_features.journey`. Column map in
`columns` (`{col: ch_type}`); SAS JSON blob is **`payload`** on `activity_events`.

| event_name | feature_id | ch_table | columns | status | registered_at |
|------------|------------|----------|---------|--------|---------------|
| `otp_entered` | `01_express_checkout` | `otp_entered` | `{"otp_success":"UInt8",…}` | `done` | `2026-06-08…` |

---

## What Context Agent owns (tables)

Every context table: `created_at`, `updated_at`. No `langfuse_trace_id` (tracing stays in Langfuse).

### 3. `context_versions`

Versioned living context. Exactly one row with `is_current = true`.

| context_version | parent_version | source | feature_id | is_current | summary | created_at | updated_at |
|-----------------|----------------|--------|------------|------------|---------|------------|------------|
| `v0` | | `seed` | | `false` | From `base_context.md` | `2026-04-01…` | `2026-04-01…` |
| `v3` | `v2` | `instrumentation` | `01_express_checkout` | `true` | Express meta reconciled; OTP↔K1 | `2026-06-08…` | `2026-06-08…` |

### 4. `context_items`

**One table** for all meaning.  
`kind` = `entity` \| `metric` \| `join` \| `funnel_step` \| `issue` \| `contradiction`.

| context_version | kind | item_key | label | payload | created_at | updated_at |
|-----------------|------|----------|-------|---------|------------|------------|
| `v3` | `entity` | `user` | Traveller | `{"primary_id_field":"user_id","definition":"…"}` | … | … |
| `v3` | `metric` | `funnel_conversion` | Funnel conversion | `{"formula":"…","grain":"user","caveats":"…"}` | … | … |
| `v3` | `join` | `app_to_doc` | | `{"from":"…","to":"…","keys":["application_id"]}` | … | … |
| `v3` | `funnel_step` | `pre_purchase:1` | | `{"funnel_key":"pre_purchase","step_order":1,"step_name":"destination_card_clicked"}` | … | … |
| `v3` | `issue` | `K1` | iOS WebKit OTP autofill | `{"hook":"OTP/pay → purchase on iOS"}` | … | … |
| `v3` | `contradiction` | `conversion_denominator` | | `{"left":"…","right":"…","guidance":"…"}` | … | … |

Init: `uv run python context_agent/scripts/init_schema.py`

---

## What Context Agent already has

| Piece | Status |
|-------|--------|
| DDL for `context_versions` + `context_items` | Done |
| Read tool `get_latest_context_items` | Done |
| Read tool `get_feature_meta` (reads Instrumentation `meta_*`) | Done |
| Write tool `publish_context_version` (copy-forward + deltas) | Done |
| Optional health FastAPI app | Done |
| Meta table DDL / meta upserts | **Out of scope** (Instrumentation) |

---

## What Context Agent still needs to do

Ordered by priority:

### 1. Seed `v0`

```bash
uv run python context_agent/scripts/seed_v0.py
```

Calls `publish_context_version` with `source=seed` and base entities / metrics /
core `funnel_step`s so Conversation is never empty. Idempotent unless `--force`.

### 2. Reconcile after Instrumentation

After `POST /v1/instrument` (or on demand):

- Read `get_feature_meta(feature_id)` / `GET /v1/registry/{feature_id}`
- Build deltas (joins/metrics/issues; update `summary`)
- **Do not** materialize feature journey as `funnel_step` rows
- Call `publish_context_version` (copy-forward + deltas)

### 3. Wire Conversation

Conversation imports `get_context_catalog_tools()` and uses deterministic CH query
builders against the Single Activity Schema (`activity_events` + `event_name` +
`payload`), citing `context_version`.

### Explicit non-goals for Context

- Writing `meta_features` / `meta_events`
- ClickHouse DDL or NDJSON load
- Extra Agno tools beyond the three above (seed/reconcile are callers of publish)
- Owning the old design tables (`meta_objects`, `meta_fields`, `meta_event_registry`, …,
  split `context_entities` / `context_metrics` / …)

---

## Conversation read recipe

1. `get_latest_context_items` → current version + meaning  
2. Filter `kind` as needed (`metric`, `issue`, `funnel_step`, …)  
3. `get_feature_meta(feature_id)` → journey + per-event `ch_table` + `payload` columns  
4. Run aggregates in **ClickHouse** (`activity_events`); cite `context_version` in the insight  

---

## Related

- [`README.md`](./README.md) — how to import tools  
- [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md) — profile / CH / meta pipeline  
- [`../conversation_agent/README.md`](../conversation_agent/README.md) — consumer of both layers  
