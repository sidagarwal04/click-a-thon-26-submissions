---
name: context-agent
description: Maintain and evolve the Atlys living context layer as an Open Knowledge Format (OKF) bundle under knowledge/. Use when the user says "update the context", "refresh the knowledge base", "run the context agent", "a new table landed — update context", "register this schema in the context layer", "maintain the context layer", "surface context contradictions", or after the Instrumentation Agent creates/changes a ClickHouse table. On activation the agent locates (or scaffolds) the OKF bundle at the mounted knowledge path, reads the live ClickHouse schema + any new DDL + base_context.md, creates/updates concept docs (entities, metrics, tables, relationships, known-issues) following the OKF rules in references/okf-docs.md, surfaces contradictions and gaps, bumps the context version, appends a changelog entry to log.md, regenerates index.md, validates the bundle, and optionally mirrors each version into a ClickHouse context_registry table.
---

# Context Agent — OKF Living Context Layer

## What this skill does

Given a **schema change** (a new/updated ClickHouse table from the Instrumentation
Agent), a **base-context seed**, or a **manual refresh** request, this skill keeps a
**living context layer** fresh so the Analytics Agent never reasons from a stale
snapshot. It:

1. **Maintains an OKF bundle** at the mounted knowledge path — one markdown concept
   file per business entity, metric, table, relationship, and known issue.
2. **Auto-updates context** when new tables/columns land — diffs the live schema
   against existing concepts and writes only what changed.
3. **Surfaces contradictions and gaps** in `base_context.md` (there are planted ones)
   as explicit `contradiction`-type concepts and log entries.
4. **Versions + changelogs** every update — bumps `context_version` and appends a
   dated diff entry to the reserved `log.md`, so freshness is provable in the trace.
5. **Feeds the Analytics Agent** the latest bundle (and optionally mirrors each
   version into a queryable ClickHouse `context_registry` table).

This satisfies Problem Statement **§3 Context Agent** and the *context freshness* /
*context diff / changelog* judging criteria.

> ⛓️ **Chained from `design-ch-schema`.** This skill is the downstream half of the
> instrumentation → context chain: after the `design-ch-schema` skill pushes a new
> `Atlys/schemas/{schema_name}.sql`, it activates this skill with the **"Schema change"**
> trigger (Step 2). It can therefore be invoked either automatically by that handoff or
> directly by the user ("update the context", "a new table landed — update context").

> 🔗 **Always load and apply**: the OKF rules in
> [`references/okf-docs.md`](references/okf-docs.md).
> Every file this skill writes must conform to that format. The summary below is
> operational; that file is the source of truth for OKF.

---

## OKF format

For the generic OKF standard — bundle layout, required `type` frontmatter, reserved
`index.md` / `log.md`, cross-link rules, and the `okf` commands — **defer to
[`references/okf-docs.md`](references/okf-docs.md)**. Read it
first; do not restate its rules. This skill only adds the **Atlys-specific** decisions
below (which concept types this bundle uses and how they map to the data).

> One rule worth repeating because it governs quality: **do not invent facts.** State
> only what the source (DDL, `base_context.md`, live schema, or Analytics findings)
> supports; mark unknowns explicitly.

### Concept types used in this bundle

| `type` | Folder | One file per |
|---|---|---|
| `overview` | `/overview.md` | the business + funnel summary (holds `context_version`) |
| `entity` | `/entities/` | user, application, destination, event, document, … |
| `metric` | `/metrics/` | one metric formula (conversion, drop-off, pass-rate, …) |
| `table` | `/tables/` | one raw or newly-instrumented ClickHouse table |
| `relationship` | `/relationships/` | a join / funnel-order relationship |
| `known-issue` | `/known-issues/` | K1–K7 and any new confirmed issue |
| `contradiction` | `/contradictions/` | a detected conflict or gap in the context |

See **[references/okf-concept-templates.md](references/okf-concept-templates.md)** for
the exact frontmatter + body template of each type, and
**[references/atlys-context-taxonomy.md](references/atlys-context-taxonomy.md)** for the
Atlys-specific seed taxonomy and the **contradiction/gap checklist**.

