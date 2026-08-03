# Final countdown checklist

Every item below is a strict, ordered gate. Do them in this order only. Each item names its
verification. Nothing is "done" until its verification passes and, where applicable, a stamped
artifact lands in `evidence/`.

Source of requirements: `docs/problem/spec.md` (unseen day),
`docs/problem/SONYLIV_SUBMISSION_GUIDELINES.md`, `docs/problem/PROBLEM_STATEMENT.md`.

## AMENDMENT, 2026-08-02: the benchmark query set no longer exists

`PROBLEM_STATEMENT.md` was revised. Two bullets were DELETED outright:

- "A **benchmark query set**: the fixed concurrency questions your system will be evaluated on"
- "A **ground-truth answer key** for the benchmark queries stays private with the judges"

Everything downstream of those two lines was rewritten. What replaces them:

1. THE DELIVERABLE IS NOW SELF-DEFINED AND EXPLICITLY ENUMERATED. "your system's concurrency
   results on it: peak and average concurrency at minute, hour, and day grain, with dimension
   filters, along with the query latencies and evidence that they ran through your pipeline."
   Three grains, both statistics, filtered. That is now a precise specification, where before it
   was a set of questions we had to guess at. Phase 10 was already aiming at exactly
   60 / 3600 / 86400, so the aim was right; it is now a requirement rather than an inference.

2. CORRECTNESS IS JUDGED BY SPOT-CHECK AGAINST RAW EVENTS, NOT AGAINST A PRIVATE KEY.
   Was: "your benchmark query answers versus the private ground truth."
   Now: "judges will spot-check your concurrency numbers against the raw events."
   This is the single most consequential change. It converts `sql/queries/validation/
   oracle_concurrency.sql` from an internal gate into a headline submission artifact: the judges
   are going to do by hand precisely what that query already does automatically. Being able to
   reconcile any served number back to raw events, on demand and in front of them, is now the
   correctness story rather than a supporting detail.

