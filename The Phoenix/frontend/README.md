# frontend: Phoenix Console

A Next.js (App Router, TypeScript) dashboard for the foreground-only concurrency serving layer.
It replaced a single-file vanilla dashboard, which has been removed, and it is what a judge sees.

There are two consoles in this app, not one:

- **`/`**, the concurrency console (`src/app/page.tsx`): the sessions/users/compare curves
  described below.
- **`/v2`**, the insight console (`src/app/v2/page.tsx`, `InsightConsole.tsx`): the ClickHouse
  insight views (state flow, transitions, spikes, and the rest) with their own filter sidebar.

Each links to the other, and both link out to the ClickStack dashboard (`ConsoleHeader.tsx` on
`/`, the header in `InsightConsole.tsx` on `/v2`), so a judge landing on either one can reach the
other and the raw observability view without hunting for a URL.

## Problem

Concurrency looks like interval overlap, count sessions whose `[start, end]` span a minute, but
an open session isn't the same as an active one. A session can sit backgrounded, paused, or silent
between heartbeats while still technically "open"; counting that time overstates the audience, and
every downstream decision a dashboard like this drives (ad loads, capacity, content ops) inherits
that overstatement. The actual problem this app's data is built to solve is narrower and harder:
find the truly active sub-ranges inside each session, not the session's full open/close span, and
run concurrency over only those, at a scale where the two obvious approaches both fail. Exploding
every session into one row per minute it was open is too much data to store and scan. Recomputing
overlap from raw session history on every dashboard query is too slow to serve. And sessions aren't
closed books, heartbeats keep arriving on open sessions, so the active ranges have to absorb
updates incrementally rather than being rebuilt from scratch each time.

That's what the pipeline behind `concurrency_deltas` / `user_concurrency_deltas` does upstream of
this app: a per-session state machine turns raw heartbeats into active-range runs (with retraction
when a session that looked paused turns out to still be live), those runs collapse into small
per-minute delta rows, and this dashboard just sums a cumulative window over that delta table, the
hard part (active-range detection under constant updates) is already paid for by the time a query
here runs in single-digit milliseconds.

## What it shows

- **Sessions**: session-aware concurrency, reading `concurrency_deltas`.
- **Users**: session-independent concurrency, reading `user_concurrency_deltas`.
- **Compare**: both curves overlaid, plus the peak-to-peak divergence (one viewer open on two
  devices is two sessions and one user, that gap is the point of having both models, not an
  error in either).

The SQL is **not** in this app. Every shipped query is read off disk from
[`sql/queries/serving/`](../sql/queries/serving/), which is the single source of truth, via
`src/lib/sql.ts`.

This used to be the other way round: the routes inlined their own copy, justified as "no runtime
dependency on the rest of the repo, deployable on its own". What that cost, measured: the inlined
copies were forked from a since-retired benchmark directory whose query this repo had already
measured at **185.95** against a true **88.20** over the same day, and the correction committed to
`serving/` was never ported across. The dashboard served a number 2.1x too high while the correct
query sat in the repo with no reader.

So the trade is now explicit and deliberate: this app requires the repo checkout at runtime,
exactly as it already required `../.env`. In exchange there is no second copy of a query to go
stale, and [`scripts/check_query_sources.sh`](../scripts/check_query_sources.sh) fails the build
if one reappears.

Columns are read from the result **by name**, never by position, so a column added for the
benchmark or validation harness cannot silently shift which number appears under which label.

## Setup

Requires **Node 20+**.

```bash
nvm use 20            # or: nvm install 20
cd frontend
npm install
```

Credentials: this app reads the repo-root `../.env` (the same file `scripts/ch.sh` uses) for
`CH_HOST` / `CH_USER` / `CH_PASSWORD` / `CH_DATABASE`.

It deliberately does **not** read `CH_PORT`. That variable is `9440`, the native secure protocol
port for `clickhouse-client`; this app speaks HTTPS, which is `8443`. Reading it meant every
request went to the wrong port and none could succeed. Override with `CH_HTTP_PORT` if a
deployment genuinely differs.
If it doesn't exist yet:

```bash
cp ../.env.example ../.env    # fill in from the ClickHouse Cloud console
```

`.env.local.example` in this folder documents an optional frontend-only override; you do not
need it if `../.env` is already set up.

## Run

```bash
npm run dev      # http://localhost:3200
npm run build && npm run start   # production build
npm run typecheck
```

## Routes