---

## Where the bundle lives (mount)

The bundle is a set of **local files**, edited through the **filesystem MCP** mounted
into LibreChat. Resolve the bundle root once:

```
KB_DIR = the mounted knowledge-bundle root
         • inside the LibreChat container (filesystem MCP): /app/knowledge
         • when run with repo shell access:                 knowledge/  (repo root)
```

> Prerequisite (one-time): bind-mount the repo `knowledge/` dir into the LibreChat
> `api` container and point `@modelcontextprotocol/server-filesystem` at
> `/app/knowledge` in `librechat.yaml`. This skill uses the filesystem MCP's
> `list_directory` / `read_file` / `write_file` tools for all bundle I/O; it does not
> assume the `okf` CLI is present (see Step 6 for the optional CLI path).

---

## Execution Overview

```
Resolve KB_DIR + ensure bundle scaffold exists                 ← Step 1
        │
Determine the trigger (new schema / seed / manual refresh)     ← Step 2
        │
Gather sources: live CH schema + new DDL + base_context.md      ← Step 3
        │
Diff → create/update concept docs (entities/metrics/tables/…)   ← Step 4
        │
Detect contradictions + gaps → write contradiction concepts     ← Step 5
        │
Bump context_version + append log.md changelog entry            ← Step 6
        │
Regenerate index.md + validate the bundle                       ← Step 7
        │
(optional) Mirror version into ClickHouse context_registry      ← Step 8
        │
(optional) Commit + PR                                          ← Step 9
```

---

## Step 1 — Resolve `KB_DIR` and ensure the scaffold

`list_directory` on `KB_DIR`. If the bundle is missing or empty, **scaffold it**:

```
knowledge/
├── overview.md                 (type: overview — holds context_version: 1)
├── log.md                      (reserved — changelog; first entry = "bundle created")
├── index.md                    (reserved — regenerated in Step 7)
├── entities/
├── metrics/
├── tables/
├── relationships/
├── known-issues/
└── contradictions/
```

Seed the first version **from `base_context.md`** using the taxonomy in
[references/atlys-context-taxonomy.md](references/atlys-context-taxonomy.md): one
`entity` per §2 entity, one `metric` per §4 formula, one `table` per §3 raw table, the
§6 joins as `relationship` concepts, and K1–K7 as `known-issue` concepts. Set
`context_version: 1` in `overview.md`.

> If the bundle already exists, **do not re-seed** — go straight to Step 2 and update.

---

## Step 2 — Determine the trigger

| Trigger | How it arrives | What to update |
|---|---|---|
| **Schema change** (primary) | Instrumentation Agent created/changed a table (new `.sql` in `Atlys/schemas/`, or a new table in the live DB) | Add/refresh the `table` concept + its `relationship`s + any new `metric` it enables |
| **Base-context seed** | First run / `base_context.md` changed | (Re)seed or reconcile concepts against `base_context.md` |
| **Manual refresh** | User asks to "refresh the knowledge base" | Full reconcile: live schema ↔ bundle |
| **User assertion** (direct edit) | User states a business definition, metric formula, entity, or relationship in chat and asks to record/change it | Create/update the exact concept the user named; set `source: user` + who/when |
| **Fold-back** | Analytics Agent confirmed/refuted a claim or found a new correlation | Update the relevant `metric` / `known-issue` / `contradiction` |

State which trigger fired before proceeding — it scopes the work.

### 2a — Handling a direct **user assertion**

When the user supplies the content themselves (not derived from schema/`base_context.md`):

1. **Identify the target concept** (which entity/metric/relationship/table) and whether
   it already exists in the bundle.
2. **Validate before accepting** where possible — check the assertion against the live
   schema (do the named columns/tables exist?) and existing concepts.
3. **On conflict, do not silently overwrite.** If the user's assertion contradicts an
   existing concept or `base_context.md`, either (a) write/refresh a
   `contradiction` concept and ask the user to confirm which wins, or (b) if the user
   explicitly authorises the change, apply it **and** log the supersession.
4. **Stamp provenance** on the written concept: `source: user` (plus who/when if known),
   so the trace shows the definition came from a human, not the data.
