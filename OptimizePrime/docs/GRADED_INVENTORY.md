# GRADED_INVENTORY.md — what is actually installed on `sonyliv`, object by object

> **Summary:** Full evidence-backed inventory of the graded database, taken 2026-08-02 (read-only).
> All 58 objects + 5 UDFs enumerated and dated; **nothing unexplained** — every object traces to repo
> tooling run as user `default`. Two drift families: the **user tier is pre-ADR-0016** (`mv_user_minute`
> live, `cc_user_minute` still AggregatingMergeTree — a publisher run today would silently inflate it),
> and five **windows views are pre-ADR-0014** (no peak-minute tie-break). Reconcile PASSES (17,028
> minutes, 0 mismatch, peak 2,917). Also: publisher smoke-ran once (0 sessions, rolled back), 6 scratch
> databases are still on the service. Evidence: `evidence/graded-inventory/`. Drift check: `ddl_diff.py`.

**Taken:** 2026-08-02, read-only, per Q31. **Method:** render the repo's SQL into a local scratch
database (`inv_drift`), then diff normalized DDL against Cloud `system.tables` — plus
`system.{mutations,parts,projections,data_skipping_indices,dictionaries,functions,users,grants,query_log}`.
Raw captures in [`evidence/graded-inventory/`](../evidence/graded-inventory/); the diff prototype is
[`evidence/graded-inventory/ddl_diff.py`](../evidence/graded-inventory/ddl_diff.py).

