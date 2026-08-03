# Concurrency dashboard (React + click-ui)

A ClickHouse-themed dashboard: the **concurrency curve** over the window of interest
with **dataset filters** applied, plus the exact SQL behind the chart.

- **Theme/UI:** [`@clickhouse/click-ui`](https://github.com/ClickHouse/click-ui)
  (`ClickUIProvider`, `Select`, `Button`, `Title`, `Text`, `Spinner`).
- **Chart:** recharts. **Backend:** a tiny Express proxy (`server.mjs`) that holds the
  ClickHouse creds and enforces read-only `SELECT`/`WITH` — the browser never sees creds.

## Run
```bash
cp .env.example .env        # ClickHouse URL + a READ-ONLY user
npm install
npm run dev                 # proxy on :8787, UI on http://localhost:5173
# production: npm run build && npm start   (serves dist on :8787)
```
Requires Node ≥ 20.6 (`--env-file`). If `@clickhouse/click-ui` resolves to a version
whose `Select` API differs, adjust the two `<Select>` blocks in `src/App.tsx`.

## Filters → dataset columns
All **11 documented dataset filter dimensions** (`spec.md`) are exposed. Eight are columns
on `hist_minute_full` (equality filter); three are content attributes — `hist` stores only
`content_id`, so they resolve by **joining `content_raw`** (the spec's real-time content join):
`content_id IN (SELECT content_id FROM content_raw WHERE <attr> = <value>)`.

| Filter | Backing | Source (spec.md) |
|---|---|---|
| Platform | `platform` (col) | raw |
| App version | `app_version` (col) | raw |
| Country | `country` (col) | raw |
| Audio | `audio_language` (col) | raw |
| Subtitle | `subtitle_language` (col) | raw |
| Player | `player_version` (col) | raw |
| Resolution | `video_resolution` (col) | raw **(new)** |
| Video type | `video_type` (col) | content |
| Title | join `content_raw.title` | content |
| Show | join `content_raw.show_name` | content **(new)** |
| Category | join `content_raw.category` | content |

> Note: `dictGet('content_dict', …)` is correct in a `SELECT`/`GROUP BY` but mis-evaluates to
> `0` as a `WHERE` predicate on this table, so filters use the `content_raw` semi-join instead.

Each dropdown lists the top 150 values **ranked by concurrency** (so the most-watched
platforms / titles / shows surface first). Filters AND together and apply to the concurrency
curve and the KPI cards (peak / peak-time / average). The curve query is
`SELECT toStartOfMinute(minute), sum(cnt) … GROUP BY minute` over the peak day with the
selected filters ANDed in — shown live in the "ClickHouse query" panel.
