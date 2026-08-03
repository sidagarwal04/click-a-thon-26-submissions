# ClickStack dashboards

Six dashboards and five alerts over the serving tables, created through the
managed ClickStack API rather than clicked together by hand — so they are
diffable, reviewable, and reproducible on another service.

| File | What it is |
|---|---|
| `dashboards/01-live-concurrency.json` | Live concurrency at 10-second grain, filterable by title / content type / category |
| `dashboards/02-concurrency-analytics.json` | Corrected concurrency at 1-minute grain, filterable by platform / app version / content type / category |
| `dashboards/03-pipeline-observability.json` | Ingest lag, rollup latency, recompute backlog, and read volume per serving query |
| `dashboards/04-grouped-viewers.json` | Stacked-bar breakdown; pick the group-by key from a tab bar |
| `dashboards/05-benchmark-answers.json` | The scored benchmark set: peak and average per grouping, at minute/hour/day, with query evidence |
| `dashboards/06-viewer-drop-alerts.json` | Retention against each slice's own trailing baseline, per location / platform / content type / category |
| `alerts.json` | The five alerts and their webhook, bound to tiles of 06 by name |
| `sources.json` | The four ClickStack sources the tiles bind to |
| `apply.sh` | Create-or-update everything. Idempotent |
| `csapi.sh` | One authenticated request against the ClickStack API |
| `check-tiles.sh` | Run every tile's SQL against ClickHouse and report pass/fail |
| `check-render.sh` | Load each dashboard in a browser and assert it actually renders |
| `TILE-VERIFICATION.md` | Last full sweep: every tile against six windows |

## Setup

`.env` needs the four Cloud API values plus one that has to be read by hand:

```
CLICKHOUSE_CLOUD_KEY_ID=...
CLICKHOUSE_CLOUD_KEY_SECRET=...        # Org Admin or Service Admin
CLICKHOUSE_CLOUD_ORG_ID=...
CLICKHOUSE_CLOUD_SERVICE_ID=...
CLICKSTACK_CONNECTION_ID=...           # 24 hex chars, from the ClickStack UI
```

**Why `CLICKSTACK_CONNECTION_ID` cannot be automated.** Managed ClickStack
provisions its own ClickHouse connection and does not expose the connections
routes over the Cloud API — on this service both `GET` and `POST` on
`.../clickstack/connections` return 404, while `/sources`, `/dashboards`,
`/alerts`, `/webhooks`, `/saved-searches` and `/roles` all work. Every tile needs
that connection's id (`connectionId` is required on a raw-SQL chart config, and
`connection` is required on a source), so it has to be read once from the UI:
open ClickStack from the ClickHouse Cloud console, then **Team Settings →
Connections**, or the **Connection** dropdown in any tile editor. It looks like
`68f3a1c9d4e77b0012ab34cd`.

The quickest way to read it: create any throwaway source in the UI, then
`./clickstack/csapi.sh GET /sources` — every source carries its `connection` field.

Then:

```bash
./clickstack/apply.sh --dry-run    # resolved payloads, sends nothing
./clickstack/apply.sh              # create or update
```

or `make clickstack` from `ingest/`.

### One API asymmetry `apply.sh` has to work around

Create assigns ids to filters and tiles; **update requires the filter ids back** —
omit them and it fails with `filters.0.id: Required`. Tile ids are optional on
update, but an omitted one makes the server mint a new tile rather than preserve
the old, which would silently orphan any alert bound to that `tileId`. So on
update `apply.sh` re-reads the live dashboard and grafts both sets of ids on,
matched by name. A filter added since the last apply gets a freshly minted
ObjectId, because update will not mint one for you.

## Verifying before you publish

ClickStack renders a broken tile as an empty box with the error tucked into a
panel, so a dashboard can look fine while half of it is failing. `check-tiles.sh`
expands the HyperDX SQL macros to concrete values and runs each tile's query
directly:

```bash
./clickstack/check-tiles.sh                                       # last 24h
./clickstack/check-tiles.sh '2026-07-26 10:00:00' '2026-07-26 11:00:00'
./clickstack/check-tiles.sh --rows                                # show first rows
```

`--sweep` runs every tile against six windows chosen for *shape* rather than size:
the canonical hot hour, the hot day, the full extract span, two live windows, and
**Jul 16-17 where the extract has no events at all**. That last one earns its place —
a tile that errors on an empty result set breaks on a quiet night, and nothing else
catches it beforehand.

All 38 SQL tiles pass against `sonyliv_prod` in all six windows (228 checks); the
last run is committed as `TILE-VERIFICATION.md`. It checks that a query is valid and
what it returns — not that the chart looks right; `make rollup-check` is what asserts
the numbers.

Reading the returned *values* rather than just pass/fail is what caught a number tile
emitting a unix epoch, an empty window rendering `-0`, and `argMax` over zero rows
leaking a fake `1970-01-01` row.