**Verdicts used** (extends the brief's three: nothing earned *unexplained*):

| Verdict | Meaning |
|---|---|
| **expected** | Matches what the repo at `dev` HEAD creates, byte-identical after normalization |
| **stale** | Created by an earlier, sanctioned repo generation; `dev` HEAD has since changed the definition and the change was never applied to Cloud |
| **undocumented** | Present and working, but no ADR/doc records the install (or docs contradict each other) |
| **unexplained** | Nobody can say where it came from — **zero objects earned this** |

---

## 1. Headline findings, ranked by what they cost if wrong

### F1 · The whole user tier is pre-ADR-0016 — `mv_user_minute` is live, and a publisher run would silently corrupt it

Cloud state (all three verified, `17-ddl-diff.txt`):

- `mv_user_minute` **exists and is live** — the repo retired it (`sql/45_user_concurrency.sql:55`
  `DROP VIEW IF EXISTS mv_user_minute`). Created 10:48, dropped + recreated 13:45–13:46, never removed.
- `cc_user_minute` is **`SharedAggregatingMergeTree` with no `computed_at`** — repo says
  `ReplacingMergeTree(computed_at)` (ADR 0016).
- `v_user_concurrency_minute` / `_total` lack the repo's `FINAL` + `HAVING concurrent_users > 0`.

This is *documented as not applied* — ADR 0016 says "nothing applied to `sonyliv`" — so it is **stale,
not rogue**. It is also currently **harmless**: the 16:39 full rebuild TRUNCATEd and repopulated the
table in one pass (91,692 buckets, cascaded through the MV — `21-insert-history.txt` shows the
122,015-row write = 30,323 intervals + 91,692 buckets), and with exactly one write generation, union
and replace give the same answer.

**What it costs if wrong:** the moment anything *incremental* writes `session_intervals` on Cloud —
`tools/publish.sh` above all — the live MV union-merges partial `uniqExact` states into buckets that
can never retract. The publisher's `users`-phase INSERT names only 5 columns, so **it succeeds** on
the old table; nothing fails loudly. ADR 0012 measured this exact failure class at **2,953 served vs
2,844 true (+3.8%)**. On the unseen day, with the publisher looping, that is a silent wrong answer on
every user-level question. **Decision needed before any publisher run on Cloud** (see §6-P1).

### F2 · Five windows views are pre-ADR-0014 — no peak-minute columns, no earliest-minute tie-break

`v_cc_minute_series`, `v_cc_minute_series_total`, `v_cc_rolling_dim`, `v_cc_rolling_total`,
`v_cc_window_range` on Cloud date from the 11:02 apply and predate commit `0446423` (ADR 0014). Cloud's
copies contain **zero `argMax` tie-breaks** (repo has 15) and none of the `peak_*_minute` / `pk_min`
columns.

**What it costs if wrong:** benchmark queries b01–b04, b10, b11 read `v_cc_window_range`. The recorded
bench run (16:54, against Cloud) passed because those queries don't select a peak *minute* at range
grain. If a graded or unseen-day question asks "peak **and when**" over a ragged range, Cloud either
cannot answer from this view (missing column) or — if patched ad hoc — answers with an **arbitrary
tie**, which ADR 0014 exists to prevent. Peak-value/average numbers are unaffected.

### F3 · The publisher was not just installed — it ran once, claimed 0 sessions, and rolled back

`sql/12_publish.sql` was applied to `sonyliv` at **15:38:16–18** (native protocol, `apply-sql.sh`,
user `default`). At **15:38:31** an `INSERT INTO cc_publish_batch` claim ran and wrote **0 rows**
(`session_dirty` was empty — `mv_session_dirty` was created *after* the one-and-only `ev_raw` load),
and at **15:38:32** the empty partition `1785598710629` was dropped (`20-attribution.txt`,
`11-ddl-sonyliv-only.txt`). Since then: `cc_publish_runs` 0 rows, cursor at epoch
(`v_cc_publish_lag`: `publish_cursor = 1970-01-01`), `session_dirty` 0 rows.

**Documentation conflict:** WALKTHROUGH §"Publish continuously" *does* now record the install
("Installed on `sonyliv` but has never committed a run") — but **ADR 0013 line 13 still says "never
applied to `sonyliv`"** and its closing section says going live "is a human's call" as if it hadn't
happened. One of them is wrong; the database says it's ADR 0013 (see §6-P3).

**What it costs if wrong:** by itself, nothing — four empty tables and an MV that fires per `ev_raw`
insert (cheap GROUP BY per block). The cost is F1: this schema being live is the loaded gun that a
`publish.sh` run fires.

### F4 · `proj_by_session` — now regularised by ADR 0021; DDL matches the repo

ADD PROJECTION + MATERIALIZE at **10:12:11–13** via curl as `default` (`system.mutations` +
`20-attribution.txt`). Active: 7 parts, **3.42 MiB vs 7.06 MiB base** (my measurement; the +93.9%
figure in Q31's brief used the pre-mutation base). After ADR 0021 and the `sql/60_projection.sql`
fix, the normalized DDL diff shows `ev_raw` **byte-identical** to the repo render, projection
included — this one is now **expected**. Residue: WALKTHROUGH §5 still says "not shipped" (§6-P4).

### F5 · Six scratch databases are still on the graded service

`sonyliv_q29vis` (7.13 MiB), `sonyliv_q8scratch`, `sonyliv_trunc` (8.31 MiB), `sonyliv_unseen`,
`sonyliv_unseen_q26` (**empty** — 0 tables), `sonyliv_verify` (5.54 MiB) — `10-databases.txt`,
`19-other-databases.txt`. Others (`sonyliv_pub`, `sonyliv_pub_ctl`, `sonyliv_q25`, `sonyliv_lgtest_*`)
were created and dropped the same day. `default` is empty.

**What it costs if wrong:** no risk to `sonyliv` data; the costs are judge-facing clutter, ~21 MiB,
and — the real one — **the pattern**: scratch databases that outlive their session are how "which
database am I in?" mistakes eventually happen. Cleanup is a human's call; **this inventory deletes
nothing** (§6-P5).

### F6 · `cc_minute_delta`'s PRIMARY KEY is the migrated shape, not the fresh-create shape

Cloud: `PRIMARY KEY (platform, country, content_id, minute)` with the 8-column extended `ORDER BY`.
A fresh create from `sql/10_intervals.sql` gets an 8-column PK. This is exactly what the repo's own
migration produces (`MODIFY ORDER BY` at 11:22 keeps the old PK — all 11 mutations in
`03-mutations.txt` are the repo's own `10_intervals.sql` ALTERs). **Benign and expected-by-migration**:
the PK is the index prefix either way, and the four appended dims are low-cardinality suffixes.
Worth knowing so the DDL diff's flag on it doesn't read as news (§6-P6 proposes recording it in the
file's comment).

### Verified explicitly, per the brief

- **`cc_hour_agg` engine**: `SharedReplacingMergeTree(computed_at)` — correct and identical to repo.
  (ADR 0016's engine change was to `cc_user_minute`; `cc_hour_agg` was *already* Replacing — that
  part "took" because it never needed applying.)
- **Reconcile at inventory time: PASS** — 17,028 minutes, 0 mismatched, max_abs_diff 0, peak 2,917
  (`18-reconcile-at-inventory.txt`, read-only run of `sql/90_reconcile.sql`). The drift above is
  entirely in *dormant* paths; the graded minute/hour path serves correctly today.
- **Row counts** unchanged since the 16:54 bench (`ev_raw` 905,558 · `session_intervals` 30,323 ·
  `cc_minute_delta` 28,073 · `cc_hour_agg` 26,254) — nothing has written to `sonyliv` since.

---

## 2. Every object, with verdict and date

All times 2026-08-01 UTC (server tz UTC). "Identical" = byte-identical to the repo render after
normalization (strip db qualifiers/backticks/`Shared*` zk args/UUIDs; `17-ddl-diff.txt`).

### Tables (11)

| Object | Engine (Cloud) | Rows | Verdict | Dated | Note |
|---|---|---|---|---|---|
| `ev_raw` | SharedMergeTree | 905,558 | **expected** | loaded 08:39:36, projection 10:12 | Identical incl. 2 skip indexes + projection. Loaded exactly once (996,850 written = 905,558 + 91,292 MV cascade) |
| `content_dim` | SharedReplacingMergeTree | 33,464 | **expected** | loaded 08:39:10 | Identical |
| `session_intervals` | SharedReplacingMergeTree(build_version) | 30,323 | **expected** | dims ALTER 11:22, rebuilt 16:39:13 | Identical incl. `idx_start` |
| `cc_minute_delta` | SharedAggregatingMergeTree | 28,073 | **expected** (migrated shape) | dims+ORDER BY ALTER 11:22, rebuilt 16:39:18 | F6: 4-col PK vs fresh-create 8-col PK — repo's own migration artifact |
| `cc_minute_stateless` | SharedAggregatingMergeTree | 91,292 | **expected** | populated 08:39:36 | Identical; insert-time tier, untouched since load |
| `cc_user_minute` | SharedAggregatingMergeTree | 91,692 | **stale** (pre-ADR-0016) | created 13:46:05, rebuilt 16:39:14 | F1: repo says ReplacingMergeTree(computed_at). Consistent today, corrupts under incremental writes |
| `cc_hour_agg` | SharedReplacingMergeTree(computed_at) | 26,254 | **expected** | rebuilt 16:39:21 | Identical — engine verified per brief |
| `session_dirty` | SharedMergeTree | 0 | **expected** | created 15:38:16 | Identical; empty because no `ev_raw` insert since its MV exists |
| `cc_publish_batch` | SharedMergeTree | 0 | **expected** | created 15:38:17 | Identical; F3 — one empty partition created + dropped 15:38:31–32 |
| `cc_publish_consumed` | SharedReplacingMergeTree | 0 | **expected** | created 15:38:17 | Identical; cursor at epoch = table empty |
| `cc_publish_runs` | SharedMergeTree | 0 | **expected** | created 15:38:18 | Identical; zero runs ever committed |

### Materialized views (3)

| Object | Verdict | Dated | Note |
|---|---|---|---|
| `mv_stateless` | **expected** | 08:38:38 | Identical; wrote its tier during the one load |
| `mv_session_dirty` | **expected** | 15:38:16 | Identical; fires per `ev_raw` insert, none since |
| `mv_user_minute` | **stale — the only object the repo does not create** | created 10:48:25, recreated 13:45–13:46 | F1: retired by ADR 0016, still **live** on Cloud. LIVE writer into `cc_user_minute` on any `session_intervals` insert |

### Dictionary + UDFs (6)

| Object | Verdict | Dated | Note |
|---|---|---|---|
| `dict_content` | **expected** | 13:08:18 | Identical (`14-dict-ddl.txt`); status LOADED, last successful reload 17:43:09, no exception |
| `norm_case`, `norm_lang`, `norm_version`, `norm_app_version`, `lang_class` | **expected** ×5 | ~16:39 (with `15_normalise.sql`) | Bodies identical to repo (`07-udfs.txt`). Server-scoped, not per-database |

### Projections & skip indexes

| Object | Verdict | Dated | Note |
|---|---|---|---|
| `ev_raw.proj_by_session` | **expected** (since ADR 0021) | 10:12:11–13 (mutations) | F4: 7 active parts, 3.42 MiB. DDL identical to `sql/60_projection.sql` |
| `ev_raw.idx_content` (bloom), `ev_raw.idx_ts` (minmax), `session_intervals.idx_start` (minmax) | **expected** ×3 | with their tables | All in repo DDL (`05-skip-indexes.txt`) |

### Views (43)

**37 identical → expected.** The full graded serving path is among them:
`v_concurrency_minute`, `_total`, `_stateless`, `_intervals`, `_intervals_dim`, `_delta_total`,
`_naive`, `_content`, `_title`, `_category`, `_video_type`, `_audio_norm`; `v_concurrency_title_now`,
`v_concurrency_category_now`, `v_concurrency_video_type_now`; `v_cc_minute_delta_norm`,
`v_cc_watermark`, `v_cc_publish_lag`, `v_cc_tumbling_dim`, `_hour`, `_total`;
`v_content_orphan_check`, `v_content_title_collisions`, `v_dimension_drift`, `_summary`; and the
seven from `87_viz.sql` (`v_session_minutes`, `v_cc_by_platform`, `_country`, `_app_version`,
`_audio_language`, `_subtitle_language`, `_player_version`) — those seven verified against the repo
text directly because `87_viz.sql` cannot render into a scratch db (hardcoded
`sonyliv.dict_content`, §6-P2).

**6 stale → the two drift families:**

| View | Dated | Missing vs repo | Family |
|---|---|---|---|
| `v_concurrency_hour`, `_hour_total`, `_day`, `_day_total` | 16:39:22–23 | `(peak != 0 OR integral != 0)` zero-row filter | pre-ADR-0016 — a retracted hour would serve zeros instead of no-row. Cosmetic until retraction exists on Cloud |
| `v_user_concurrency_minute`, `_total` | 13:46:07 | `FINAL` + `HAVING > 0` | pre-ADR-0016 — correct only while `cc_user_minute` has a single write generation (F1) |

| View | Dated | Missing vs repo | Family |
|---|---|---|---|
| `v_cc_minute_series`, `_total`, `v_cc_rolling_dim`, `_total`, `v_cc_window_range` | 11:02:55–57 | all `argMax` earliest-minute tie-breaks, `peak_*_minute` / `pk_min` columns | pre-ADR-0014 (F2) |

### Mutations (11 — the complete `system.mutations` history)

All done, none failed (`03-mutations.txt`): 10:12:11–13 projection ADD+MATERIALIZE on `ev_raw` (×2);
11:22:04 the `10_intervals.sql` migration — 4 ADD COLUMN + 1 MODIFY ORDER BY on `cc_minute_delta`,
4 ADD COLUMN on `session_intervals`. Every one matches a statement in the repo. **No mutation is
unaccounted for.**

### Server level

Users: 11 Cloud-internal + `default` + `sql-console` + two human console identities
(`barundebnath91@gmail.com`, `mitalilaroia3@gmail.com`) — **every DDL/write in the log ran as
`default` via repo tooling** (curl = `tools/ch`-family, native = `apply-sql.sh`); zero console-user
DDL (`20-attribution.txt`). 15 settings profiles, 2 quotas: ClickHouse Cloud stock. 0 row policies,
0 named collections.

---

## 3. Timeline of every write that shaped `sonyliv` (2026-08-01 UTC)

| Time | What | Evidence |
|---|---|---|
| 08:38–08:39 | Schema created; `ev_raw` (905,558) + `content_dim` (33,464) loaded **once**; `mv_stateless` populated its tier | `21-insert-history.txt` |
| 10:12 | `proj_by_session` ADD + MATERIALIZE (the incident later regularised by ADR 0021) | mutations, `20-attribution.txt` |
| 10:48 | User tier v1 installed (`cc_user_minute` + `mv_user_minute`) | `20-attribution.txt` |
| 11:02 | Windows views applied (pre-ADR-0014 generation — still current on Cloud, F2) | metadata times |
| 11:22 | Seven-dimension migration: 9 ALTERs on `cc_minute_delta` + `session_intervals` | mutations |
| 13:02–13:59 | Repeated `cc_user_minute` TRUNCATEs + drop/recreate at 13:45–46 (model-build iterations) | `20-attribution.txt` |
| 13:08 | Content enrichment (`dict_content` + content views) | metadata times |
| 13:10 | `sonyliv.ev_raw` copied **out** to `sonyliv_verify` (read, not a write to `sonyliv`) | `21-insert-history.txt` |
| 15:15 | `87_viz.sql` views applied | metadata times |
| 15:38 | Publisher schema installed; smoke claim ran, 0 sessions, partition dropped (F3) | `20-attribution.txt` |
| 16:39 | **Full model rebuild** — last write to `sonyliv`: intervals 30,323 → deltas 28,073 → hours 26,254 → user buckets 91,692 (via still-live MV); `15_normalise` + serving views re-applied (pre-0016 view generation) | parts, `21-insert-history.txt` |
| 16:54 | Benchmark evidence run (read-only) — row counts identical to now | `evidence/benchmark/results/meta.env` |

**Dating caveat:** Cloud's `system.query_log` is replica-local and non-durable — at inventory time it
covered only 08:17→18:38 on 2026-08-01. Durable evidence is `system.mutations`, `system.parts`
`modification_time`, and `metadata_modification_time`; the timeline above cross-checks all three.
Anything that happens while no replica survives to flush its log **will not be datable this way** —
one more reason for the committed-baseline check below.

---

## 4. How to detect this drift automatically next time

The one-off is worth little; the re-runnable check is the deliverable. **Proposed: `tools/graded-drift.sh`**
(prototype: [`evidence/graded-inventory/ddl_diff.py`](../evidence/graded-inventory/ddl_diff.py) — it
found every finding in this document). Four comparisons, each printing PASS/FAIL:

1. **DDL render-diff** (the core): apply the object-creating SQL files (`00, 10, 12, 15, 20, 45, 50,
   60, 80, 85, 87`) to a **local** scratch db, then compare normalized `create_table_query` per object
   against Cloud. Normalization: strip db qualifiers, backticks, `Shared` engine prefix + zk-path
   args, UUIDs. FAIL on: object only on Cloud, object only in render, or body mismatch.
   *Blocked today by §6-P2 (87_viz hardcodes `sonyliv.`); until fixed the script must carry a 7-view
   textual fallback, which is exactly the kind of special case that rots.*
2. **Mutation baseline**: `system.mutations` count + `max(create_time)` vs the committed snapshot
   (`03-mutations.txt`, 11 rows). Any new mutation = a schema-shaping write nobody recorded.
3. **Database allowlist**: `system.databases` vs `{default, sonyliv, system, INFORMATION_SCHEMA,
   information_schema}` — flags scratch leftovers like F5 the day they appear.
4. **Writer sweep** (best-effort, non-durable): any `query_log` write/DDL against `sonyliv` since the
   last committed run stamp, excluding known tool user-agents — catches out-of-band console writes
   *while a replica's log survives*.

UDFs (`system.functions` vs `15_normalise.sql`), projections, and skip indexes ride along in check 1
(they appear in table DDL / dedicated system tables). Run it in the same breath as `/reconcile`:
reconcile proves the *numbers* match raw; drift-check proves the *machinery* matches the repo.

---

## 5. What was enumerated (so "nothing found" means "I looked")

`system.tables` (58 objects in `sonyliv`: 11 tables, 3 MVs, 43 views, 1 dictionary — full DDL
captured), `system.databases` (11), `system.functions` (5 non-system), `system.dictionaries`,
`system.projections` + `projection_parts`, `system.data_skipping_indices` (3),
`system.mutations` (11, complete), `system.parts` (active-part dating for all 7 data-bearing tables),
`system.users` (14) / `grants` / `settings_profiles` (15) / `quotas` (2) / `row_policies` (0) /
`named_collections` (0), and `system.query_log` across replicas (6,102 DDL rows → 1,229 touching
`sonyliv`, 215 inserts — every one attributed). Plus a read-only reconcile run. **Zero objects
unexplained; zero mutations unaccounted; zero out-of-band writers.**

## 6. Proposals (this inventory changes nothing itself)

- **P1 · Decide the ADR 0016 migration before any publisher run on Cloud** (owner: human + unseen-day
  runbook). Either apply the sanctioned migration (build-model.sh's guarded pre-0016 detection: drop
  `mv_user_minute`, recreate `cc_user_minute` as Replacing, re-apply `45`/`50` views) **before** the
  unseen day, or forbid `publish.sh` phases `users`/`hours` against Cloud until it happens. Running
  the current publisher against the current Cloud state fails **silently**, not loudly (F1).
  `docs/RUNBOOK_UNSEEN.md` should gate on this explicitly.
- **P2 · Make `sql/87_viz.sql` database-agnostic**: `dictGet('sonyliv.dict_content', …)` →
  `dictGet('dict_content', …)` (resolves in the current database, same ADR 0010 pattern that fixed
  `60_projection.sql` — and the same class of bug that caused yesterday's incident). Until then the
  file cannot be applied to any scratch database and blocks drift-check §4.1.
- **P3 · Amend ADR 0013**: its summary line ("never applied to `sonyliv`") and closing ("going live
  is a human's call") are contradicted by the 15:38 install + smoke run (F3). One sentence each,
  pointing here.
- **P4 · Update WALKTHROUGH §5**: "measured and not shipped" → shipped and kept, per ADR 0021 (F4).
- **P5 · Human call: drop the six scratch databases** (F5) — or keep `sonyliv_verify` if wanted, but
  say so somewhere. Not done here: read-only task, and "I was just tidying up" is how incident #2
  happens.
- **P6 · Record the migrated-PK shape** of `cc_minute_delta` in `sql/10_intervals.sql`'s migration
  comment (F6), so the drift check can whitelist it deliberately instead of re-flagging it forever.
