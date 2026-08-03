---
name: atlys-okf-authoring
description: Author and maintain the Atlys living-context bundle as an Open Knowledge Format (OKF) set of markdown concept files under librechat/context_docs/ — scaffold and seed the bundle, determine the update trigger, gather live-schema/DDL/base_context sources, diff and write one-concept-per-file docs (entity, metric, table, relationship, known-issue), and regenerate/validate index.md. Apply on every context run. OKF standard, concept templates, and the Atlys taxonomy are in references/.
always-apply: true
---

# Skill: OKF Authoring

Keep the living context bundle fresh. Read the OKF standard first, then apply the Atlys-specific
decisions below. **Do not invent facts** — state only what the source (DDL, `base_context.md`,
live schema, Analytics findings, or a user assertion) supports; mark unknowns explicitly.

> Load and apply the OKF standard in [references/okf-docs.md](references/okf-docs.md) — bundle
> layout, required `type` frontmatter, reserved `index.md` / `log.md`, cross-link rules, and the
> `okf` commands. It is the source of truth for OKF; the summary here is operational.

## Concept types used in this bundle

| `type` | Folder | One file per |
|---|---|---|
| `overview` | `/overview.md` | the business + funnel summary (holds `context_version`) |
| `entity` | `/entities/` | user, application, destination, event, document, … |
| `metric` | `/metrics/` | one metric formula (conversion, drop-off, pass-rate, …) |
| `table` | `/tables/` | one raw or newly-instrumented ClickHouse table |
| `relationship` | `/relationships/` | a join / funnel-order relationship |
| `known-issue` | `/known-issues/` | K1–K7 and any new confirmed issue |
| `contradiction` | `/contradictions/` | a detected conflict or gap (see `atlys-contradiction-detection`) |

Exact frontmatter + body per type: [references/okf-concept-templates.md](references/okf-concept-templates.md).
Atlys seed taxonomy: [references/atlys-context-taxonomy.md](references/atlys-context-taxonomy.md).

## Step 1 — Resolve `KB_DIR` + ensure scaffold

`list_directory` on `KB_DIR`. If missing/empty, scaffold:

```
librechat/context_docs/
├── overview.md        (type: overview — holds context_version: 1)
├── log.md             (reserved — changelog; first entry = "bundle created")
├── index.md           (reserved — regenerated in Step 7)
├── entities/  metrics/  tables/  relationships/  known-issues/  contradictions/
```

Seed v1 **from `base_context.md`** using the taxonomy: one `entity` per §2 entity, one `metric`
per §4 formula, one `table` per §3 raw table, the §6 joins as `relationship`s, and K1–K7 as
`known-issue`s. Set `context_version: 1` in `overview.md`. **If the bundle already exists, do NOT
re-seed** — go to Step 2.

## Step 2 — Determine the trigger (state which fired)

| Trigger | How it arrives | What to update |
|---|---|---|
| **Schema change** (primary) | Instrumentation Agent created/changed a table (new `.sql`, or new live table) | Add/refresh the `table` concept + its `relationship`s + any new `metric` it enables |
| **Base-context seed** | First run / `base_context.md` changed | (Re)seed or reconcile against `base_context.md` |
| **Manual refresh** | "refresh the knowledge base" | Full reconcile: live schema ↔ bundle |
| **User assertion** | User states a definition/formula/entity/relationship in chat | Create/update the named concept; stamp `source: user` (+ who/when) |
| **Fold-back** | Analytics confirmed/refuted a claim or found a correlation | Update the relevant `metric` / `known-issue` / `contradiction` |

### Handling a direct user assertion

1. Identify the target concept and whether it already exists.
2. Validate against the live schema where possible (do the named columns/tables exist?).
3. **On conflict, do not silently overwrite** — either write a `contradiction` and ask which
   wins, or, if the user explicitly authorises, apply the change AND log the supersession.
4. Stamp `source: user` provenance so the trace shows a human origin.

## Step 3 — Gather sources (read before writing)

1. **Live ClickHouse schema** via the ClickHouse MCP:
   ```sql
   SELECT name, engine, sorting_key, partition_key FROM system.tables WHERE database = 'atlys';
   SELECT table, name, type FROM system.columns WHERE database = 'atlys' ORDER BY table, position;
   ```
2. The **new/changed DDL**: `Atlys/schemas/{schema_name}.sql` (if present).
3. **`base_context.md`** — authored, treat with suspicion (it lags the data).
4. **Existing bundle concepts** for the affected area — update, do not duplicate.
5. **The user's stated content** (assertion trigger), validated per Step 2.

> Pull schema/metadata only. Do **not** stream raw event rows into context.

## Step 4 — Diff and write concept docs (only what changed)

- **New table** → `/tables/{table}.md`: columns + types, ordering key, partitioning, TTL, MVs,
  and *what it measures*. Link the entities + metrics it touches. For the JSON-column design,
  note that fields live under `payload.*` and are queried via typed paths (e.g.
  ``payload.`payment.latency_ms` ``).
- **New/changed column** → update the owning `table`; add/adjust the relevant `/metrics/*.md` if
  it introduces a measurable.
- **New relationship** → `/relationships/*.md`: how the new table joins the funnel
  (`user_id`, `application_id`, timestamp order).
- **Metric touched** → update `/metrics/*.md` with the exact formula and denominator.

Every file: non-empty `type`; `timestamp` = today (ISO-8601); prefer lists/tables/short fenced
blocks; add bundle-relative links; one concept per file; never touch `index.md` / `log.md` here.

## Step 5 — Contradictions

Run the checklist and write `contradiction` concepts — see `atlys-contradiction-detection`.

## Step 6 — Version + changelog

Bump `context_version` and append a `log.md` entry — see `atlys-context-versioning`.

## Step 7 — Regenerate index + validate

If the `okf` CLI is available: `okf index "$KB_DIR"` then `okf validate "$KB_DIR"` (fix every
ERROR — usually a missing/empty `type`). Otherwise maintain `index.md` by hand (a grouped list
of links to every concept by type/folder) and self-check each file has a non-empty `type` and
valid frontmatter delimiters. Broken-link warnings are acceptable only if the target legitimately
does not exist yet.
