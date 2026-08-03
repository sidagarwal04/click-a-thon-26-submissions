---
name: design-ch-schema
description: Onboard a product/spec into ClickHouse by generating a production-ready DDL schema from its NDJSON events file. Use when a user says "onboard product in clickhouse", "onboard this spec into clickhouse", "onboard product to clickhouse", "design a ClickHouse schema from this ndjson", "generate CH DDL from these events", or "instrument this ndjson into ClickHouse". On activation the agent asks three questions — (1) the spec name, (2) the frequently-filtered field(s), (3) the metrics most commonly fetched from this spec — then applies the clickhouse-best-practices skill and generates a single-JSON-column table under the atlys database (typed hints only for ORDER BY / PARTITION BY paths), a ch_insert_time MATERIALIZED column, a CREATE DATABASE guard, and materialized views when warranted. Validates locally with chdb, tests on ClickHouse Cloud, then commits and raises a PR. After pushing, it chains into the `context-agent` skill (installing it if absent) to refresh the OKF living-context bundle for the new schema.
---

# ClickHouse Schema Design — NDJSON → JSON-Column DDL

## What this skill does

Given an **NDJSON file** of raw events, this skill generates a production-ready
ClickHouse DDL file containing:

1. A `CREATE DATABASE IF NOT EXISTS <db>` guard so the DDL is self-contained.
2. **Exactly ONE base table per spec** — every event type in the NDJSON is inserted into
   this single table. It is designed as:
   - a **single `JSON` column named `payload`** holding the whole event object (all event
     types share it),
   - with **typed sub-column hints** declared **only** for the paths used in
     `ORDER BY` / `PARTITION BY` — including the **event-type discriminator** at
     `payload.event` (or `payload.type`/`payload.name`), typed `LowCardinality(String)`,
   - plus a **`ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3)`** column
     used for partitioning and TTL.
3. **Optionally, materialized views (MVs)** — only when the derivation logic in
   Step 2d (driven by the NDJSON profile + the feature `spec.md`) concludes an MV is
   justified. MVs read from the single base table and **filter by `payload.event`** when a
   metric applies to only some event types.

This is a **schema-agnostic**, **one-table-per-spec** design: the `payload` JSON column
absorbs the union of every event type's fields, so the DDL does not break when new fields or
event types appear. Only the handful of paths needed for the sort/partition key are typed,
and the **ORDER BY key is capped at 4–5 columns** (see Step 3c).

### Portable configuration (environment variables)

This skill is portable across users and forks. The following env vars are read at runtime
(defaults in parentheses); everything else is derived from them or asked in Step 1:

| Env var | Purpose | Default |
|---|---|---|
| `CH_TARGET_REPO` | Git repo (URL) the schema is committed to | `https://github.com/srinidhi-22/tillthelastrow.git` |
| `CH_TARGET_BRANCH` | Base branch to branch from and open the PR against | `master` |
| `CH_REPO_DIR` | Local clone directory | `$HOME/<repo-name>` |
| `CH_DATABASE` | ClickHouse database all tables/MVs live under | `atlys` |
| `CH_HOST`, `CH_USER`, `CH_PASSWORD` | ClickHouse Cloud credentials for the smoke test | (required at Step 6) |

A user on another device only needs to export the vars that differ from these defaults.