5. Proceed through Steps 4–7 as normal (write concept → version bump → log → index).

---

## Step 3 — Gather sources (read before writing)

1. **Live ClickHouse schema** (via the ClickHouse MCP the other agents use):
   ```sql
   SELECT name, engine, sorting_key, partition_key
   FROM system.tables WHERE database = 'atlys';

   SELECT table, name, type
   FROM system.columns WHERE database = 'atlys' ORDER BY table, position;
   ```
2. **The new/changed DDL** for the triggering table, if a file exists:
   `Atlys/schemas/{schema_name}.sql`.
3. **`base_context.md`** — the authored context (treat with suspicion; it lags data).
4. **Existing bundle concepts** for the affected area — so you update, not duplicate.
5. **The user's stated content** (User-assertion trigger) — the definition / formula /
   relationship the user gave in chat, treated as an authoritative source to record
   (validated per Step 2a).

> Pull **schema/metadata only** here. Do **not** stream raw event rows into context —
> that is the Analytics Agent's job, and only aggregates, never raw rows.

---

## Step 4 — Diff and write concept docs

For each affected area, **diff** the source against the current bundle and write **only
what changed**:

- **New table** → create `/tables/{table}.md` (`type: table`): columns + types,
  ordering key, partitioning, TTL, MVs, and *what it measures*. Link the entities and
  metrics it touches.
- **New/changed column** → update the owning `table` concept; if it introduces a new
  measurable, add/adjust the relevant `/metrics/*.md`.
- **New relationship** → `/relationships/*.md` (`type: relationship`): how the new
  table joins the funnel/supporting tables (`user_id`, `application_id`, timestamp
  order).
- **Metric touched** → update `/metrics/*.md` with the exact formula and denominator.

Rules for every file written:
- Keep a **non-empty `type`**; set `timestamp` to today (ISO-8601).
- Prefer **lists, tables, short fenced blocks** over prose.
- Add **bundle-relative links** to related concepts.
- Focus each file on **one concept**; never touch `index.md` / `log.md` here.

---

## Step 5 — Surface contradictions and gaps

Run the **contradiction/gap checklist** in
[references/atlys-context-taxonomy.md](references/atlys-context-taxonomy.md). For each
finding, write a `/contradictions/{slug}.md` concept (`type: contradiction`) stating:
the **claim**, the **conflicting claim / evidence**, **where** each came from, and a
**recommended resolution** — do not silently pick a winner.

Known planted examples to always check (non-exhaustive):
- **Dual "conversion" definition** — `base_context.md` §4 headline (*purchases ÷
  sessions*) vs the §4 note (*purchase_completed ÷ application_started*).
- **`os = NULL` while `device_type = 'android'`** — envelope data gap.
- **Legacy `ORDER BY (id, timestamp, user_id)`** — queries filter by time/segment,
  never `id`; flag as a schema smell the Instrumentation Agent should not copy.
- **On-time delivery / `visa_issuance_eta_days`** — referenced as a metric but declared
  post-purchase and *not computable* from the funnel tables → gap.

Cross-link each contradiction from the concept(s) it affects.

---

## Step 6 — Version bump + changelog (`log.md`)

1. **Bump** `context_version` in `overview.md` frontmatter (`N → N+1`).
2. **Append** an entry to the reserved `log.md` (newest first):

```markdown
## v{N+1} — {ISO-8601 datetime} — {trigger}
- added: /tables/{table}.md, /relationships/{...}.md
- updated: /metrics/conversion-rate.md (denominator clarified)
- contradictions: /contradictions/{slug}.md (dual conversion definition)
- source: Atlys/schemas/{schema_name}.sql + live atlys schema
```

The version + trigger + file list is what makes freshness **provable in the Langfuse
trace** ("no stale snapshot" is demonstrable).

---

## Step 7 — Regenerate index + validate

If the `okf` CLI is available (shell/execute_code), prefer it:

```bash
okf index "$KB_DIR"        # regenerate index.md navigation
okf validate "$KB_DIR"     # fix every reported ERROR (usually a missing/empty type)
```