| Route | Reads | Returns |
|---|---|---|
| `GET /api/concurrency` | `concurrency_deltas` | minute curve + peak/avg, session-aware |
| `GET /api/user-concurrency` | `user_concurrency_deltas` | minute curve + peak/avg, session-independent |
| `GET /api/status` | `raw_events`, `*_minute_runs`, `*_deltas` | ingestion counters, for the live/ingested header |
| `GET /api/dimensions` | `concurrency_deltas` | distinct filter values for the sidebar |
| `GET /api/v2/*` | insight tables under `sql/insights/` | one insight view's rows plus its query/cost fields, for `/v2` |

Query params on `/api/concurrency` and `/api/user-concurrency` (all optional):
`platform`, `country`, `video_type`, `app_version`, `content_id`, `from`, `to`.
Empty string / `0` means "no filter on that dimension", filters are always passed as
ClickHouse query parameters (`param_*`), never interpolated into the SQL text.

Every route above returns its data alongside the query it ran and what that query cost, read by
`QueryPanel` (`src/components/QueryPanel.tsx`, shared by both consoles):

- `sql`: the executed query text, one entry per statement (some routes run a curve query plus a
  reach query, so this is an array, not a single string).
- `sqlFiles`: the repo-relative path each `sql` entry was read from, same order.
- `reads`: the table the query reads (what `/v2`'s filter-disabling logic checks a column against,
  see below).
- `rowsRead`, `bytesRead`, `serverMs`: read off ClickHouse's own `statistics` for the query, not
  timed client-side. `serverMs` is separate from wall time so a fast query does not get blamed for
  a slow network hop.

`QueryPanel` strips each file's leading comment block for display (`stripComments`), since a
40-line explanation of why a clause is shaped the way it is belongs in the repo, not stacked above
the eight lines of SQL a reader came to see; the server still executes the whole file, comments
included; only the on-screen rendering is trimmed.

On `/v2`, a view's filter sidebar disables any control whose column the current view's table does
not carry, and names the table in the disabled control's title/label, rather than silently
accepting a filter the query would drop. This replaced accepting-and-ignoring, which let a judge
believe a filter narrowed a result that in fact ran unfiltered.

## Layout

```
src/app/                 App Router pages + route handlers (Node.js runtime, server-only)
src/app/api/*/route.ts   one handler per endpoint above
src/components/          client components, Dashboard orchestrates fetch/state,
                          everything else is presentational
src/lib/                 env loading, the ClickHouse HTTP client, shared types, filter parsing
```

## Design

Both consoles share one design system, defined once in `src/app/globals.css`: a light "printed
broadsheet" theme rather than a dark control-room or a separate admin-panel look. Warm paper
background (`--bg` `#edeee9`), a slightly lighter card surface (`--bg-panel` `#f6f7f3`) for panels
and tables, near-black ink (`--ink` `#14181c`), squared corners throughout (`--radius: 0`, a ruled
document has no rounding), and hairline rules with one heavy rule reserved for the masthead and
result frames. Two typefaces: Archivo Narrow for display, Archivo for body, plus IBM Plex Mono for
tabular figures.

Two accent colours carry the data, one job each: `--signal` (`#0f6e63`, teal) is the corrected,
foreground-only answer and the primary chart series everywhere; `--cool` (`#345f7a`, slate blue) is
the second series (user concurrency against session concurrency on `/`, a comparison series on
`/v2`), deliberately not red, since red on this project already means the naive session-span
overcount. `--phosphor` (`#8f6200`) marks live/"still arriving" state; `--alert` (`#b23a2e`) marks
divergence and errors. Every one of these is measured against the paper, the darkest of the three
surfaces, so the ratios in `globals.css`'s comments are worst-case, not best-case.

`src/app/v2/tokens.css` does not define a second theme: it is a thin alias layer, scoped to `.v2`,
that maps `/v2`'s own token names (`--surface-1`, `--action-blue`, `--series-1..5`, and so on) onto
the shared tokens above. `console.module.css` under `/v2` references only those aliases, never a
hardcoded colour, so the two consoles cannot drift into looking like different products. What
does vary between the two, and is meant to: `/v2`'s type scale and 4px spacing grid, sized for
dense insight tables rather than `/`'s ruled instrument panels.

This replaced a prior state where `/` was a near-black "Signal Room" dark theme and `/v2` was a
separate light theme (called "Langfuse" in a root-level `DESIGN.md` that has since been deleted
along with that theme). Two visual languages in one submission read as two products; a judge
should not be able to tell which console they are on from the palette alone.

The `/` chart is a hand-rolled SVG component (no charting dependency) since the data is one
densified per-minute series, a library buys nothing here but bundle size.
