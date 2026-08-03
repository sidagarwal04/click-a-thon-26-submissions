# evidence/benchmark — OUR COVERAGE MATRIX for the required concurrency results
> **Summary:** The organiser specifies peak and average concurrency at minute, hour and day grain
> with dimension filters, not a fixed SQL set. These 13 queries are OUR COVERAGE MATRIX for those
> shapes — peak AND average concurrency, at
> minute / hour / day grain, with dimension filters (platform, country, content, video type) —
> plus the one shape the hour tier explicitly does NOT serve (a partial platform filter), so its
> minute-scan fallback cost is measured, not guessed. Run `tools/bench.sh` to regenerate
> `evidence/bench.txt` and `results/`. Queries are parameterized: `bNN_*.sql` + `bNN_*.params`.

## What each query covers

| file | grain | statistic | filter | serving path |
|---|---|---|---|---|
| `b01_day_peak_avg_total` | day (24h range) | peak + avg | none | `v_cc_window_range` → hour tier, 0 partial hours |
| `b02_day_peak_avg_platform` | day | peak + avg | platform | hour tier, cube level `(platform,*,-1)` |
| `b03_day_peak_avg_country` | day | peak + avg | country | hour tier, cube level `(*,country,-1)` |
| `b04_day_peak_avg_content` | day | peak + avg | content_id | hour tier, cube level `(*,*,content_id)` |
| `b05_hour_grain_peak_day` | hour | peak + avg per hour | none | stored rows of `cc_hour_agg`, 24 rows |
| `b06_minute_series_peak_hour` | minute | dashboard curve | none | delta scan of one hour + running sum + `WITH FILL` |
| `b07_minute_series_peak_hour_platform` | minute | dashboard curve | platform | same, filter = sort-key prefix of `cc_minute_delta` |
| `b08_day_peak_avg_video_type` | minute-scan | peak + avg | video type (`dictGet`) | minute tier, dictionary filter — video_type is not a cube level |
| `b09_day_peak_avg_partial_platform` | minute-scan | peak + avg | platform IN (2 values) | **the documented fallback**: a partial filter is NOT a cube level (`sql/50_hour_agg.sql`), must recompute from `cc_minute_delta` |
| `b10_range_peak_avg_full_span` | 13-day range | peak + avg | none | `v_cc_window_range` — cost grows O(range_hours), not O(range_minutes) |
| `b11_range_peak_avg_ragged` | ragged range | peak + avg | none | ADR 0003 decomposition: hour tier + ≤2 partial-hour minute scans |
| `b12_day_grain_all_days` | day | peak + avg per day | none | `v_concurrency_day_total` rollup of the hour tier |
| `b13_hour_top_content` | hour | top-10 content by peak | content dimension | content cube level of `cc_hour_agg` + `dictGet` enrichment |

## Ground rules the runner enforces

- **Warm first.** The Cloud service auto-suspends; the first query after idle has been measured at
  29.3 s. The runner issues warm-up queries and discards them before timing anything.
- **No query cache.** Every timed run sets `use_query_cache = 0` and `use_query_condition_cache = 0`.
- **Median of 3** server-side `elapsed_ns` (from `X-ClickHouse-Summary`, no `SYSTEM FLUSH LOGS`).
- **Findable.** Every run carries `SETTINGS log_comment='bench:<query>:run<N>:<tag>'` and its
  `X-ClickHouse-Query-Id` is recorded, so each number is auditable in `system.query_log`.
- **Read-only.** The runner only ever SELECTs against the graded database.

## Known deviations, stated up front

- The deployed `v_cc_window_range` on the graded database predates ADR 0014 and does not expose
  `peak_minute`; range queries (b01–b04, b10, b11) therefore report peak/avg/integral without the
  peak minute. Hour/day-tier queries (b05, b12, b13) do report `peak_minute`.
- Grain choices (which day, which hour, which platform) are ours; the official set may weight
  differently. The shapes are the statement's own words.