If only the filesystem MCP is available, **maintain `index.md` by hand**: a grouped
list of links to every concept by type/folder. Then self-check each written file has a
non-empty `type` and valid frontmatter delimiters. Broken-link warnings are acceptable
only if the target legitimately does not exist yet.

---

## Step 8 — (Optional) Mirror to ClickHouse `context_registry`

Only if queryable lineage is wanted (lets the Analytics Agent fetch "current context
version" over the ClickHouse MCP). Files remain the **source of truth**; this is a
mirror.

```sql
CREATE TABLE IF NOT EXISTS atlys.context_registry
(
    context_version  UInt32,
    updated_at       DateTime64(3, 'UTC') DEFAULT now64(3),
    trigger          LowCardinality(String),
    concept_path     String,
    change_kind      LowCardinality(String),   -- added | updated | contradiction
    summary          String,
    body_md          String
)
ENGINE = MergeTree
PARTITION BY context_version
ORDER BY (context_version, concept_path);
```

Insert one row per changed concept for the new version. Skip this step entirely if
files-only is the chosen design.

---

## Step 9 — (Optional) Commit + PR

Only when explicitly requested **and** shell/git is available (the pure LibreChat
filesystem-MCP path just writes files — no git). Mirrors the sibling skill:

```bash
# Same portable env vars as the design-ch-schema skill (defaults shown).
CH_TARGET_REPO="${CH_TARGET_REPO:-https://github.com/srinidhi-22/tillthelastrow.git}"
CH_TARGET_BRANCH="${CH_TARGET_BRANCH:-master}"
CH_REPO_SLUG="$(echo "${CH_TARGET_REPO%.git}" | sed -E 's#https?://[^/]+/##')"

cd "$REPO_DIR"
git checkout "$CH_TARGET_BRANCH" && git pull --ff-only origin "$CH_TARGET_BRANCH"
EPOCH=$(date +%s)
git checkout -b context/update-v{N+1}-${EPOCH}
git add knowledge/
git commit -m "chore(context): update living context to v{N+1} ({trigger})"
git push --set-upstream origin context/update-v{N+1}-${EPOCH}
gh pr create --repo "$CH_REPO_SLUG" --base "$CH_TARGET_BRANCH" \
  --head context/update-v{N+1}-${EPOCH} \
  --title "chore(context): living context v{N+1}" \
  --body "Context bump to v{N+1}. See knowledge/log.md for the diff."
```

Report the PR URL when done.

---

## Constraints (always enforce)

- **Always** conform to OKF per [`references/okf-docs.md`](references/okf-docs.md):
  every concept file keeps a **non-empty `type`**; `index.md` and `log.md` are reserved.
- **Only** create/edit files inside `KB_DIR`. **Never modify source code or specs.**
- **Always** read the live schema + `base_context.md` + existing concepts **before**
  writing — update, do not duplicate.
- **Always** bump `context_version` and append a `log.md` entry on every change — a
  silent update is a stale-context bug.
- **Always** surface contradictions as explicit `contradiction` concepts; never
  silently resolve a conflict in `base_context.md`.
- **Never** pull raw event rows into context — schema/metadata only.
- **Never** invent facts; mark unknowns. Keep one concept per file.
- **Never** overwrite a concept wholesale when a targeted edit suffices.

---

## Quick Reference: Repo Layout

```
tillthelastrow/
├── Atlys/
│   ├── base_context.md              ← authored seed (imperfect — treat with suspicion)
│   └── schemas/{schema_name}.sql    ← Instrumentation Agent output (schema-change trigger)
├── knowledge/                       ← ✅ OUTPUT: the OKF living context bundle (KB_DIR)
│   ├── overview.md   (context_version)
│   ├── log.md        (changelog — reserved)
│   ├── index.md      (nav — reserved, regenerated)
│   ├── entities/  metrics/  tables/  relationships/  known-issues/  contradictions/
└── skill/
    └── context-agent/               ← this skill
        ├── SKILL.md
        └── references/
            ├── okf-docs.md               ← OKF standard (moved here)
            ├── okf-concept-templates.md
            └── atlys-context-taxonomy.md
```