3. "A team that can defend its trade-offs beats a team with lucky numbers" (was: "a lucky
   benchmark"). Reasoning is explicitly weighted over output.

Two further readings of the full statement, which had not been read end to end before today:

4. RELIEF ON CLICKSTACK. Requirement is "meaningfully integrate AT LEAST ONE of ClickStack,
   Langfuse, or LibreChat." LibreChat alone satisfies it. An earlier note in this file treated
   removing ClickStack as putting the whole 25 percent criterion at risk; that was too strong.
   The risk is not that the criterion goes unmet, it is that one integration must carry it well.
   Phase 15 stands unchanged on that basis.

5. SCOPE CAUTION, and it cuts against Phase 11. "Out of scope. Authentication, production
   deployment, real dashboard products, and polished frontends. A minimal visualization of
   concurrency over time is enough to demo; judges reward the model and the serving layer."
   The submission guidelines still require a hosted demo link and still require the curve and
   filters to render in the product UI, so the deployment is not optional for submission
   compliance. But the problem statement is now explicit that it earns no points on its own.
   Keep Phase 11 minimal and spend the remaining hours on correctness evidence instead.

Decisions taken (2026-08-02, confirmed by the user):

- D-A: unseen day loads into a fresh `phoenix_unseen` (graded answers) and into `phoenix_next`
  (live console). `phoenix` is NOT touched, so every existing stamped number stays reproducible.
- D-B: all twelve dataset filter dimensions get exposed, not just the two new ones.
- D-C: pipeline evidence comes from ClickHouse Cloud query monitoring plus a stamped
  `system.query_log` extract. ClickStack is removed entirely.
- D-D: production runs as docker compose on the EC2 host with nginx on port 80 fronting the
  console and LibreChat.
- D-F (2026-08-02, later): LibreChat is the v2 conversational layer ONLY. Ask is removed from v1,
  which now answers the concurrency question and shows the query that answered it, nothing else.
- D-G: the Ask key is the USER'S OWN LLM PROVIDER KEY, not a credential on our LibreChat. Three
  allowlisted providers: Claude, Gemini, Codex (OpenAI). Questions bill to the visitor's account,
  which is what lets the hosted demo stay open.
- D-H: the deployed stack runs continuous ingest. `phoenix_next` is live and moving so v2
  demonstrates the curve building in real time; v1 serves the unseen day as delivered, static by
  intent because those are the graded answers and must not move while being read.
- D-E: the frozen slice is removed from v1 and v2 in production. Dataset selection becomes an
  explicit database switch in the UI, not a timestamp predicate.

---

## Phase 0. Unblock the integrity gate

- [x] 0.1 Not needed. `CONTEXT.md` was stale: the `PARTITION BY` declaration already matches.
- [x] 0.2 Not needed. `_skeptic_touched` is covered by the existing `phoenix` allowlist.
- [x] 0.3 Verified 2026-08-02: `./scripts/check_docs.sh` is fully green. All nine doc and query
  assertions pass, `phoenix` matches `sql/schema/` with 17 allowed generation differences, and
  `phoenix_next` matches with 0.

## Phase 1. Schema migration for the new columns

Order matters: the ALTER must land before any CSV touches the tables, because `CSVWithNames`
hard-errors on a header column with no matching table column.

- [x] 1.1 Headers confirmed against the live files on 2026-08-02 via `DESCRIBE url(...)`.

  Content, 5 columns: `content_id, title, video_type, category, show_name`.

  Raw, 14 columns: `content_id, video_session_id, user_id, event_type, event, event_timestamp,
  platform, app_version, country, audio_language, subtitle_language, player_version,
  session_start_epoch, video_resolution`.

  Two findings that change the ingest SQL:

  1. The raw URL in the pasted commands DOES NOT WORK. At 1.8 GB, `drive.google.com/uc?export=
     download&id=...` returns the Drive virus-scan interstitial, and ClickHouse fails with
     `EMPTY_DATA_PASSED` / `CANNOT_EXTRACT_TABLE_STRUCTURE`. The working form is
     `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`.
     The 1.4 MB content URL is fine either way.
  2. The raw header order matches `raw_events_landing`'s first 13 columns exactly, with
     `video_resolution` appended. That is precisely what makes the pasted `phoenix` INSERT
     dangerous: `phoenix.raw_events_landing` is 14 columns ending in `event_id String`, the CSV is
     14 columns ending in `video_resolution String`, the counts and types match, so
     `INSERT ... SELECT *` succeeds and writes resolution values into `event_id` with no error.
     Confirmed as a real hazard, not a theoretical one. Use named column lists only.
- [x] 1.2 Applied to `phoenix` and `phoenix_next`. `phoenix` was included deliberately even though
  it receives no unseen rows: adding a column changes no existing value, and keeping all three
  schemas uniform avoids widening `DRIFT_ALLOW`. Its rows carry the empty default, which is honest.
- [x] 1.3 Applied.
- [x] 1.4 Applied.
- [x] 1.5 Both MVs dropped and recreated, each preserving its own trailing column (`event_id` on
  `phoenix`, `now64(3) AS arrival_timestamp` on `phoenix_next`), with `video_resolution` inserted
  after `session_start_epoch`. Bodies verified by reading back `system.tables.as_select`.
- [x] 1.6 `sql/schema/01_raw_events.sql` and `02_content.sql` updated. `show_name` sits BEFORE
  `ingested_at` because `ingested_at` is the ReplacingMergeTree version column and must stay last.
- [x] 1.7 Verified by hand from `system.tables.as_select`, not via the gate.

## Phase 2. Ingest the unseen data

The pasted INSERTs must NOT be run as given. `INSERT ... SELECT *` matches by position, not name.
`phoenix.raw_events_landing` has 14 columns ending in `event_id String` and the new CSV has 14
ending in `video_resolution` (both String): it would succeed and write resolution strings into
`event_id` with no error anywhere. `content` would write `show_name` into `ingested_at`, which is
the ReplacingMergeTree version column.

- [ ] 2.1 Roll `.derive_watermark.phoenix_next` back behind 2026-07-31. It currently holds
  2026-08-01, which is after the unseen day, so the derive tick would skip the new events entirely.
- [x] 2.2 Created. 14 concurrency tables plus 10 insight tables.
- [x] 2.3 Loaded with named columns. `phoenix_unseen.content` = 33,326 titles, all carrying
  `show_name`. `phoenix_next.content` = 41,144 after the merge with the original corpus, 33,326 of
  them with `show_name`.
- [x] 2.4 Loaded into `phoenix_unseen` with named columns via the usercontent URL.
  STILL TO DO: the same load into `phoenix_next`.
- [x] 2.5 Verified: exactly 7,000,000 rows, 108,486 sessions. 6,936,152 of them fall on
  2026-07-31 as the spec promises; the rest are a small dirty tail spanning 2014 to 2026-08-03,
  which is the dataset's own noise and which the foreground state machine must tolerate rather
  than have us clean.
- [ ] 2.6 Anti-join check: zero `content_id` in the new events with no row in `content`.
- [x] 2.7 `derive.sh phoenix_unseen` PASS in 41 seconds on 7,000,000 rows. 118,498 asserted runs.
  All three invariants green: closure 0, max assertions of one run 1, max runs per session minute 1.
  Artifact: `evidence/derive_phoenix_unseen__20260802T023815Z__6d595ae-dirty.tsv`.
  STILL TO DO: the derive tick for `phoenix_next` once its raw load lands.

  FIRST UNSEEN-DAY ANSWER, computed through the pipeline, not by hand:
  peak 22,416 concurrent sessions at 2026-07-31 11:16, daily average 914.65 over all minutes and
  1,667.21 over active minutes, 790 of 1,440 minutes carrying audience.
  The hourly curve is a clean single-event shape: negligible overnight, a ramp through the morning,
  a two-hour spike across 10:00 and 11:59 (hourly peaks 21,786 then 22,416), then effectively zero
  from 12:00. That shape is the "full window of interest with visible peaks and ramps" that
  SONYLIV_SUBMISSION_GUIDELINES section 1 requires, so the unseen day is a good demo window.
- [ ] 2.8 `FROM_TS=... TO_TS=... refresh_insights.sh` so all ten v2 insight tables cover the new day.
- [ ] 2.9 Gates: `schema_drift.sh`, `vocabulary_check.sh` (it will flag the new dimension values),
  `check_query_sources.sh`, `validate_insights.sh`.

## Phase 3. Ingest paths for the v2 views

- [ ] 3.1 Confirm each of the ten registered v2 views returns rows on the unseen day, not just on
  the old corpus.
- [ ] 3.2 `content_entry_cohorts` was roughly 14h behind, which left the Retention view blank.
  Catch it up and confirm Retention renders.
- [ ] 3.3 `spike_explanation` has no Gate A parity evidence. Add one or mark it explicitly.
- [ ] 3.4 Add `concurrency_boundary_deltas` to the guard lists in `derive.sh` and `rebuild_swap.sh`.
  A `REBUILD=1` re-derive currently appends a duplicate set silently.

## Phase 4. Filters: all twelve dataset dimensions

Raw dimensions: `platform`, `country`, `app_version`, `audio_language`, `subtitle_language`,
`player_version`, `video_resolution`.
Content dimensions: `title`, `video_type`, `category`, `show_name`.
Plus `content_id`.

- [ ] 4.0 DECISION on `video_resolution`, taken 2026-08-02 after measuring the live column.
  The values are free-form and fuse two facts: a quality-mode prefix and a pixel size, written
  inconsistently (`1920*1080`, `1920 * 1080`, `Auto-1280*720`, `DataSaver-640x360`, `NA`, empty).
  Measured cardinality: 2,071 raw, 2,041 after collapsing separators, and still 1,940 distinct
  pixel sizes once the mode prefix is split off, against only 39 distinct modes. The long tail is
  real device sizes, not dirt; the top 12 sizes cover 6.7M of the 7M rows.
  Therefore: FILTER ON THE RAW COLUMN VERBATIM, exactly as the dataset provides it. Do not invent
  a normalisation, because a normalisation silently changes the answers we are graded on. The
  picker lists the top values by volume, the same top-N shape `dimension_values.sql` already uses,
  with free text for the tail.
- [ ] 4.1 Extend `sql/queries/serving/dimension_values.sql` with a UNION ALL branch per new dim.
- [ ] 4.2 Resolve the content-side dimensions through the existing D15 content-id-resolution
  pattern in `sql/queries/serving/title_category_peak_average.sql`. Do not denormalise.
- [ ] 4.3 Plumb the frontend: `lib/filters.ts` `parseFilters`, `lib/types.ts` `ClientFilters` and
  the `DimensionValue.dim` union, `components/FilterRail.tsx` `DIM_FIELDS`, `components/Dashboard.tsx`,
  `lib/insights.ts`, and `ALL_FILTERS` in `app/api/v2/insight/[view]/route.ts`.
- [ ] 4.4 Filters must apply to the concurrency curve, not only to the v2 views. This is explicit
  in guideline 2.
- [x] 4.0b MEASURED, 2026-08-02, before committing to the widening. Distinct key cardinality on the
  unseen day goes from 547,310 (minute, platform, country, content_id, app_version) to 876,542 with
  `audio_language`, `subtitle_language`, `player_version` and `video_resolution` added: **1.6x, not
  an explosion**. Current `concurrency_deltas` is 341 KiB over 120,396 rows, so the widened table
  lands near 550 KiB. Per-dimension cardinality: platform 21, country 1, app_version 174,
  audio_language 72, subtitle_language 13, player_version 135, video_resolution 2,071.
  Verdict: widening is affordable. Proceed, and re-run `bench.sh` afterwards so the published
  "30,662 rows in 12 ms" is restated from measurement rather than carried over.
- [x] 4.0c SCHEMA AND PIPELINE WIDENED AND PROVEN, 2026-08-02.
  `audio_language`, `subtitle_language`, `player_version`, `video_resolution` now flow from
  `raw_events` through `foreground_intervals`, `session_minute_runs`, `user_minute_runs` and into
  all three delta tables, across all seven pipeline files (batch and incremental, session and
  user, both atomic variants).

  KEY PLACEMENT: appended AFTER `app_version`, deliberately not interleaved by cardinality. The
  first five columns are the prefix every existing filter prunes on and every published read
  figure was measured against; inserting `video_resolution` (2,071 distinct) mid-key would change
  the platform filter's pruning silently.

  TWO TRAPS HIT AND FIXED WHILE DOING IT, both invisible at read time:
  - `session_minute_runs` and `user_minute_runs` are CollapsingMergeTree. A retraction row that
    does not match its assertion COLUMN FOR COLUMN never cancels. The incremental paths
    (`03`, `03b`, `04c`) needed the four new columns in the retract arm AND in its `GROUP BY`,
    or every retraction would have accumulated forever.
  - A first attempt used bulk regular-expression edits across all seven files and produced
    duplicated and mis-indented column lists in four of them. Reverted and redone file by file.
    This is exactly the "bulk edit at hour 22" failure the repo's own comments warn about.

  VERIFIED BY DERIVING THE SAME 7,000,000 ROWS TWICE, five dimensions versus nine:
  asserted runs 118,498 both sides, peak 22,416 at 11:16 both sides, avg 914.65 and 1,667.21 both
  sides, zero minutes with a differing delta. Two minute rows exist on one side only and both
  carry delta sum 0, so neither moves any cumulative sum: unmerged zero-sum residue in the dirty
  tail, not a difference. Derive time 41s both sides, no regression.
  COST: 341.41 KiB / 120,396 rows becomes 439.13 KiB / 133,784 rows. Plus 28.6 percent on disk for
  four more filterable dimensions, far below the 1.6x the key cardinality suggested, because
  SummingMergeTree collapses.
  Evidence: `evidence/widen_dimensions_parity__20260802T032519Z__6d595ae-dirty.tsv`.

- [x] 4.0e SERVING AND FRONTEND DONE, and a SILENT CORRECTNESS BUG CAUGHT ON THE WAY.

  Serving: the four parameters added to `concurrency_curve`, `user_concurrency_curve`,
  `peak_average`, `peak_average_exact`, `average_definitions` and `reach`; four UNION ALL branches
  added to `dimension_values.sql`. Frontend: `ClientFilters`, `DimensionValue.dim`, `parseFilters`,
  `parseInsightFilters`, `DIM_FIELDS`, both consoles' querystring builders, and the v2 route's
  inert-filter declaration. Build green, typecheck clean.

  THE BUG. Widening added four columns to the MIDDLE of three tables, and every pipeline INSERT
  was a bare `INSERT INTO t SELECT ...`, which matches BY POSITION. The session path shifted:
  `concurrency_deltas.video_resolution` ended up holding player-version strings (`1.8.2`,
  `3.29.71_adNE`), and filtering `video_resolution = '1920*1080'` returned zero rows.
  It was SILENT because every column involved is `LowCardinality(String)`, so a shifted value is
  still a valid value and nothing errors. Found only by querying what the dimension actually
  contained rather than trusting that the derive's PASS verdict meant the data was right: all
  three invariants passed on misaligned data, because closure and run-count invariants say nothing
  about which column a value landed in.

  THE FIX is explicit column lists on all eight pipeline INSERTs, not a reordering. Naming the
  columns makes physical order irrelevant and retires the class rather than the instance. This is
  the third appearance of the same class in this project: the `event_id` incident
  (`scripts/inventory.sh`), the organisers' pasted `INSERT ... SELECT *`, and now this.

  Verified after the fix: every dimension holds values of its own kind, asserted runs still
  118,498, unfiltered peak still 22,416 at 11:16, avg still 914.65 / 1,667.21, and the
  `1920*1080` filter now returns peak 4,307 at 10:30 where it previously returned nothing.
  Evidence: `evidence/dimension_alignment_fix__20260802T033304Z__6d595ae-dirty.tsv`.

- [x] 4.0f PHASE 4 COMPLETE AND LIVE. Verified through the deployed stack on port 80, not locally:
  all nine dimensions reach the rail on the unseen dataset (platform 21, country 1, video_type 2,
  app_version 136, audio_language 52, subtitle_language 11, player_version 92,
  video_resolution 705, content 14,879), and filtering on the NEW dimensions returns real curves:
  `video_resolution=1920*1080` gives peak 4,307 at 10:30, `audio_language=hin` gives peak 10,898.
  All ten v2 insight views return rows (lateness is 0 until live ingest produces a genuinely late
  event, which is correct rather than broken).

  ONE HONEST LIMITATION, measured: the four new dimensions sit at positions 6 to 9 of the sorting
  key, so filtering on them alone prunes almost nothing. Unfiltered reads 354,305 rows; filtered by
  `video_resolution` reads 354,185. Prefix filters prune, suffix filters do not. This was the
  deliberate trade for not disturbing the existing key, and it belongs in the README rather than
  being left for a judge to discover.

- [ ] 4.0d SUPERSEDED by 4.0f. Original text: apply the widened schema to `phoenix_unseen` and `phoenix_next`
  and re-derive; add the four parameters to the serving queries; add the UNION ALL branches to
  `dimension_values.sql`; plumb the frontend; re-run `bench.sh` and restate the read figures.
- [ ] 4.5 Do NOT widen the ORDER BY of `concurrency_deltas`, `user_concurrency_deltas` or
  `concurrency_boundary_deltas` without measuring. That tuple is what produces "30,662 rows in
  12 ms". If it changes, re-run `bench.sh` and restate the number honestly.
- [ ] 4.6 Document in `README.md` which dataset column backs each filter. Guideline 2 requires it
  by name. No dimension may be left silent.

## Phase 5. Remove the frozen slice from production

- [x] 5.1 Removed from all 22 production queries (11 in `sql/queries/serving/`, 11 in
  `sql/insights/benchmark/`). Proven safe first: both `phoenix` and `phoenix_next` hold 905,558
  rows and ZERO rows at or after 2026-08-01, so the predicate was already matching everything and
  removing it changes no number in `evidence/`.
  Verified by EXECUTING all 22 queries against `phoenix_next`, not by reading them: 22 of 22 run
  clean.
- [x] 5.2 Removed from `lib/env.ts`, `lib/filters.ts`, `lib/insights.ts`, `lib/types.ts` and all
  seven route handlers. `Filters` is now identical to `ClientFilters`.
- [ ] 5.3 Keep the corpus-boundary shell variable where it guards validation scripts
  (`reset_live.sh`, `frozen_gate.sh`, `naive_baseline.sh`). Those are gates, not serving paths.
- [x] 5.4 `check_query_sources.sh` passes, `check_docs.sh` passes, `tsc --noEmit` clean,
  `next build` green.

## Phase 6. The dataset toggle in the UI

- [x] 6.1 Default is `original`; an absent or malformed `dataset` param resolves there too.
- [x] 6.2 `components/DatasetSwitch.tsx` plus `DatasetSwitch.module.css`, a segmented control with
  `aria-pressed` so the active generation is announced, not just coloured.
- [x] 6.3 Closed allowlist in `lib/datasets.server.ts`. The client sends an opaque id; the database
  name is never in the request and never reaches the browser. SPLIT INTO TWO MODULES because
  `lib/datasets.ts` is bundled for the client and `lib/env.ts` reads `../.env` with `node:fs` at
  module scope, which broke the production build until the server half was separated.
  `check_ask_guardrails.sh` still passes all four assertions.
- [x] 6.4 Every v1 fetch carries the dataset: status, dimensions, concurrency, user-concurrency.
  Switching clears the previous curve first, so a stale answer can never sit under the new label,
  and `dataset` is in the tick effect's dependency list so the switch re-answers immediately.
- [x] 6.5 Same control on v2, wired through status, dimensions and the insight route. Status is
  cleared on switch because the watermark anchors every view's window.

## Phase 7. LibreChat: user-supplied API key

- [x] 7.1 Collapsible key panel in `components/AskAI.tsx`. The toggle label doubles as the status
  readout. Blank falls back to the server's key, so a local developer types nothing.
- [x] 7.2 Disclaimer rendered as body copy, not fine print: the key stays in the browser tab, is
  not stored, logged, shared, or sent anywhere except as the authorization header on the user's
  own question, and is discarded when the tab closes. A "Forget key" button backs that up.
- [x] 7.3 Carried in an `X-LibreChat-Key` HEADER, never a query parameter or the body. Query
  strings reach access logs, Referer headers and `system.query_log`, and this project publishes
  query_log extracts as graded evidence, so a key in a URL would be a key in the submission.
  Held in component state only: no localStorage, no sessionStorage. Server-side `requestApiKey()`
  bounds it at 400 characters and character-checks it before it reaches an outbound header, so an
  unbounded client string cannot become header injection. Grep confirms it is never logged,
  stringified into a body, or persisted.
- [x] 7.4 `check_ask_guardrails.sh` passes all four assertions.

## Phase 8. Remove ClickStack

All of this lands in ONE commit. `check_docs.sh` asserts both that every verified-claim tag resolves
to a `LEDGER.tsv` row and that every ledger `artifact_path` exists, so a partial removal is red in
both directions.

- [ ] 8.1 Delete `docker/clickstack/compose.yml` and with it the whole `docker/` tree.
- [ ] 8.2 Delete `frontend/src/app/clickstack/route.ts`.
- [ ] 8.3 Remove the links in `components/ConsoleHeader.tsx` and `app/v2/InsightConsole.tsx`, plus
  the orphaned CSS classes.
- [ ] 8.4 Delete `scripts/clickstack_setup.sh` and `scripts/emit_query_spans.sh`.
- [ ] 8.5 Delete the three `evidence/clickstack_*.tsv`, their two `LEDGER.tsv` rows, and all seven
  `[V:clickstack_integration]` tags.
- [ ] 8.6 Purge the env vars: `NEXT_PUBLIC_CLICKSTACK_URL`, `HDX_URL`, `HDX_EMAIL`, `HDX_PASSWORD`,
  `OTLP_ENDPOINT`, `OTLP_API_KEY`.
- [ ] 8.7 Docs: delete `docs/clickstack.md`; clean `README.md`, `DEPLOYMENT.md` (port table, security
  group line, section 4, the nginx `/clickstack-ui/` location, the ops line, the secrets bullet),
  `docs/DECISIONS.md` D10, `docs/STATUS.md`, `docs/SUBMISSION_COMPLIANCE.md`,
  `docs/CUTOVER_PHOENIX_NEXT.md`, `docs/ROADMAP.md`, `frontend/README.md`, `TASK.md`.
- [ ] 8.8 Rewrite the "meaningfully integrate ClickStack, Langfuse or LibreChat" argument in
  `docs/SUBMISSION_COMPLIANCE.md` onto LibreChat plus `mcp-clickhouse`. That is now the sole
  integration claim and it must stand on its own.

## Phase 9. Pipeline evidence, which is a scored deliverable

The spec says twice: no pipeline evidence, no credit.

- [ ] 9.1 New `scripts/query_log_evidence.sh`: pull `query_id`, query text, `query_duration_ms`,
  `read_rows`, `read_bytes`, `memory_usage`, `event_time` from `system.query_log` for the benchmark
  run, stamped through the existing `evidence()` helper.
- [ ] 9.2 Capture the equivalent view from ClickHouse Cloud query monitoring as the second, external
  witness.
- [ ] 9.3 Verify the extract actually contains the concurrency-result queries by `query_id`,
  not by guessing.

## Phase 10. The concurrency-results artifact

`bench.sh` emits latency and read cost but no peak or average values. `RUNBOOK_UNSEEN_DAY.md` step
10 writes nothing stamped while step 11 asserts that it did. This is the single missing deliverable.

Now specified exactly by the revised statement: peak AND average, at minute AND hour AND day grain,
with dimension filters, plus latencies, plus pipeline evidence.

- [x] 10.1 DONE. `scripts/answers.sh` written and run against `phoenix_unseen`.
  Two bugs found and fixed in the writing: `peak_average.sql` ends in a semicolon, so wrapping it
  in an outer aggregate was a syntax error that made every cell read NA while the query itself was
  correct; and the default window was the data's full extent, which on the unseen day is eleven
  years wide because of the dirty tail, so `avg_all_minutes` divided a real audience by ~5.9
  million empty minutes. The window now anchors on the BUSIEST UTC DAY, which is also what
  guideline 1 asks for ("one full window of interest, with visible peaks and ramps").
  RESULT: 6 filter shapes x 3 grains, every cell populated, latencies **17 to 46 ms** on 7,000,000
  rows. Unfiltered peak 22,416 at 2026-07-31 11:16; avg 914.65 over all 1,440 minutes and 1,667.21
  over the 790 with an audience.
- [x] 10.1b (superseded item kept for the record) New `scripts/answers.sh`: sweep `sql/queries/serving/peak_average.sql` across all three
  required grains (60, 3600, 86400) crossed with the filter set, against `phoenix_unseen`.
  All three grains are mandatory now, not a choice.
- [ ] 10.2 Emit one stamped TSV carrying the answer value AND the per-query `serverMs`. That single
  artifact is deliverables 1 and 2 together.
- [ ] 10.3 Fix `docs/RUNBOOK_UNSEEN_DAY.md`: `UNSEEN_DAY` is 2026-07-31 not 2026-08-02; the
  hardcoded old content CSV at line 41; the 13-column guard at line 27 that now expects 14.
- [ ] 10.4 Run the corrected runbook end to end and commit the artifacts.

## Phase 11. Docker on EC2, port 80

- [ ] 11.1 Root `docker-compose.yml` with `proxy` (nginx, `80:80`) and `web` (the Next.js console).
- [ ] 11.2 `include:` LibreChat's compose. nginx routes `/` to the console and `/chat/` to
  librechat on 3080.
- [ ] 11.3 The web container MUST bind-mount the `sql/` tree and `.env`. `lib/sql.ts` and
  `lib/insights.ts` read query text off disk at runtime relative to cwd, and the app 500s on every
  route without it. Bind-mounting also keeps the "single source of query text" claim true.
- [ ] 11.4 Publish port 80 only. Nothing else reaches the host: not 3200, 3080, 8000, and not 3000
  (the LibreChat admin panel, which the current runbook's security-group line forgets).
- [ ] 11.5 Rewrite `DEPLOYMENT.md` around the compose stack instead of systemd plus a hand-copied
  nginx snippet.
- [ ] 11.6 Verify from outside the host: `http://<ec2>/` serves v1, `/v2` serves the insight
  console, `/chat/` serves LibreChat.

## Phase 10b. Spot-check reconciliation, promoted to a first-class deliverable

New, and it exists only because of the amendment above. Judges will "spot-check your concurrency
numbers against the raw events", so the reconciliation has to be a thing we hand them rather than a
thing we hope holds.

- [ ] 10b.1 Run `sql/queries/validation/oracle_concurrency.sql` against `phoenix_unseen` and stamp
  the result. It re-derives concurrency from raw events by an independent path; on the original
  corpus it matched the serving layer across 3,663 minutes with 0 differences.
- [ ] 10b.2 Publish a short "check us" section: pick any minute off the curve, here is the raw-event
  query that reproduces it, here is the answer. Make the spot-check one copy-paste, because a judge
  who has to write that query themselves may not bother.
- [ ] 10b.3 Run `naive_baseline.sh` on the unseen day. The naive overcount (32.3 percent on the
  original corpus) is the single clearest proof that foreground-only was actually implemented, and
  it is the failure mode the statement says "this whole problem exists to prevent".
- [ ] 10b.4 `average_definitions.sql` ships all three candidate averages side by side. That was
  hedging while the answer key was private; with correctness now judged by reconciliation it reads
  as rigour instead. Say so plainly in the README rather than burying it.
- [ ] 10b.5 `test_peak_is_not_a_rollup.sql` directly answers the scenario in statement line 25
  (a platform peak and a platform-plus-country peak landing on different minutes). Surface it.

## Phase 12. Cross-check: asked versus delivered

Read this against `docs/problem/SONYLIV_SUBMISSION_GUIDELINES.md` line by line, not against our own
roadmap. The risk being managed here is that v2 is an impressive edge solution while a mandatory
basic is missing.

- [ ] 12.1 Concurrency curve rendered in the product UI, showing a full window with visible peaks
  and ramps, with the ClickHouse query shown. Mandatory.
- [ ] 12.2 Filters applying to that curve and to every other view, with each backing dataset column
  documented in the README. Mandatory.
- [ ] 12.3 Unseen-day results, latencies, and pipeline evidence, all three present, with peak and
  average at all three grains and with dimension filters.
- [ ] 12.3b Correctness defensible by spot-check against raw events, per the revised rubric.
- [ ] 12.4 Hosted demo link in the README. Currently absent.
- [ ] 12.5 Recorded demo video, 2 to 3 minutes, showing the curve and filters working live.
  Currently absent.
- [ ] 12.6 Pitch deck PDF. Currently absent; `pitch/` holds only a placeholder.
- [ ] 12.7 Architecture documented.
- [ ] 12.8 ClickHouse is the primary datastore, and the LibreChat integration argument is written
  down.

## Phase 13. Intact, scalable, fast

- [ ] 13.1 Re-run `bench.sh` on the unseen day and restate every performance number in the README
  from the new artifacts. No number survives into the submission unmeasured.
- [ ] 13.2 Confirm the serving path still reads only deltas plus content, via the query-log gate.
  No serving query may scan `raw_events`.
- [ ] 13.3 Confirm partitioning, ORDER BY keys and `LowCardinality` choices still hold at 7M rows,
  and that the new dimensions did not push the delta tables into a worse key.
- [ ] 13.4 Consider codecs. There are none anywhere today; `index_granularity` and `LowCardinality`
  are the only choices made. Measure before adding any.
- [ ] 13.5 Full `check_docs.sh` green, which transitively runs `check_query_sources.sh` and
  `schema_drift.sh` on every database.

## Phase 14. Submission packaging

From the Click-a-thon '26 root README "How to Submit". Partner guidelines take precedence where
they are more specific, but everything here is mandatory for all tracks.

- [ ] 14.1 Fork the Click-a-thon '26 submissions repository.
- [ ] 14.2 Create a folder at the repo root named after the team. The team name is the unique
  identifier across all tracks. OPEN ITEM: the team name is not recorded anywhere in this repo and
  must be confirmed before the PR is opened.
- [ ] 14.3 The submission must be self-contained within that folder. Decide now whether the
  `librechat/` vendored tree ships in full or is reduced to the files judges actually need
  (`librechat.yaml`, `docker-compose.override.yml`, `.env.example`). Prefer the reduced form: the
  vendored source is not what runs, since the compose file pulls prebuilt images.
- [ ] 14.4 Project source code committed.
- [ ] 14.5 `README.md` rewritten to the required template, in this order: Team Name, Track,
  Project, Team Members, What it does, Hosted Demo, Demo Video, Architecture, How we built it,
  How to run it. The hosted demo link is mandatory and the demo itself must cover the SonyLIV
  guideline items, meaning the concurrency curve and the filters have to be usable at that URL.
- [ ] 14.6 Architecture: a diagram or explanation. Covering it inside `README.md` is acceptable for
  the SonyLIV track.
- [ ] 14.7 Demo video, 2 to 3 minutes, recorded. Must show the concurrency curve and the filters
  working live, and must show the LibreChat flow end to end.
- [ ] 14.8 `pitch-deck.pdf` at the folder root.
- [ ] 14.9 Track extras: the unseen-day answers, the latencies, and the query-log evidence from
  Phases 9 and 10 travel with the submission as committed artifacts.
- [ ] 14.10 Open the pull request titled exactly `[Submission] <Team Name>`.

## Phase 15. LibreChat evidence, since it is now our only OSS-stack claim

The root README is blunt: "we had it running" is not evidence, and superficial inclusion scores
nothing on the ClickHouse and OSS Stack criterion, which is the heaviest at 25 percent. Removing
ClickStack means this phase carries that entire 25 percent on its own.

- [ ] 15.1 Commit the wiring: `librechat/docker-compose.override.yml` (the `mcp-clickhouse`
  service), the root `docker-compose.yml`, and the integration code in `frontend/src/lib/ask.ts`
  plus the `/api/ask` and `/api/v2/ask` routes.
- [ ] 15.2 Commit `librechat/librechat.yaml` and the custom endpoint, agent and tool definitions,
  with every key redacted.
- [ ] 15.3 Commit an `.env.example` covering every variable the stack reads, secrets redacted.
  Today's `.env.example` carries only the five `CH_*` variables and is badly out of date.
- [ ] 15.4 Explain LibreChat's role in the README architecture section: which part of the pipeline
  runs through it. Specifically that Ask AI reaches ClickHouse through `mcp-clickhouse` as the
  read-only `phoenix_ask` user, with the database scope pinned server-side per console.
- [ ] 15.5 Show it live in the hosted demo and in the video. A screenshot is explicitly not proof.
- [ ] 15.6 Because Phase 7 makes the user supply their own API key, the README must give judges
  either a test key or an unambiguous path to use their own, or the Ask flow is unreviewable. Show
  the full chat flow in the video regardless.
- [ ] 15.7 No Langfuse claim is being made. Do not leave the `docker-compose.langfuse-fanout.yml`
  artifact in the submission implying otherwise.