### Valid SQL is not a rendered dashboard

`check-tiles.sh` proves the SQL runs and the API's own `POST /dashboards/validate`
proves the payload is well formed. Neither proves the UI can draw it, so
`check-render.sh` loads each dashboard in a browser and asserts its name reaches the
document title *and* a tile-specific probe string reaches the body:

```bash
./clickstack/check-render.sh     # 4 render, 0 broken
```

It needs a logged-in session. `browse` is Chromium-only and its
`cookie-import-browser` reads only Chromium-family profiles, so a Firefox session has
to be carried across by hand — Firefox keeps cookies in plain SQLite, and the ClickStack
UI lives on `hyperdx.clickhouse.cloud`. Failing that, `browse handoff` and one manual
sign-in works; the session persists.

**The settle is the whole trick.** Waiting on an `svg` node returns instantly, because
the sidebar has SVG icons from the first paint — the probe then reads an unmounted page
and reports every dashboard as broken. That false signal cost a round of "diagnosis"
that blamed the `pie` and `bar` chart types for a fault that did not exist. Use
`wait --networkidle`, which blocks until the SPA stops fetching.

## What the dashboards read, and the one rule behind their layout

Both concurrency dashboards read the serving tables from
`ingest/sql/007_serving_concurrency.sql`, never `events_raw`. The tables exist in
the shape they do because of a single property:

- **`active_ms` is additive across every dimension.** `sum(active_ms) / window`
  is the exact time-weighted average concurrency under *any* filter combination.
  Every filterable tile is built from it.
- **`ending_concurrency` is additive across dimensions at one instant**, because a
  session belongs to exactly one slice. It is the honest "how many right now".
- **A peak is additive across nothing.** Two titles peak at different moments, so
  summing their peaks counts viewers who were never simultaneously present. Exact
  peaks are therefore precomputed per grouping (`dim_mask`) and cannot respond to
  an arbitrary filter — there is no precomputed peak for *Platform=IPHONE AND
  Category=Sport*, and manufacturing one by summing would produce an upper bound
  masquerading as a peak.

That is why dashboard 02 splits its tiles into two labelled groups instead of
letting every filter touch every tile. The distinction is visible in the UI on
purpose.

It is also why dashboard 04 stacks bars of average concurrency and carries no peak
at all. `active_ms` is additive, so a stack of per-platform bars sums to exactly the
true overall average — verified: mask 63 grouped by platform totals 855.603469 over
the hot hour, identical to the ungrouped mask 0 figure, and the shares sum to 100.00.
Stacked peaks would total more viewers than were ever simultaneously present.

## Two ClickStack traps these dashboards work around

**`$__timeFilter` is inclusive at both ends.** A 10:00–11:00 selection returns 61
minutes, not 60. Every window here adds an explicit `AND <col> < $__toTime` to make it
half-open `[from, to)`, matching the pipeline's interval convention. Without it the
time-weighted average ran **4.3% high**, because the numerator counted 61 minutes while
the denominator capped at the selected span. If a minute count ever reads 61, that
guard has been dropped.

**Timestamps render in the browser's timezone; the pipeline is UTC end to end.** On an
IST machine the 10:55 UTC peak minute displays as 16:25, and picking "10:00–11:00" in
the date control selects 04:30–05:30 UTC — a quiet period on this extract that reads a
peak of 10 rather than 2,305. Drive the range from UTC epochs when a number has to be
comparable to a reference figure:
`?from=1785060000000&to=1785063600000` is the canonical hot hour.

## Reference figures

`make rollup-check` asserts these against the serving tables, scoped to the
extract's own sessions so synthetic traffic cannot move a fixed number:

| Figure | Value |
|---|---|
| Active intervals | 31,947 across 10,848 sessions |
| Session-hours | 1,779.502796 |
| Hot hour 2026-07-26 10:00–11:00 UTC, exact in-minute peak | 2,305 |
| Hot hour, time-weighted average | 855.578199 |

## Known limits