> 🔗 **Always load and apply**: [`clickhouse-best-practices` skill](https://github.com/ClickHouse/agent-skills/blob/main/skills/clickhouse-best-practices/SKILL.md)
>
> Before writing any DDL, fetch and internalize that skill. Every decision (JSON usage,
> ORDER BY column order low→high cardinality, LowCardinality hints, avoiding Nullable in
> keys, partition-count bounds, codec choice) must be consistent with its rules, and every
> design choice in the output should cite the rule that justifies it
> (`schema-json-when-to-use`, `schema-pk-cardinality-order`, `schema-partition-lifecycle`, …).

---

## Reference design (the pattern to emulate)

The generated DDL uses plain `MergeTree` for **ClickHouse Cloud**
(no Replicated / Distributed / storage_policy):

```sql
CREATE DATABASE IF NOT EXISTS <db>;

-- ONE base table per spec; all event types insert here.
CREATE TABLE IF NOT EXISTS <db>.<spec_table>
(
    payload JSON(
        event          LowCardinality(String),   -- the event-type discriminator
        <path_a>        LowCardinality(String),   -- a frequently-filtered dim (Q2)
        <path_b>        LowCardinality(String),
        user_id         String,
        timestamp       DateTime64(3, 'UTC')      -- the event's OWN timestamp path
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
-- ORDER BY: 4–5 columns max — discriminator first, then frequent filters, user_id, timestamp last.
ORDER BY (payload.event, payload.<path_a>, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1;
```

Design rules (because the target is **ClickHouse Cloud**):

| Concern | This skill (ClickHouse Cloud) |
|---|---|
| Engine | plain `MergeTree` — never `ReplicatedMergeTree` or replication macros |
| Distribution | **omit** any `..._distributed` `Distributed(...)` table — Cloud handles it |
| Storage tiering | **omit** `storage_policy` — Cloud-managed |
| Extra top-level columns | **omit** unless the path is present in the NDJSON |
| Ingestion watermark | **keep** `ch_insert_time MATERIALIZED now64(3)` — required |
| Partitioning | **keep** `PARTITION BY toYYYYMMDD(ch_insert_time)` |
| Retention | **keep** `TTL ... + INTERVAL 90 DAY DELETE` (default 90d; a Step 1 input) |

---

## Execution Overview

```
Ask 3 onboarding questions: spec name, frequent filters, common metrics   ← Step 1
        │
        ▼
Resolve spec folder → events.ndjson + spec.md
        │
        ▼
Read the NDJSON and the feature spec.md
        │
        ▼
Detect the event-type discriminator + union-scan ALL fields across event types
        │
        ▼
Apply clickhouse-best-practices skill    ← JSON usage, key ordering, LowCardinality, TTL
        │
        ▼
Pick ORDER BY (≤5 cols): discriminator + frequent_filters (Q2) + user_id + timestamp last
        │
        ▼
Derive MV need from common_metrics (Q3) + spec.md + NDJSON profile   ← Step 2d logic
        │
        ▼
Draft DDL: CREATE DATABASE + ONE base table per spec (payload JSON column) + ch_insert_time
          (+ MVs reading from that table, filtered by payload.event, only if derivation says yes)
        │
        ▼
Validate locally with chdb               ← CREATE → INSERT raw NDJSON row → SELECT → assert
        │  (fix & retry on any error)
        ▼
Test on ClickHouse Cloud                 ← run the exact same DDL, insert a real row
        │  (fix & retry on any error)
        ▼
Write final .sql file
        │
        ▼
Git: branch from master → commit → push → PR
        │
        ▼
Hand off to context-agent skill          ← Step 9: schema-change trigger refreshes knowledge/
   (install it first if not present)
```

---

## Step 0 — Prerequisites (automated checks)

Run all checks automatically. Do NOT wait for the user — execute and fix issues automatically.

### 0a — Check & Install `gh` CLI

```bash
if ! command -v gh &>/dev/null; then
  if command -v brew &>/dev/null; then
    brew install gh
  elif command -v apt-get &>/dev/null; then
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) \
      signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
      https://cli.github.com/packages stable main" \
      | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt-get update && sudo apt-get install gh -y
  else
    echo "ERROR: install gh CLI manually: https://cli.github.com/" && exit 1
  fi
fi
echo "gh version: $(gh --version | head -1)"
```

### 0b — Authenticate `gh` CLI

The target repo determines **which GitHub host** `gh` must be authenticated against. A very
common failure is `gh` being logged into an **enterprise** host (e.g.
`github.dev.global.tesco.org`) while the target repo lives on **github.com** — `gh pr create`
then fails. Resolve the required host from `CH_TARGET_REPO` and check auth against *that* host.

```bash
# Derive the git host from the target repo URL (default github.com)
CH_TARGET_REPO="${CH_TARGET_REPO:-https://github.com/srinidhi-22/tillthelastrow.git}"
GH_TARGET_HOST="$(echo "$CH_TARGET_REPO" | sed -E 's#^[a-z]+://([^/]+)/.*#\1#; s#^git@([^:]+):.*#\1#')"
[ -z "$GH_TARGET_HOST" ] && GH_TARGET_HOST="github.com"
export GH_TARGET_HOST

if ! gh auth status --hostname "$GH_TARGET_HOST" &>/dev/null; then
  echo "⚠️  gh is not authenticated to $GH_TARGET_HOST (it may be logged into a different/enterprise host)."
  echo "   Attempting web login to $GH_TARGET_HOST …"
  gh auth login --hostname "$GH_TARGET_HOST" --git-protocol https --web || true
fi
gh auth status --hostname "$GH_TARGET_HOST" || \
  echo "NOTE: could not authenticate to $GH_TARGET_HOST — Step 8 will fall back to printing the PR URL."
```

If auth to `$GH_TARGET_HOST` still cannot be established, the branch/commit/push still work;
Step 8 will detect this and print a ready-to-click PR URL instead of failing.

### 0c — Clone or update the target repo (never read from a pre-existing local path)

The skill operates **only** on a clone of the target repo that it manages itself under
`$REPO_DIR`. It must **never** assume the user already has the repo checked out somewhere, and
must **never** read the spec/NDJSON from any other local path. If `$REPO_DIR` does not already
contain this repo, **clone it first**; only then read inputs and write outputs — all under
`$REPO_DIR`.

The target repo and its base branch are **configurable** via environment variables so the
skill is portable across users and forks. Defaults are shown below; override by exporting
`CH_TARGET_REPO` and/or `CH_TARGET_BRANCH` (or ask the user for them if unset).

```bash
# Configurable — override via env, else use these defaults
CH_TARGET_REPO="${CH_TARGET_REPO:-https://github.com/srinidhi-22/tillthelastrow.git}"
CH_TARGET_BRANCH="${CH_TARGET_BRANCH:-master}"

# Derive a local clone dir from the repo name
REPO_NAME="$(basename "${CH_TARGET_REPO%.git}")"
REPO_DIR="${CH_REPO_DIR:-$HOME/$REPO_NAME}"
export REPO_DIR CH_TARGET_REPO CH_TARGET_BRANCH

# 1. Clone if we don't already have THIS repo at $REPO_DIR.
if [ -d "$REPO_DIR/.git" ] && \
   git -C "$REPO_DIR" remote get-url origin 2>/dev/null | grep -q "$REPO_NAME"; then
  echo "Reusing existing clone at $REPO_DIR"
else
  # $REPO_DIR is missing or is not this repo — (re)clone into a clean location.
  if [ -e "$REPO_DIR" ] && [ ! -d "$REPO_DIR/.git" ]; then
    REPO_DIR="${REPO_DIR}-ch-schema"   # avoid clobbering an unrelated directory
    export REPO_DIR
  fi
  echo "Cloning $CH_TARGET_REPO → $REPO_DIR"
  git clone "$CH_TARGET_REPO" "$REPO_DIR"
fi

# 2. Sync the base branch to a clean, up-to-date state.
cd "$REPO_DIR"
git fetch origin --prune
git checkout "$CH_TARGET_BRANCH"
git pull --ff-only origin "$CH_TARGET_BRANCH"
echo "Repo ready at: $REPO_DIR on branch $CH_TARGET_BRANCH"
```

All subsequent input reads (spec/NDJSON), file writes (the `.sql`), and git commands run from
`$REPO_DIR` — never from any other local copy of the repo. The feature branch is created in
Step 7 and the PR (Step 8) is opened against `$CH_TARGET_BRANCH`.

### 0d — Check & Install `chdb`

`chdb` must support the `JSON` type — install/upgrade to a recent version.

```bash
if ! python3 -c "import chdb" &>/dev/null; then
  pip3 install --upgrade chdb
fi
python3 -c "import chdb; print('chdb version:', chdb.__version__)"
```

> The `JSON` type is a modern ClickHouse type. If chdb rejects `JSON(...)` typed hints,
> upgrade chdb (`pip3 install --upgrade chdb`) before treating it as a DDL error.

---

## Step 1 — Onboarding Questions

This skill runs the **ClickHouse product-onboarding** flow. All tables and MVs live under a
**single database**, resolved once at the start:

```bash
CH_DATABASE="${CH_DATABASE:-atlys}"   # configurable; default 'atlys'
```

Set `ch_database = $CH_DATABASE`. Everywhere this document writes the literal `atlys`
(DDL, validation, PR body, examples), substitute the resolved `ch_database` value. Do NOT
ask the user for a database name interactively unless `CH_DATABASE` is unset **and** there
is no sensible default — the default `atlys` is used otherwise. Never create any database
other than the resolved `ch_database`.

On activation, **ask the user these three questions first** (they drive spec resolution,
ORDER BY ordering, and MV derivation respectively):

| # | Question | Variable | Drives |
|---|----------|----------|--------|
| 1 | **What is the spec name?** (e.g. `01_express_checkout`) | `spec_name` | Locates the spec folder `Atlys/specs/{spec_name}/` → its `events.ndjson` + `spec.md`; also the default `schema_name` and output file `Atlys/schemas/{spec_name}.sql` |
| 2 | **What field(s) are most frequently filtered?** (e.g. `application_id`, `channel`) | `frequent_filters` | The leftmost ORDER BY columns (Step 3c) — frequently-filtered + LowCardinality go first |
| 3 | **What metrics are most commonly fetched from this spec?** (e.g. `count of completions`, `p95 payment latency`) | `common_metrics` | MV derivation Signal A (Step 2d) — each metric is a candidate rollup |

Resolve the inputs from the answers:

```
spec_name        → provided by the user (Q1)
ndjson_path      = $REPO_DIR/Atlys/specs/{spec_name}/events.ndjson
spec_md_path     = $REPO_DIR/Atlys/specs/{spec_name}/spec.md
schema_name      = {spec_name}            (output → $REPO_DIR/Atlys/schemas/{spec_name}.sql)
frequent_filters → provided by the user (Q2)  — used in Step 3c ORDER BY
common_metrics   → provided by the user (Q3)  — used in Step 2d MV derivation
```

> All paths above resolve **inside the clone at `$REPO_DIR`** (created in Step 0c). The skill
> never reads the NDJSON/spec from any other local location — if the repo isn't cloned yet,
> Step 0c clones it first.

Also confirm (do not block on these — use sensible defaults):

| Input | Variable | Default |
|---|---|---|
| **ClickHouse Cloud credentials** — host, user, password (or env `CH_HOST`, `CH_USER`, `CH_PASSWORD`) | `ch_credentials` | read from env |
| **TTL in days** for `ch_insert_time` retention | `ttl_days` | `90` |

> The user's Q2 (frequent filters) and Q3 (common metrics) are **first-class design signals**:
> Q2 overrides the default ORDER BY ordering when it names a dominant filter; Q3 is the
> primary input to the "is an MV needed?" derivation, cross-checked against the NDJSON.

---

## Step 2 — Read & Profile the NDJSON + Spec

**Automatically** read and profile both inputs before writing any DDL. Do NOT ask the user
to summarise — parse them directly.

### 2a — Read the NDJSON and its sibling `spec.md`

Using the `spec_name` from Step 1 Q1, resolve the spec folder and read **both** files — the
NDJSON drives the table shape; the `spec.md` (with the user's Q3 metrics) drives whether an
MV is needed.

All specs live under `$REPO_DIR/Atlys/specs/` in the cloned repo (on branch
`$CH_TARGET_BRANCH`, default `master`) — e.g.
`https://github.com/srinidhi-22/tillthelastrow/tree/master/Atlys/specs`. Resolve the folder
there; if the named spec is missing, list what IS available and stop.

```bash
SPEC_DIR="$REPO_DIR/Atlys/specs/{spec_name}"
NDJSON="$SPEC_DIR/events.ndjson"
SPEC_MD="$SPEC_DIR/spec.md"

# Guard: the spec must exist under the cloned repo's Atlys/specs/
if [ ! -f "$NDJSON" ]; then
  echo "❌ Spec '{spec_name}' not found at $SPEC_DIR/events.ndjson"
  echo "   Available specs under $REPO_DIR/Atlys/specs/:"
  ls -1 "$REPO_DIR/Atlys/specs/" 2>/dev/null || echo "   (none — is the repo cloned & on $CH_TARGET_BRANCH?)"
  exit 1
fi

# The NDJSON (required)
wc -l "$NDJSON"
head -20 "$NDJSON"

# The spec.md in the SAME folder (may be absent — handle gracefully)
if [ -f "$SPEC_MD" ]; then
  cat "$SPEC_MD"
else
  echo "No spec.md for {spec_name} — MV derivation will rely on the user's Q3 metrics + NDJSON profile only."
fi
```

> Example layout: for `spec_name = 01_express_checkout`, the inputs are
> `Atlys/specs/01_express_checkout/events.ndjson` and `Atlys/specs/01_express_checkout/spec.md`.

### 2b — Profile every event type dynamically

Drive everything from the file. The agent runs (mentally / via a scratch script) the
following profiling to discover the structure — there is **no hardcoded schema**:

1. **Detect the event-type discriminator key** (commonly `event`, `type`, or `eventType`)
   and list its distinct values (the event types). This does **not** create multiple tables —
   there is **exactly ONE base table for the whole spec**. The discriminator becomes a typed
   path (`payload.event`) used in `ORDER BY` and in MV filters. If no discriminator exists,
   the single table simply has no discriminator path in its key.
2. **Union-scan ALL rows across ALL event types** — collect every JSON path that appears
   anywhere in the file (top-level and nested), plus, for each path, its value samples,
   whether it is ever null/absent (paths that only some event types emit ARE expected — the
   `payload` column absorbs them), and its approximate distinct-value count.
3. **Common identity paths — always present.** `user_id` and `application_id` appear on
   **every** event. Treat them as guaranteed, non-null typed paths available to `ORDER BY`.
   `user_id` is high-cardinality; `application_id` is typically low/medium-cardinality.
4. **Locate the event's own timestamp path** — the field holding the event time
   (e.g. `timestamp`, `ts`, `eventTime`). This becomes the last element of `ORDER BY`.
5. **Rank candidate ORDER BY paths** using the ordering preference in Step 3c, then **cap the
   key at 4–5 columns**: discriminator first, then the frequently-filtered LowCardinality dims
   (Q2), then `user_id`, then the timestamp last.
6. **Flag metric paths** — numeric paths (amounts, latencies, durations, counts) and the
   event types that carry them (e.g. only `express_payment_confirmed` has `payment.*`). These
   feed the MV derivation in Step 2d; an MV that targets such a metric filters by
   `payload.event` for the relevant event type(s).

### 2c — Output a profile summary before proceeding

```
📋 NDJSON profile: {ndjson_path}
─────────────────────────────────────────────────
✦ Rows scanned          : {N}
✦ Spec.md               : {found / not found}
✦ Event discriminator   : {payload.<key>, or "none"}
✦ Event types (in table): {list of distinct event types — ALL share one base table}
✦ Base table name       : {spec_table}
✦ Union of all paths    : {count} paths across all event types
✦ Timestamp path        : {path chosen for ORDER BY tail}
✦ ORDER BY (≤5 cols)    : {discriminator, frequent dims, user_id, timestamp}
✦ Paths to TYPE in hint : {only ORDER BY / PARTITION BY paths}
✦ Numeric metric paths  : {candidate aggregation targets + which event type carries them}
✦ All other paths       : absorbed by the untyped `payload` JSON column
─────────────────────────────────────────────────
Proceeding to MV-need derivation (Step 2d).
```

### 2d — Derive whether a Materialized View is needed

An MV is a **pre-aggregated rollup** over the raw JSON-column table. It is only worth
creating when the feature is answered by **repeated aggregate queries**, not by raw-row
lookups. Derive the decision from **two signals**:

**Signal A — the user's `common_metrics` answer (Q3) + the `spec.md` analytical questions.**
The metrics the user named in Step 1 Q3 are the primary source; corroborate and extend them
with phrases in `spec.md`. Scan both for aggregation over time or dimensions:

| Metric / phrase (from Q3 or spec.md) | MV signal |
|---|---|
| "conversion rate", "funnel", "drop-off across steps" | ✅ strong — ratio/count MV |
| "p50 / p95 / p99", "percentile", "latency distribution" | ✅ strong — quantile MV |
| "per {dimension} over time", "hourly/daily trend of …" | ✅ strong — time-bucketed rollup MV |
| "top N by …", "count/sum of … grouped by …" | ✅ moderate — count/sum MV |
| "average … by …" | ✅ moderate — avg MV |
| "show the raw events", "look up a single record", "debug one session" | ❌ none — raw table is enough |

> Each metric named in Q3 maps to one candidate MV. If the user named no metrics **and** the
> spec has no aggregation questions, Signal A is negative.

**Signal B — the NDJSON profile.** An MV is only feasible if the payload actually contains
the ingredients:

- at least one **numeric metric path** (for avg/sum/quantile MVs), OR a countable event
  (for count/ratio MVs), **and**
- at least one **low-cardinality dimension path** to GROUP BY, **and**
- the event **timestamp path** (to bucket by hour/day).

**Decision rule (both must hold to propose an MV):**

```
MV_NEEDED = (user Q3 metrics OR spec.md aggregation questions — Signal A ✅)
            AND
            (NDJSON has the metric/dimension/timestamp to satisfy it — Signal B ✅)
```

If the derivation says **yes**, record for each proposed MV: the **single base table** as
source, a `WHERE payload.event = '<type>'` filter if the metric applies to only some event
types, the time bucket (`toStartOfDay` / `toStartOfHour`), the GROUP BY dimension paths, and
the aggregate function + metric path. Follow **[references/materialized-views.md](references/materialized-views.md)**
to generate the backing table + MV in Step 3f.

**Always generate incremental `AggregatingMergeTree` MVs that fire on insert — never a
refreshable (`REFRESH EVERY`) MV** for these metrics. An incremental MV aggregates only each
newly inserted block into partial states and **never rescans the base table**, so cost scales
with insert size, not table size — this is the performant choice for a growing event table.
`toStartOfDay`/`toStartOfHour` is just the bucket granularity, **not** a refresh schedule; a
day-bucketed incremental MV still updates continuously as rows arrive. Only fall back to a
refreshable MV when the aggregation genuinely cannot be incremental — JOINs across tables,
dedup/`argMax` over full history, top-N/window functions, or any metric that must rescan the
whole base table. The standard funnel-count / latency-quantile / sum metrics never need this.

If the derivation says **no** (raw-lookup feature, missing metrics, or no `spec.md`
justification), **do not create any MV** — note the reason and proceed with tables only.

### 2e — Output the MV derivation verdict

```
🧮 MV derivation
─────────────────────────────────────────────────
Signal A (Q3 metrics + spec.md) : {user metrics + matched phrases, or "no aggregation asks"}
Signal B (NDJSON ingredients)   : metric paths={...}; dimensions={...}; timestamp={...}
Verdict                         : {MV NEEDED — list proposed MVs  |  NO MV — reason}
─────────────────────────────────────────────────
Proceeding to DDL design (ONE base table, `payload` JSON column + ch_insert_time{ + MVs if needed}).
```

---

## Step 3 — Design the DDL

Apply all rules from the **`clickhouse-best-practices`** skill. The fixed shape:

### 3a — Database guard (always first, once per file)

```sql
CREATE DATABASE IF NOT EXISTS atlys;
```

### 3b — ONE base table per spec

Emit a **single** `CREATE TABLE` for the whole spec. All event types insert into it; the
`payload` JSON column absorbs the union of their fields.

```sql
CREATE TABLE IF NOT EXISTS atlys.{spec_table}
(
    payload JSON(
        event            LowCardinality(String),    -- event-type discriminator
        application_id   LowCardinality(String),    -- common to all events; low-card
        {orderby_path_2} LowCardinality(String),    -- frequently-filtered dim (Q2)
        user_id          String,                     -- common to all events; high-card
        {timestamp_path} DateTime64(3, 'UTC')        -- event's own time; ORDER BY tail
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY ({orderby_expr})
TTL toDateTime(ch_insert_time) + INTERVAL {ttl_days} DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1;
```

- `{spec_table}` defaults to `{spec_name}` (e.g. `express_checkout`).
- `{orderby_expr}` references typed paths through the `payload` column, **capped at 4–5
  columns**, e.g. `payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp`.
- The type-hint list only needs the paths that appear in `{orderby_expr}` — never type the
  rest of the payload.

### 3c — ORDER BY column-ordering preference (apply strictly)

Order the key from **left to right** by these preferences, then **cap the total at 4–5
columns**:

1. **Event-type discriminator first (leftmost).** `payload.event` is LowCardinality and is
   the field most queries filter on to pick an event type, so it leads the key. (Omit only if
   the NDJSON has no discriminator.)
2. **The user's `frequent_filters` answer (Q2) next.** The LowCardinality dims the user named
   as most frequently filtered, in their stated order.
3. **Then `user_id`** (higher-cardinality identity).
4. **Timestamp path last.**

Because `application_id` (low-card) and `user_id` (high-card) are on every event, the typical
resulting key is:

```
ORDER BY (payload.event, payload.{frequent_filter_1}, payload.user_id, payload.{timestamp_path})
```

e.g. `ORDER BY (payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp)`.

**Hard cap: 4–5 columns.** If the discriminator + Q2 filters + user_id + timestamp would
exceed 5, drop the lowest-priority middle dims (keep discriminator, the single most-filtered
Q2 dim, and timestamp). Only diverge from Q2 if a named field is Nullable/absent from some
rows (it cannot be a key) — fall back to the next candidate and note why in a `--` comment.
**Never** place a Nullable path in the key.

### 3c-rules — Design rules (enforced; cite best-practices)

| Rule | Requirement | Best-practices rule |
|---|---|---|
| ONE table per spec | Emit **exactly one** base table for the whole spec; every event type inserts into it. Do NOT create a table per event type. | `schema-json-when-to-use` |
| Single JSON column | Name it `payload`; it holds the **entire** event object. The event-type discriminator is exposed as the typed path `payload.event` and used in ORDER BY + MV filters. The insert data pipeline wraps each raw row as `{"payload": <row>}`. | `schema-json-when-to-use` |
| Typed hints | Declare typed sub-columns **only** for paths in ORDER BY / PARTITION BY — never type the whole payload | `schema-json-when-to-use` |
| String literals | Type-modifier strings and value literals use **single quotes only** — write `DateTime64(3, 'UTC')`, `'express_checkout_shown'`. **Never** wrap a literal in escaped double quotes like `'"UTC"'` or `'"express_checkout_shown"'`. This is invalid ClickHouse SQL and is the most common generation bug — chdb validation (Step 5) MUST catch it before commit. | `schema-types-native-types` |
| Sparse paths are EXPECTED | Because all event types share one table, many payload paths (`shown_amount`, `otp_attempts`, `payment.*`, …) are present only for some event types. This is **not** an error — the untyped `payload` column absorbs them; MVs that need them filter by `payload.event`. | `schema-json-when-to-use` |
| Common identity | `user_id` (String) and `application_id` (LowCardinality(String)) are on every event; always typed and available to ORDER BY | — |
| Timestamp | Use the **event's own** timestamp path, typed `DateTime64(3, 'UTC')` | `schema-types-native-types` |
| ORDER BY | `payload.event` first → frequently-filtered LowCard dims → `user_id` → `payload.{timestamp_path}` last; **max 4–5 columns**; **no Nullable paths in the key** (see 3c) | `schema-pk-cardinality-order`, `schema-pk-prioritize-filters` |
| LowCardinality | Apply to typed string paths with ≤ ~10K distinct values (`application_id`, feature dims); **not** `user_id` | `schema-types-lowcardinality` |
| `ch_insert_time` | Always add: `DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))` | ingestion-time watermark |
| PARTITION BY | `toYYYYMMDD(ch_insert_time)` — bounded daily partitions | `schema-partition-low-cardinality`, `schema-partition-lifecycle` |
| TTL | `toDateTime(ch_insert_time) + INTERVAL {ttl_days} DAY DELETE`, `ttl_only_drop_parts = 1` | data lifecycle |
| Engine | plain `MergeTree` (Cloud) | — |

### 3d — Never emit (ClickHouse Cloud)

- `ReplicatedMergeTree(...)` or replication macros (`{cluster}`, `{shard}`, `{replica}`)
- a `..._distributed` `Distributed(...)` table
- `storage_policy = ...`
- typed hints for paths that are **not** in ORDER BY / PARTITION BY
- **escaped double-quoted literals** — `'"UTC"'`, `'"express_checkout_shown"'`, `DateTime64(3, '"UTC"')`. Always single-quote: `'UTC'`, `'express_checkout_shown'`. When emitting a constant string in an MV `SELECT` (e.g. an `event_type` column), write `'express_checkout_shown' AS event_type`, never `'"express_checkout_shown"'`.

### 3e — Output file

Produce **one file** containing the `CREATE DATABASE` guard followed by the **single base
table**, then any MVs:

```
Atlys/schemas/{schema_name}.sql
```

File header format:

```sql
-- Schema: {schema_name}
-- Source NDJSON: {ndjson_path}
-- Database: atlys
-- Base table: {spec_table}  (ONE table per spec — all event types land here)
-- MVs: {comma-separated list of MVs, or "none"}
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)
```

See **[references/production-ddl-template.md](references/production-ddl-template.md)** for the
full template and a worked example.

### 3f — Materialized views (only if Step 2d verdict = MV NEEDED)

If — and only if — the Step 2d derivation concluded an MV is needed, append the MV
object(s) to the **same `.sql` file**, after the base table. For each proposed MV, emit
the two-object pattern (AggregatingMergeTree backing table + `CREATE MATERIALIZED VIEW`)
that reads dimensions/metrics through `payload.*` paths **from the single base table**. When
a metric applies to only some event types (e.g. `payment.*` on `express_payment_confirmed`),
add `WHERE payload.event = '<event_type>'` to the MV `SELECT`.

Follow **[references/materialized-views.md](references/materialized-views.md)** for the exact
pattern, aggregate-state mapping, and a worked example. Note the MV objects in the file
header `-- MVs:` line.

If the verdict was **NO MV**, skip this step entirely and record the reason in the profile
output — do not add speculative MVs.

---

## Step 4 — Validate Locally with chdb

Run automatically. Do NOT ask the user. Do NOT use a pre-written template. **This step is a
hard gate — you may NOT commit, push, or open a PR (Steps 6–8) until it passes.** If you
cannot run chdb, STOP and tell the user; do not skip ahead to git.

### 4-lint — Static lint FIRST (catches the #1 generation bug)

Before running chdb, run this cheap static check on the generated `.sql`. It catches the
escaped-double-quote literal bug (`'"UTC"'`, `'"express_checkout_shown"'`, `DateTime64(3, '"UTC"')`)
that has slipped through before:

```bash
SQL="$REPO_DIR/Atlys/schemas/{schema_name}.sql"

if grep -nE "'\"" "$SQL"; then
  echo "❌ LINT FAIL: escaped double-quoted literal found (e.g. '\"UTC\"'). "
  echo "   Fix every occurrence to single quotes: 'UTC', 'express_checkout_shown'."
  echo "   Do NOT proceed until this returns no matches."
else
  echo "✅ LINT OK: no escaped double-quoted literals."
fi
```

Only continue to the dynamic chdb validation once this prints `LINT OK`.

The agent **generates the validation script dynamically** for this specific NDJSON —
then executes it, fixes any errors, and re-runs until it passes.

See **[references/chdb-validation.md](references/chdb-validation.md)** for the full
dynamic generation algorithm.

### How to generate the script (summary)

1. **Take one representative raw row per event type** (the row with the most non-null paths).
   Together they exercise the union of paths that land in the single base table.
2. Insert each row into the **single base table**, **wrapped** as `{"payload": <raw row>}`,
   via `FORMAT JSONEachRow` — the raw NDJSON row IS the event object, so it must be nested
   under `payload` to match the column name. The `payload` column absorbs the whole object
   (no per-field flattening / typing needed).
   - Ensure the event's timestamp path is a value parseable as `DateTime64(3)`.
3. **Emit `/tmp/validate_{schema_name}.py`** with fully resolved content — the exact
   `CREATE DATABASE`, the single `CREATE TABLE`, any MVs, and each real wrapped sample row.
   No `{placeholders}`.
4. The script asserts:
   - `CREATE DATABASE` + the base `CREATE TABLE` (+ MV tables/MVs) succeed,
   - inserting each wrapped row succeeds,
   - `SELECT count()` on the base table ≥ number of event types inserted,
   - the typed ORDER BY paths are readable and non-NULL
     (e.g. `SELECT payload.event, payload.destination, payload.timestamp FROM ...`),
   - `ch_insert_time` is auto-populated (`SELECT ch_insert_time` is not NULL),
   - each MV's backing table received rows (and any `payload.event` filter is honoured).
5. **Run the script:**
   ```bash
   python3 /tmp/validate_{schema_name}.py 2>&1 | tee /tmp/chdb_validation_output.txt
   echo "Exit code: $?"
   ```

### Auto-fix loop

```
Generate script from NDJSON → run it
  │
  ├─ ✅ BASE TABLE + MVs PASSED → proceed to Step 5
  │
  └─ ❌ FAIL
        ├─ Read error message → identify root cause (see chdb-validation.md error table)
        ├─ Fix: update DDL in Atlys/schemas/{schema_name}.sql
        │        (usually: wrong ORDER BY path, a Nullable typed path in the key,
        │         a bad timestamp value, an unwrapped INSERT row, or chdb too old for JSON)
        └─ Re-run  (max 5 iterations; surface to user if still failing after 5)
```

---

## Step 5 — Test on ClickHouse Cloud

After chdb passes, test the exact same DDL against the real ClickHouse Cloud instance.

### 5a — Connect

Use credentials supplied in Step 1, or read from environment:

```bash
CH_HOST="${CH_HOST}"
CH_USER="${CH_USER}"
CH_PASSWORD="${CH_PASSWORD}"
CH_DB="${CH_DATABASE:-atlys}"   # resolved database (default 'atlys')
```

Connect using the `clickhouse-client` CLI:

```bash
clickhouse-client \
  --host "$CH_HOST" \
  --user "$CH_USER" \
  --password "$CH_PASSWORD" \
  --secure
```

If `clickhouse-client` is not installed locally, fall back to the HTTP interface:

```bash
curl -s "https://${CH_HOST}:8443/" \
  --user "${CH_USER}:${CH_PASSWORD}" \
  --data-binary "SELECT 1" \
  --get
```

### 5b — Run DDL on Cloud

The `.sql` file already contains `CREATE DATABASE IF NOT EXISTS`, so run it directly:

```bash
clickhouse-client \
  --host "$CH_HOST" \
  --user "$CH_USER" \
  --password "$CH_PASSWORD" \
  --secure \
  --multiquery \
  < "$REPO_DIR/Atlys/schemas/{schema_name}.sql"
```

### 5c — Smoke test

For each new table, run:

```sql
-- Confirm table was created
SELECT name, engine, partition_key, sorting_key
FROM system.tables
WHERE database = 'atlys' AND name = '{event_table}';

-- Insert one raw row from the NDJSON (payload goes straight into the JSON column)
INSERT INTO atlys.{event_table} (event) FORMAT JSONEachRow
{"event": <one raw NDJSON row object>};

-- Confirm row landed
SELECT count() FROM atlys.{event_table};
-- ✅ expected: >= 1

-- Confirm typed ORDER BY paths + ch_insert_time are accessible
SELECT event.{timestamp_path} AS ts, ch_insert_time
FROM atlys.{event_table} LIMIT 1;
-- ✅ ch_insert_time must be auto-populated (non-NULL)

-- Clean up test row
TRUNCATE TABLE atlys.{event_table};
```

### 5d — Auto-fix loop

```
Cloud test
  │
  ├─ ✅ All tables pass → proceed to Step 6
  │
  └─ ❌ FAIL
        ├─ Parse cloud error (JSON type unsupported on tier, bad path type, TTL syntax, etc.)
        ├─ Fix DDL in the .sql file
        ├─ Re-run chdb validation (Step 4) to confirm fix is still locally valid
        └─ Re-test on Cloud (max 5 iterations; surface to user if still failing)
```

> **📸 Capture cloud test output:**
> ```bash
> echo "=== Cloud smoke test ===" > /tmp/cloud_test_output.txt
> clickhouse-client --host "$CH_HOST" --user "$CH_USER" --password "$CH_PASSWORD" \
>   --secure \
>   --query "SELECT name, engine, sorting_key FROM system.tables WHERE database='$CH_DB'" \
>   >> /tmp/cloud_test_output.txt 2>&1
> ```

---

## Step 6 — Write the Schema File

Write the finalised DDL (passed both chdb and Cloud tests) to:

```
Atlys/schemas/{schema_name}.sql
```

Use `write_file` / `create_file`. **Never overwrite an existing file without confirming with the user.**

---

## Step 7 — Git: Branch, Commit & Push

Run automatically from `$REPO_DIR`. Do NOT wait for the user.

```bash
cd "$REPO_DIR"

git checkout "$CH_TARGET_BRANCH"
git pull

EPOCH=$(date +%s)
git checkout -b ch-schema/{schema_name}-${EPOCH}

git add Atlys/schemas/{schema_name}.sql

git commit -m "feat(schema): generate ClickHouse DDL from {schema_name} ndjson"

git push --set-upstream origin ch-schema/{schema_name}-${EPOCH}
```

---

## Step 8 — Raise PR

Run automatically after the push succeeds.

Use the **host derived in Step 0b** (`$GH_TARGET_HOST`) so the PR is created on the same
GitHub instance the target repo lives on — NOT whatever host `gh` happens to default to.
`gh` honours the `GH_HOST` env var; set it for this call. Also pass the full `owner/repo`
slug. If `gh pr create` still fails (e.g. auth is only available for an unrelated enterprise
host), **fall back to printing the compare URL** — never leave the user without a PR link.

```bash
CH_REPO_SLUG="$(echo "${CH_TARGET_REPO%.git}" | sed -E 's#https?://[^/]+/##')"
BRANCH="ch-schema/{schema_name}-${EPOCH}"

# Point gh at the correct host (set in Step 0b)
export GH_HOST="${GH_TARGET_HOST:-github.com}"

PR_BODY="## ClickHouse Schema: {schema_name}

**Source NDJSON:** \`{ndjson_path}\`
**Database:** \`{ch_database}\`
**Tables added:** {comma-separated list}
**Design:** single JSON column + \`ch_insert_time\` MATERIALIZED; plain MergeTree (Cloud)
**Schema file:** \`Atlys/schemas/{schema_name}.sql\`

### Validation
- [x] static lint (no escaped double-quoted literals) ✓
- [x] chdb local validation passed ✓
- [x] ClickHouse Cloud smoke test passed ✓

### chdb Output
\`\`\`
$(cat /tmp/chdb_validation_output.txt 2>/dev/null)
\`\`\`

### Cloud Test Output
\`\`\`
$(cat /tmp/cloud_test_output.txt 2>/dev/null)
\`\`\`"

if gh pr create \
      --repo "$GH_HOST/$CH_REPO_SLUG" \
      --base "$CH_TARGET_BRANCH" \
      --head "$BRANCH" \
      --title "feat(schema): ClickHouse DDL for {schema_name}" \
      --body "$PR_BODY"; then
  echo "✅ PR created."
else
  echo "⚠️  'gh pr create' failed (likely gh is authenticated to a different/enterprise host than $GH_HOST)."
  echo "   The branch is pushed. Open the PR manually here:"
  echo "   https://$GH_HOST/$CH_REPO_SLUG/compare/$CH_TARGET_BRANCH...$BRANCH?expand=1"
fi
```

Report the PR URL to the user once complete.

---

## Step 9 — Hand off to the Context Agent (chain)

A new/updated table in `Atlys/schemas/` is a **schema-change trigger** for the downstream
**`context-agent`** skill, which refreshes the OKF living-context bundle under `knowledge/`
so the Analytics Agent never reasons from a stale snapshot. After the push/PR succeeds,
**activate `context-agent`** automatically — installing it first if it is not present.

### 9a — Ensure `context-agent` is installed, then run it

```bash
# The context-agent skill ships next to this one in the repo (skill/context-agent).
SKILLS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills"
CTX_SRC="$REPO_DIR/skill/context-agent"     # in the cloned repo
CTX_DEST="$SKILLS_DIR/context-agent"

if [ ! -f "$CTX_DEST/SKILL.md" ]; then
  echo "context-agent not installed — installing it now."
  if [ -x "$CTX_SRC/install.sh" ]; then
    "$CTX_SRC/install.sh"                    # its own installer
  elif [ -d "$CTX_SRC" ]; then
    mkdir -p "$CTX_DEST" && cp -R "$CTX_SRC/SKILL.md" "$CTX_SRC/references" "$CTX_DEST/"
  else
    echo "⚠️  context-agent source not found at $CTX_SRC — skip chain; ask the user to install it."
  fi
  echo "NOTE: opencode loads skills at startup — a restart may be required before the"
  echo "      newly-installed context-agent can be activated in a fresh session."
fi
```

### 9b — Activate the Context Agent with the schema-change trigger

Once installed (and loadable), **invoke the `context-agent` skill** as the next step, passing
the schema-change context so it runs its Step 2 **"Schema change"** trigger — not a full
reseed:

- **Trigger:** `Schema change`
- **New DDL:** `Atlys/schemas/{schema_name}.sql`
- **Database:** `{ch_database}` (default `atlys`)
- **Base table + MVs:** the objects created in Steps 3–6
- **Repo / branch:** `$REPO_DIR` on `$CH_TARGET_BRANCH`

Concretely, hand off with an instruction equivalent to:

> "A new table landed — update context. Run the context-agent for the schema-change trigger
> on `Atlys/schemas/{schema_name}.sql` (database `{ch_database}`), then bump the context
> version and open its PR against `$CH_TARGET_BRANCH`."

If `context-agent` cannot be activated in the current session (just installed, needs a
restart), tell the user exactly how to run it next:
`restart opencode, then say "a new table landed — update context for {schema_name}"`.

> This makes the two skills a **chain**: `design-ch-schema` (instrumentation) → push/PR →
> `context-agent` (living-context refresh). The context agent reads the live schema + the new
> DDL, writes/updates the `table`/`relationship`/`metric` concepts, surfaces contradictions,
> bumps `context_version`, and logs the diff.

---

## Constraints (always enforce)

- **Always** load and apply the `clickhouse-best-practices` skill before writing any DDL, and cite the specific rules driving each decision.
- **Always** read and profile the input NDJSON (detect the discriminator, union-scan all paths across event types) before designing.
- **Always** create the table and MVs under the resolved database (`ch_database`, default `atlys`), and emit `CREATE DATABASE IF NOT EXISTS <ch_database>;` at the top of the file. Never use any other database.
- **Always** emit **exactly ONE base table per spec** — every event type inserts into it. Never create a table per event type.
- **Always** design the base table as **one `JSON` column named `payload`** plus `ch_insert_time DateTime64(3,'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))`. Expose the event-type discriminator as the typed path `payload.event`.
- **Always** type JSON sub-columns **only** for paths used in ORDER BY / PARTITION BY — never type the whole payload. Paths present only for some event types are expected (the `payload` column absorbs them); this is not an error.
- **Always** use **single quotes** for every string literal and type modifier: `'UTC'`, `DateTime64(3, 'UTC')`, `'express_checkout_shown' AS event_type`. **Never** emit an escaped double-quoted literal like `'"UTC"'` or `'"express_checkout_shown"'`.
- **Always** treat `user_id` (String) and `application_id` (LowCardinality(String)) as present on every event and type them for use in ORDER BY.
- **Always** order the ORDER BY key **`payload.event` first → frequently-filtered LowCard dims → `user_id` → timestamp last**, **capped at 4–5 columns** (Step 3c), and `PARTITION BY toYYYYMMDD(ch_insert_time)`.
- **Always** have MVs read from the single base table, filtering by `payload.event` when a metric applies to only some event types.
- **Always** run the Step 4 static lint (no escaped double quotes) **and** chdb validation, and pass both, before any git/commit/PR step.
- **Always** target the GitHub host derived from `CH_TARGET_REPO` (`$GH_TARGET_HOST`) for `gh`; if auth/PR creation fails, print the compare URL rather than failing silently.
- **Always** chain into the `context-agent` skill after the push/PR (Step 9) — install it from `$REPO_DIR/skill/context-agent` if it is not present — so the OKF living-context bundle is refreshed for the new schema. Never end the run at the PR without triggering (or clearly instructing the user to trigger) the context refresh.
- **Never** put a `Nullable` path in ORDER BY.
- **Never** emit `ReplicatedMergeTree`, `Distributed` wrappers, replication macros, or `storage_policy` — this is ClickHouse Cloud.
- **Never** commit until the static lint, chdb, and Cloud tests all pass.
- **Never** overwrite an existing schema file without user confirmation.

---

## Quick Reference: Repo Layout

```
tillthelastrow/
├── Atlys/
│   ├── specs/
│   │   └── {spec_folder}/           ← input: NDJSON + spec.md live together
│   │       ├── events.ndjson
│   │       └── spec.md
│   └── schemas/                     ← ✅ OUTPUT: one .sql file per ndjson
│       └── {schema_name}.sql
└── skill/
    └── design-ch-schema/            ← this skill
        ├── SKILL.md
        └── references/
            ├── chdb-validation.md
            ├── production-ddl-template.md
            └── materialized-views.md
```

## Quick Reference: Target Table Pattern (ONE per spec)

```sql
CREATE DATABASE IF NOT EXISTS atlys;

CREATE TABLE IF NOT EXISTS atlys.{spec_table}
(
    payload JSON(
        event          LowCardinality(String),   -- event-type discriminator
        application_id LowCardinality(String),   -- common to all events (low-card)
        destination    LowCardinality(String),   -- frequently-filtered dim (Q2)
        user_id        String,                    -- common to all events (high-card)
        timestamp      DateTime64(3, 'UTC')
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
-- ORDER BY capped at 4–5 columns: discriminator, frequent dims, user_id, timestamp
ORDER BY (payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1;
```