- **These dashboards and `sonyliv` answer content-dimension queries differently, on purpose.**
  Ask "concurrency by category, sliced per title" here and you get 84 categories; ask the same
  of `sonyliv.concurrency_minute_versions` and you get one. Neither is wrong — they resolve
  differently.

  `video_type` and `category` are functionally determined by `content_id` (the catalogue maps
  each id to exactly one of each), so any row carrying a `content_id` *can* have them resolved
  from `content_dict` even at a mask that did not select them. These views do that; the
  `sonyliv` pipeline deliberately does not, on the argument that widening the `dictGet` surface
  is a risk not worth taking under time pressure. That argument is recorded in
  `docs/CROSS-PIPELINE-RESPONSE.md` §4 and it is a reasonable one.

  We resolve because the alternative is worse for a dashboard: without it, masks 4 and 5 render
  both columns blank and a filter on either silently returns **zero rows** against 31,537
  content rows that could have answered it. The risk it trades against — a cold replica
  returning the dictionary's fallback for every row, which self-heals before anyone can look —
  is made assertable rather than accepted: every miss resolves to `__unknown__`, a string that
  cannot occur in the catalogue, and `090`'s `d_dict_resolves` invariant fails if the count is
  ever non-zero. It currently reads 0 of 111,483 content-carrying rows.

  **What this does NOT make correct is a filtered peak.** `minute_peak` is exact only at the
  row's own mask. Filter `grouping = 'content'` by category and `max(minute_peak)` gives the
  busiest single *title* in that category — measured **14** — not the category's peak, measured
  **46** at `grouping = 'category'`. Averages are safe either way, since `active_ms` is
  additive: both paths give 11.012060. Tiles that report a peak pin a mask that carries the
  dimension; tiles that filter freely report averages.

- **An unresolvable title is graphed, not dropped.** The title leaderboards carry
  `title != ''`, which excludes rows whose mask carries no content dimension. `''` therefore
  means only that; an id that does not resolve reads `__unknown__` and stays in the chart. Zero
  rows on the tuning extract — all 3,352 titles resolve — but the unseen day ships a fresh
  catalogue and no such guarantee, and a leaderboard that silently omits real viewing is worse
  than one with an ugly label in it.

- **Two observability tiles need `READ ON REMOTE`.** They read
  `system.query_log` and `system.parts` through `clusterAllReplicas(default, ...)`,
  because both are per-node on Cloud and a plain read shows only the replica that
  answered — measured here, 8,519 query_log rows against 36,895 cluster-wide. That
  needs `GRANT READ ON REMOTE TO sonyliv_svc` on top of `SELECT` on the system
  tables. If those two tiles ever render empty, check that grant first.
- **The live dashboard needs live traffic.** 93.9% of the extract sits in a
  2.5-hour window on 2026-07-26, so the 10-second layer has nothing recent to
  show unless something is producing events. `bin/sonyliv-gen --concurrency 900
  --duration 90m --speed 1 --content-pool 30 --seed <fresh>` alongside
  `make rollup-live` fills it. A fresh seed each run is required — identical flags
  produce an identical dedup fingerprint and the load is silently skipped as a
  replay.
- **Live buckets older than the rebuild window are frozen snapshots.** The live
  layer rebuilds only a trailing `--live-window` (30 min default), so once a bucket
  ages out it keeps whatever it held — written while those sessions were still open,
  with each interval ending at the optimistic `last_signal + 120s` lease. It is never
  revisited, while the `TTL` keeps it queryable for three days. So a wide window on
  dashboard 01 shows slightly *optimistic* history; dashboard 02 is the corrected
  reading. `make rollup-check` quantifies the gap rather than assuming it: measured at
  **0.066% over 92 frozen minutes**, which is both small enough to trust the live
  layer and a real reason the lagged one exists.
- **A fresh loop pays a cold start.** `--loop` keeps an in-memory cursor of what it
  last recomputed, so the first pass after a restart has no cursor, reads every
  dirty session, and rebuilds every service day. Steady state is one day; the first
  pass is all of them. Restarting the loop is therefore cheap but not free.
- **Alerts evaluate but deliver nowhere by default.** `CLICKSTACK_ALERT_WEBHOOK_URL`
  is optional and falls back to an RFC 2606 `.invalid` host, which cannot resolve.
  State transitions are real and visible in ClickStack; nothing is sent anywhere.
  Point it at a Slack incoming webhook for delivery. Not defaulted to a live
  endpoint on purpose — concurrency figures should not leave the account because a
  config value was missing.
- **An alert interval must exceed the minute layer's publish lag.** At `1m` or `5m`
  the window contains no settled minute; ClickHouse `min()` over an empty set
  returns `0.0`, not null, so every evaluation would page. Hence `15m` intervals and
  an explicit `count() = 0` guard in every tile. Read the current lag off
  *Detector lag (s)* before lowering either.
- **A 15m alert is evaluated on a 15m cadence.** Changing a threshold does not
  re-evaluate immediately — expect up to one interval before the state catches up.
- **The location alert reports total collapse, not a regional one.** `country`
  carries a single value, `india`, throughout this extract. The detector is
  per-slice with an independent baseline each, so a multi-country day lights up per
  country with no change; today, platform is the dimension where a partial outage
  is visible.
- **A scheduled end-of-broadcast decline is indistinguishable from an outage.** No
  baseline-relative detector can separate them without an EPG signal the extract
  does not carry; the 2026-07-26 11:19 episode is exactly that case. Related: as the
  trailing baseline decays, an alert self-clears after roughly 15 minutes even if
  the outage continues. Correct for paging, wrong for a status page.
