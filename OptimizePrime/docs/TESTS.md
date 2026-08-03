# TESTS — the catalog

> **Summary:** What is tested, what each test actually proves, and the anti-patterns that make a green
> suite meaningless here. The load-bearing test is `/reconcile` — everything else is secondary. Tests
> that assert against the serving layer alone prove nothing; correctness tests must recompute from
> `ev_raw`.

## The suite

| Test | Proves | Run by |
|---|---|---|
| `/verify-env` | the stack is actually configured — schema present, users real, constraints active | after any env change |
| **policy check** | the one declaration ([ADR 0032](adr/0032-one-versioned-policy-declaration-read-by-every-consumer.md)) and everything derived from it are in step: `sql/01_policy.sql` is a current rendering of `policy/model.policy` (a hand-edit fails), every publisher cover is `>= TAIL_S + 60` (the latent break DYNAMIC_PARAMS §A2 found and nothing enforced), the queue TTLs in `sql/12_publish.sql` equal `QUEUE_TTL_DAYS`, and **no consumer has grown its own literal back** — the model, the gate, the oracle and both generators are grepped for the pattern the constants used to be written in. Add `--database DB` to also assert the deployed view matches the tree | `tools/policy.sh check` — in `tools/test-all.sh` and at stage 0/6 of `tools/build-model.sh`, which refuses to build on a stale rendering. Evidence: `evidence/policy/` |
| `/reconcile` | the serving layer equals the truth recomputed from raw | after **every** model change |
| `/bench` | benchmark latency and, more importantly, **bytes read** | before demo / unseen run |
| **truncation / absorption test** | the model absorbs mid-stream truncation and a late arrival **incrementally**, converging on the from-scratch answer. Covers the open-session and late-arrival probes below in one run | `tools/truncation-test.sh` — after any change to `session_intervals`, its engine, or the delta emission |
| **partition-safe backfill test** | 130 **sparse** output dates, including the non-start days of a 25-hour interval, are enumerated from accepted `session_intervals` and built in exactly 3 chunks per day-partitioned tier (64/64/2); asserts exact user and OPEN/CLOSE delta rows, so Cloud-safe batching cannot silently omit later days of a long interval | `tools/chunked-backfill-test.sh` — in the fast suite; after any change to `tools/chunked-backfill.sh`, SQL40's backfill anchor, SQL45's backfill anchor, or either full-rebuild caller |
| open-session probe | the model absorbs sessions with no `VideoSessionEnd` | folded into the truncation test (52.6% of sessions are open at the cut) |
| late-arrival probe | a heartbeat arriving after its minute was aggregated updates the served value | folded into the truncation test (447,081 events arrive after the cut) |
| hour-clip probe | an interval spanning ≥3 hours reads correctly **at a minute inside the middle hour** — the case that fails if clipping is wrong | after any change to delta emission |
| **continuous-publication test** | the aggregates move **without a rebuild** and land byte-identical to one — on ALL FOUR serving tiers (minute deltas, intervals, user-minute buckets, hour/day cube — ADR 0016). Covers the straggler, open-session, bootstrap, SHRINK (a late pause pulls an interval_end earlier), DIMENSION-FLIP (late events change an interval's dominant platform) and idempotence probes in one run | `tools/publish-test.sh` — after any change to `sql/12_publish.sql`, `tools/publish.sh`, `sql/30_build_intervals.sql`, `sql/40_deltas.sql`, `sql/45_user_concurrency.sql` or `sql/50_hour_agg.sql`. Evidence: `evidence/publish.txt` |
| straggler probe | a heartbeat dated **46 minutes behind the watermark** moves the served value AND matches a from-scratch rebuild on all 1,579 minutes — not merely "the value changed", which is the anti-pattern ADR 0006 names | folded into the publication test |
| vanishing-interval probe | a straggler bridging a gap merges two runs, so an `interval_start` ceases to exist; asserts **0 orphan rows** survive. `ReplacingMergeTree` cannot delete a key, so without the prune phase this silently over-counts for ever | folded into the publication test |
| bootstrap-equals-steady-state probe | the FIRST publish run on an empty database (every session dirty) produces exactly what a batch rebuild produces — there is no separate initial-build path to drift | folded into the publication test |
| publication idempotence probe | republishing 200 **unchanged** sessions moves 0 of 1,579 minutes — the property that makes replays, resumed runs and forced corrections safe | folded into the publication test |
| tail-sensitivity sweep | peak/avg across `HEARTBEAT_GAP_S` ∈ {120,150,180} × `TAIL_GRACE_S` ∈ {0,60,150} — proves robustness, or names the point we knowingly chose | before submission |
| **normalisation self-test** | the dimension-normalisation rule behaves — 24 `throwIf` assertions over **literals only**, so it needs no tables and fails at apply time (Code: 395) rather than as a wrong dashboard number. Includes negative assertions: `jap` must **not** merge with `jpn`, `norm_version` must **not** strip a subtag from `v-0.0.117.12.05.1_adNE`, `9.0.0` must **not** fold to `9` | runs automatically whenever `sql/15_normalise.sql` is applied |
| **landing-boundary test** | proves [ADR 0030](adr/0030-all-string-landing-table-makes-cast-failure-per-row.md): the real file loaded through the all-`String` landing table is **byte-identical** in `ev_raw` and `content_dim` to the pre-landing typed `input()` (order-free fingerprint over every column), the gate on a model built that way still reads 17,028 / 0 mismatched / peak 2,917, one corrupted `event_timestamp` costs **1 row instead of 905,558**, a phase-B fault rolls the typed tables back to empty, a REFUSED load creates nothing at all, and the cost is measured rather than claimed. 22 assertions | `tools/landing-test.sh` — after any change to `tools/load.sh` or `sql/05_landing.sql`. Evidence: `evidence/landing/identity.txt` |
| **entry-point agreement test** | the two doors into the pipeline agree about what a valid file is: **anything the contract gate passes, `tools/unseen-run.sh` must accept**. Q37 found two valid files the gate passed and the runner refused — an RFC-4180 quoted embedded newline (`wc -l` counted 99 records where the parser and the loader both saw 98, killing a load that was clean: `landed 98 = typed 98 + rejected 0`) and a new filter column (refused against a fixed 13-column header string, although ADR 0024 carries it into `extra`, 128/128 rows). A green pre-flight followed by a failed run is the worst sequence available on a one-attempt day. Carries **both-refuse controls**, so agreement cannot be earned by a guard that stopped guarding | `tools/contract-runner-agreement.sh` — after any change to `tools/unseen-run.sh`, `tools/load.sh`'s `analyse_header()`, or `tools/validate-source-contract.sh`. Evidence: `evidence/q37/` |
| **dimension drift audit** | every normalisation group carrying more than one raw spelling is listed from `ev_raw` — so an unseen day's new value family is *seen* rather than silently splitting a bucket. On the provided file: audio 14 groups / 903,857 rows, subtitle 4 / 897,227, app_version 1 / 872, and **zero** for platform/player_version/country | `SELECT * FROM v_dimension_drift_summary` — **before** trusting any filtered number from the unseen day |

## How to write a correctness test here

Recompute from `ev_raw`. A test that compares `cc_minute_delta` against a view over
`cc_minute_delta` proves only that arithmetic is deterministic.

## Anti-patterns — these make the suite lie

- **Asserting on the serving layer only.** The whole risk is that the model is wrong; comparing it to
  itself cannot find that.
- **Testing only on the provided file.** It has **zero open sessions** — the path most likely to break
  on the unseen day is completely unexercised. Truncate the file to create one.
- **Testing only `country`.** It has a single value; a filtering bug is invisible. Always also test
  `platform` (10 values).
- **Trusting a green health check.** A failed init script leaves the container `Up` and
  `/api/health` returning `200` with a half-built schema.
- **`set -e` in a script that pipes to `tee`.** It does not fire — the script reports success while
  writing empty files. Use `set -euo pipefail`.
- **Asserting a corrected value merely *changed*.** After a straggler lands, the served number must
  equal a brute-force recomputation from `ev_raw` — "it moved" passes even when it moved to the wrong
  value.
- **Trusting approximate aggregates in a correctness test.** `uniq` carries 1–2% error. A reconcile
  that compares two `uniq` results agrees with itself while both are wrong. Use `uniqExact` everywhere
  a number is served or asserted.


## Model reconciliation (H2/H3)

Run by `tools/build-model.sh` on every rebuild; it fails loudly rather than printing a warning.

| Test | What it catches |
|---|---|
| Delta serving layer vs interval expansion, **every minute** | any error in hour-clipping, merging or the running sum. Currently PASS on 3,725 minutes, peak 2,887 |
| **Hour-clipping, interior hour** (ADR 0003) | an interval spanning >= 3 hours checked at a minute inside the MIDDLE hour. Worked case: `20:59:48 -> 22:04:49` must emit `+1 @20:59`, `+1 @21:00`, `+1 @22:00`, `-1 @22:05` and NO close in hours 20 or 21 |
| Same-minute interval merge | a session that pauses and resumes inside one minute. 4,797 sessions (44%) hit this; without the merge the delta model double counts and 556 of 1,903 minutes were wrong |

**Anti-pattern that already bit us:** comparing the two models only on minutes where deltas *change*
passes trivially (1,466 minutes, 0 mismatches) while the model is still wrong. The comparison must be
densified with `WITH FILL` so every minute is checked.


## Truncation / open-session absorption (H4/H8)

`tools/truncation-test.sh` · schema in `sql/70_truncation_test.sql` · output `evidence/truncation.txt`

Cuts the stream at the global peak (`2026-07-26 10:56:00`), builds the whole model on the stump,
inserts the withheld 447,081 events as a late arrival, absorbs them by ADR 0006 correction-by-diff,
and compares against a from-scratch build **and** against production, on every minute.

**Runs entirely in the `sonyliv_trunc` database.** `sonyliv` is read with `SELECT` only, and
`assert_isolated()` refuses to execute any templated file naming production as a write target. The
derivation SQL is `sed`-templated out of `sql/30_build_intervals.sql` and `sql/40_deltas.sql` rather
than reimplemented, so the test cannot drift from the model it tests.

| Sub-check | What it catches | Status |
|---|---|---|
| control build vs production, every minute | non-determinism in the derivation | PASS — 2,887 @10:56 and 2,450 @11:10, exact |
| incremental absorption vs control, every minute — **`build_version`, i.e. what production runs** | anything that makes incremental ≠ rebuild | **PASS** — `CONVERGES` on all 1,578 minutes, peak **2,887** (`evidence/truncation.txt`) |
| the same, on the retained `interval_end` variant | that the test can still **detect** the historical defect | DIVERGES by design — 3 of 1,578 minutes, +37 at the peak. This is the regression guard firing, **not** a report that we have the bug |
| delta arithmetic isolated from interval state | whether ADR 0006's negate-and-re-emit is itself lossy | PASS — exact on all 1,578 minutes |

**This test is two-sided — read both rows before concluding anything.** `sql/70_truncation_test.sql`
deliberately **keeps** a `ReplacingMergeTree(interval_end)` variant so the historical defect stays
detectable; the `build_version` variant is the one production runs. Until `1dee090` this table said
*"FAIL as shipped — 3 of 1,578 minutes, +37 at the peak"*, which was true when written and false
after `388a845`.

**The bug this test found, and where it was fixed.** `session_intervals` *was*
`ReplacingMergeTree(interval_end)`, which resolves duplicates by keeping the **largest**
`interval_end` — justified with "late heartbeats EXTEND an interval", i.e. assuming re-derivation is
monotonically increasing. It is not. A provisional interval carries `TAIL_S = 60s` of grace because
its run appeared to end; the completed derivation places the true end **earlier** (at a pause, or at a
real `VideoSessionEnd` inside the grace window). The stale, longer row then outranked the correct one
permanently and dragged a stale `is_open = 1` with it. Measured: **316 intervals up to 60s too long,
315 stuck at `is_open = 1`, +37 on the peak minute (2,924 vs 2,887, +1.3%).**

- **Fixed in `388a845`** — `session_intervals` is now `ReplacingMergeTree(build_version)`, a monotonic
  build counter; `cc_minute_delta.starts`/`ends` became `Int64` in the same commit.
- **The test itself was repaired in `1dee090`** — it had broken on the ADR 0008 7-dimension schema
  (hard-coded column lists, a dead `sed` anchor) and its verdict text still claimed the model did not
  converge.
- **Evidence:** `evidence/truncation.txt` — `CONVERGES  versioned incremental == production truth on
  all 1578 minutes · peak 2887`, and `FIXED  versioned session_intervals is row-for-row identical to
  a clean rebuild`. ⚠️ The trailing `VERDICT` block of that committed run predates the `1dee090`
  verdict-text repair and still reads "does NOT converge"; the machine-compared lines above it are the
  authoritative part, and the next regeneration of the file replaces the block with the two-sided
  wording already in `tools/truncation-test.sh`.

**Second finding — also fixed in `388a845`.** `cc_minute_delta.starts`/`ends` **were**
`SimpleAggregateFunction(sum, UInt64)`, so the negative corrective row ADR 0006 mandates was not
representable. ClickHouse does **not** reject it — it wraps to `2^64 - n`. `sum()` still comes out
right by modular arithmetic, but `max()` returns 1.8e19 and any pre-merge single-row read is garbage.
Both are `Int64` now.

**Anti-patterns specific to this test:**

- **Comparing only the two probe minutes.** The divergence at 10:54 is a single viewer; only the
  all-minutes comparison makes the pattern visible.
- **Rebuilding `cc_minute_delta` during absorption.** That tests nothing — the whole claim is that the
  sealed tier is append-only. The test never truncates it after the stump build.
- **Blaming the diff arithmetic.** Always run the isolation probe before touching ADR 0006; here the
  arithmetic was exact and the fault was two layers upstream.
- **Reading `session_intervals` without `FINAL`.** Pre-merge, the stale and fresh rows are both
  present and every count is doubled.


## Self-observation (H7)

`internal/otelemit`, `internal/pipelinehealth`, `internal/chdb`, `cmd/sonyliv` · `make test` · see
[OBSERVABILITY.md](OBSERVABILITY.md) for what `sonyliv observe` emits and why.

**The Go unit suite is database-free by construction.** Every test runs against fixtures, fakes of
the `driver.Conn` interface, `httptest` collectors, or loopback ports nothing listens on — `make ci`
never opens a connection to any ClickHouse, least of all the graded `sonyliv` database. Coverage
after the 2026-08-01 audit: `pipelinehealth` 90.8%, `otelemit` 95.7%, `chdb` 93.1%, `config` 91.4%
(was 79.6% — the default-resolution paths were unexercised), `cmd/sonyliv` 58.7% (the remainder is
`main`/`cli` and the live-connection halves of `verify`/`observe`, which cannot be unit-tested
without a server and are exercised by `make verify` instead), 77.6% total. Treat these numbers as a
ceiling on ignorance, not proof of coverage — the audit below found eight breaks the pre-audit
suite could not see at almost identical percentages.

| Test | Proves |
|---|---|
| `TestReadReconcileEvidence_GreenFixture` | the parser reads `testdata/reconcile_green.txt` — a byte-for-byte CAPTURE of a real green `tools/reconcile.sh` run (2026-08-01, commit d6c85e2), never a hand-written stand-in. The verdict comes from the SUMMARY row (`minutes_compared=17028`), not from counting sample rows |
| `TestReadReconcileEvidence_MismatchFixture` | a failing gate is surfaced, not averaged away — the fixture is a REAL captured failure (cloud serving-layer drift, 177 mismatched minutes, max abs diff 39) |
| `TestReadReconcileEvidence_OldFormatIsNotAPass` | the pre-81c0161 five-column format — the exact shape the parser once pinned while production output had moved on — parses as NOT a pass: no SUMMARY row means unattested evidence |
| `TestReadReconcileEvidence_OldFormatMismatchStillVisible` | even without a SUMMARY, the row-level fallback still surfaces the historical `+37 at the peak` defect magnitude |
| `TestReadReconcileEvidence_EmptyFileIsNotAPass` / `_MalformedFileIsNotAPass` | an empty or garbage evidence file cannot read as "everything passed" |
| `TestReadReconcileEvidence_SurvivesAddedColumn` | the regression the 2026-08-01 rewrite exists for: adding a column to the gate's table must not silently zero the parse — SUMMARY tokens are key=value, detail rows anchor on the timestamp |
| `TestPass_SummaryGuards` | `Pass()` requires all of: summary present, verdict PASS, ≥1 minute compared, 0 mismatched — a self-contradictory summary fails |
| `TestReadReconcileEvidence_SectionFence` | the `== 1.`/`== 2.` section fence itself: a fully gate-shaped row (timestamp, three ints, PASS) placed outside section 1 must NOT parse into `Minutes`. Added by the 2026-08-01 audit — removing the fence previously survived every test, because no fixture had a verdict-bearing row outside the gate section |
| `TestIntAttrEncodesAsJSONString` | OTLP/HTTP JSON's int64-as-decimal-string mapping is actually followed — a bare `int64` JSON field would lose precision above 2^53 |
| `TestSeverityConstantsAreLowerCase` | `severity:error` saved searches keep matching — HyperDX stores `SeverityText` lower-cased (VERIFIED.md), and this is the one constant a careless edit would recapitalize |
| `TestNewTraceID` / `TestNewSpanID` / `TestNewTraceIDIsRandom` | id shape (16/8 random bytes, lower-case hex) and that two runs do not collide |
| `TestQueryWatermark_*` (`health_test.go`) | the v_cc_watermark sign convention survives the code path: **negative lag is healthy**, positive lag is not; an all-NULL row (fresh database) scans to zero values instead of panicking; a scan failure names the view. Since the audit, all seven columns scan with **distinct** fixture values asserted field-by-field — swapping two scan destinations (raw↔sealed) previously survived a not-zero check |
| `TestQueryBuildStages_*` | stage rows come typed off `system.query_log`; a stage with no recorded run is `Found=false`, **not** an error and not a fabricated row; a real query failure names which stage died. Since the audit, the two queries' load-bearing fragments are pinned (`has(tables, 'db.…')` per stage, `NOT has(…ev_raw)`, `type = 'QueryFinish'`, `query_kind = 'Insert'`) — corrupting a table name in the predicate previously survived, because the fake routed on `NOT has` alone |
| `TestClientPostsEachSignalToItsPath` / `TestClientMetricsWireShape` (`otelemit/client_test.go`) | each signal POSTs to its `/v1/<signal>` path with the ingestion key in `authorization` and the OTLP JSON field names actually on the wire (`asDouble`, `timeUnixNano` as a decimal string) |
| `TestClientNon2xxIsAnError` / `TestClientUnreachableCollectorIsAnError` | a 401 (wrong key) or a dead collector is a loud error carrying the status and response body — not a silent drop |
| `TestClientUnmarshalablePayloadFailsBeforePosting` | a NaN gauge fails at marshal time, before any bytes reach the collector |
| `TestAttrConstructorsEncodeTheTaggedUnion` / `TestSeverityNumberMapsPerOTLPSpec` / `TestLogRecordCarriesBodySeverityAndTraceCorrelation` / `TestGaugeMetricShape` | every constructor sets exactly one arm of the OTLP AnyValue union (`boolValue:false` survives `omitempty`), severity text↔number stay in sync, logs keep their trace correlation |
| `TestTables` / `TestTablesErrors` / `TestServerVersion*` (`chdb_test.go`) | the inventory reads `system.tables` (never per-table `count()`) **with `ORDER BY name`** (deterministic verify output), binds the database as a parameter, closes its rows, and each of the three failure points names itself |
| `TestOpenUnreachable` | a dead endpoint fails **at Open** (via the ping), naming the address and user — for both plain and TLS configs. Target is a loopback port nothing listens on |
| `TestRunDispatch` / `TestVerifyAndObserveRejectBadInputBeforeConnecting` (`cmd/sonyliv`) | CLI dispatch, and that both subcommands reject bad flags / an unknown target **before** any connection attempt |
| `TestObserveRunLifecycle` / `TestNewChildSpanStatus` / `TestObserve*` | one trace per observe run: children parented to the root, a query failure still yields a `StatusError` span, missing reconcile evidence is a legitimate state |
| `TestBuildMetrics` / `TestBuildLogsSeverities` | every gauge **value** (not just its name): lag −90 emits −90, `gate_pass` is 1 on a green gate and 0 with `max_abs_delta=39` on the captured drift failure; metric families with no data behind them are **absent, not zero** (a fabricated 0 reads as healthy on a dashboard); unhealthy watermark and failing/unattested gate log at `error`, missing evidence and never-run stages at `warn`. Before the audit only metric NAMES were asserted — an inverted `gate_pass` and a zeroed lag gauge both survived |
| `TestLoadCloudDefaults` / `TestLoadLocalDefaults` (`config_test.go`) | an all-defaults cloud load resolves to port 8443 with **TLS on** and user `default`; local stays plaintext `localhost:8123` as `app`. Added by the audit — flipping `Secure` to false or the default port to 9000 previously survived, because every test set those variables explicitly |
| `TestPrintSummary` / `TestClampUint64ToInt64` | the human summary names what it could not find; `uint64→int64` clamps at MaxInt64 instead of wrapping negative |

**Anti-pattern avoided:** re-deriving build-stage duration or benchmark-query latency by wrapping a
client-side timer around a re-run query. `system.query_log` already has the real, server-measured
number (and `granules_read`/`bytes_read`, which a client cannot know at all) — a client span would
only ever be a strictly worse copy of data ClickHouse already recorded. See OBSERVABILITY.md's
"what is deliberately not instrumented" section.

**Now covered (was the gap named here until 2026-08-01):** the OTLP emission path
(`internal/otelemit.Client`) has `httptest.Server`-backed tests for the success, 401-wrong-key,
dead-collector and marshal-failure paths (`client_test.go`). The by-hand verification against the
real ClickStack collector (curl probes, then reading rows back out of
`otel_metrics_gauge`/`otel_logs`/`otel_traces` — see OBSERVABILITY.md) remains the ground truth the
fakes were modeled on.

**Not yet covered by an automated test:** the connected halves of `sonyliv verify`/`observe`
(`cmdVerify`/`cmdObserve` past config validation) and the `chdb.Open` success path — all need a live
ClickHouse and are exercised by `make verify` / `sonyliv observe -dry-run` against the local stack
instead.

## False-confidence audit — 2026-08-01

Method (rule 14): for each suspect test, deliberately break the code it claims to cover and confirm
whether the suite notices. A test that stays green through a real break is confirmed false
confidence. Every sabotage was reverted; the fixes below are test-side only.

**10 probes run · 2 caught by the original suite (controls) · 8 survived · all 8 now fixed and
re-probed as caught.** No test reaches a live database — verified by reading every fake/fixture and
by the loopback/`httptest` designs above.

| # | Sabotage | Original result | Fix |
|---|---|---|---|
| A | invert `Watermark.Healthy()` sign | **caught** (control) | — |
| B | drop the `Mismatched == 0` guard from `Pass()` | **caught** (control) | — |
| 1 | invert the `gate_pass` gauge value | survived | `TestBuildMetrics` asserts gauge **values**, both green and failing-gate cases |
| 2 | emit 0 for `sealed_lag_seconds` | survived | same |
| 3 | corrupt `ev_raw` table name in the build-stage `query_log` predicate | survived | `TestQueryBuildStages_BothStagesFound` pins each query's predicate fragments |
| 4 | swap raw/sealed watermark scan destinations | survived | distinct per-column fixture values, asserted field-by-field |
| 5 | flip cloud `Secure` default to false | survived | `TestLoadCloudDefaults` |
| 6 | change cloud default port 8443→9000 | survived | same |
| 7 | remove the reconcile `== 1.`/`== 2.` section fence | survived | `TestReadReconcileEvidence_SectionFence` |
| 8 | drop `ORDER BY name` from `chdb.Tables` | survived | query-content assertion in `TestTables` |

Packages probed and found sound without changes: `otelemit` (wire-level `httptest` assertions pin
paths, headers, exact JSON), `cmd/sonyliv` dispatch, the reconcile fixtures (byte-for-byte captures
whose format matches what `tools/reconcile.sh` writes today — verified by diff against
`evidence/reconcile.txt`; only data values differ, post-model-change).


## H — edge-case matrix (Codex 003 §11, semantic golden tests §13.1)

`tools/edge-test.sh` · fixtures + harness doc in [tests/edge/](../tests/edge/README.md) · scratch db
`edge_matrix`, local-only · run after any change to `sql/30_build_intervals.sql`, `sql/40_deltas.sql`
or `sql/45_user_concurrency.sql`.

32 hand-auditable fixtures, one hazard each, run through the **real** derivation (sed-templated, never
reimplemented). Expected intervals AND expected per-minute concurrency are **derived by hand from the
spec** (ADR 0003/0007/0008/0009, `interval-math`) in each fixture header — never from the model, per
Codex 003 §13.1. All 32 PASS on the shipped model (2026-08-02). Every family is sabotage-checked: 10
named mutations of the production SQL each turn their paired fixture red (`tools/edge-test.sh
sabotage`; ledger with the one instructive miss in [tests/edge/README.md](../tests/edge/README.md)).
Fixtures that pin an **open fork** carry a `FORK` note naming the dossier — they assert the SHIPPED
reading so a silent semantic change is caught, and a mentor ruling names exactly which expectations
to rewrite.

| Fixture | Register row | Proves (and the fork it pins, if any) |
|---|---|---|
| B01 | §11.3 start on minute boundary | exact-boundary start; tail lands the end on a boundary; minutes floor(s)..floor(e) |
| B02 | §11.3 end on minute boundary | interior pause ends a segment EXACTLY on :00 — end minute counted with 0 active seconds (**doubts/05**); also the conservative unclosed-pause rule |
| B03 | §11.3 both ends in one minute | a sub-minute interval yields exactly one active minute |
| B04 | §11.3 zero-length interval | an isolated event (singleton run) produces NO interval, NO tail, NO minute |
| B05 | §11.3 + §11.1 | hour-boundary crossing (ADR 0003 re-open, no close in hour 10); a gap of exactly `GAP_S` does NOT split (strict `>`) |
| B06 | §11.3 | interval ending in the hour's last minute — the `-1` is suppressed, hour 11 shows nothing (asserted 0) |
| B07 | §11.3 day boundary | run crossing UTC midnight: partitions, hour clip and running sums agree |
| B08 | §11.3 end on hour boundary | segment ends exactly at :00:00 of the next hour — re-open + close at 11:01, minute 11:00 counted (**doubts/05** at hour grain) |
| S01 | §11.2 pause→background | bg event renews the run (fail-open), pause becomes interior → NO tail |
| S02 | §11.2 heartbeats during pause | paused beats keep the run alive but never count; the minute DIPS to 0 mid-session |
| S03 | §11.2 unmatched resume | resume with no pause has no state effect (**doubts/02**) |
| S04 | §11.2 pause/pause/resume | overlapping windows fold once, never double-subtract |
| S06 | §11.2 trailing pause | a pause that ENDS its run still collects the +60 tail (**doubts/07** — S01 is the interior contrast) |
| S07 | §11.2 bg/fg liveness | bg/fg events bridge 140 s gaps: 9 minutes credited on one heartbeat pair (**doubts/10, doubts/11**) |
| S08 | §11.3 pause+resume in one minute | the same-minute merge: one viewer, one +1 (the /reconcile-caught double count) |
| O01 | §11.1 same-second pair | resume-before-pause in one truncated second → pause is a no-op (ADR 0009 `>=`; **doubts/08**) |
| O02 | §11.1 out-of-order arrival | newest-first insertion, identical derivation (batch property only) |
| O03 | §11.1 events after end | `VideoSessionEnd` is not terminal: run continues, is_open=0 (**doubts/07**) |
| O04 | §11.1 duplicates | exact duplicate rows change nothing (adversarial ledger row 18) |
| O05 | §11.1 multiple ends | two end events + a lone restart beyond the gap → restart yields nothing |
| L01 | §11.4 late extend | late heartbeat grows the interval; correction adds exactly one minute |
| L02 | §11.4 late shrink | late pause: minutes 10:01–10:03 exist only in the old world and must NET TO ZERO through `old + (−old + new)` |
| L03 | §11.4 late bridge | two runs become one; the old `(session, 10:06:00)` interval key vanishes |
| L04 | §11.4 late dimension flip | attribution flips web→android with time unchanged; the old web tuple must net to zero per-platform |
| D01 | §11.5 dominant + tie | vote 2:2:1 → tie broken by smallest value, deterministically (ADR 0009) |
| D02 | §11.5 mid-session dim change | per-segment attribution at interval level; the minute-merge keeps the EARLIER platform (ADR 0008 first-wins, pinned including its weirdness) |
| D03 | §11.5 unseen dynamic fields | an unknown `experiment_id` key and released `video_resolution` alias survive interval attribution; modal values win deterministically |
| D04 | §11.5 independent dynamic-key votes | keys vote independently instead of as a composite `Map`; reversed input key order cannot change the canonical result |
| D05 | §11.5 missing vs empty dynamic value | missing and explicitly empty are distinct votes; a presence-first tie retains `cohort=''` instead of dropping the key |
| U01 | §11.5 exact users | one user on two simultaneous sessions in one dimension: sessions=2, users=1 |
| U02 | §11.5 exact users across dimensions | one user on web+tv: total users=1 while sum(per-platform users)=2, proving user counts are not additive |
| U03 | §11.5 multi-user session | one session id carries two users across a pause: sessions=1 and users=2 at the overlap minute; grouping only by session erases a viewer |

**§11 rows deliberately NOT implemented here** — silent omission reads as coverage, so they are named:

- **§11.1** session ID reuse across days/devices; future-dated timestamps / invalid epochs / clock
  rollback (no defined spec to derive an expectation from — needs a mentor ruling first); two
  legitimate events with identical payload but different source offsets (the schema has no source
  offset to distinguish them by).
- **§11.2** buffering/seek/ad/casting/error signals *as non-watchable states* (the shipped model has
  no such states — S07 pins the fail-open reading; the fail-closed alternative is measured in
  `evidence/liveness/`, decision pending doubts/10–11); explicit end + delayed older heartbeat vs
  genuine restart (needs the §12.2 Q9 reopen rule).
- **§11.3** non-UTC/DST zones (out of scope: both servers verified UTC, adversarial row 16; the
  harness preflight enforces UTC); empty query range / range of only zero minutes and ranges
  starting inside an hour (query-layer concerns — `evidence/benchmark/` b09–b11 territory, not
  derivation fixtures).
- **§11.4** events older than queue TTL / watermark / compacted state; processor crash points; two
  concurrent finalizers; dedup-window expiry — all **publisher coordination**, owned by
  `tools/publish-test.sh` (ADR 0019); this matrix tests the correction *algebra*, not the protocol.
- **§11.5** catalog arrival /
  title-to-multiple-content-ids (dictionary layer, `80_content.sql`); case/spelling aliases and
  sentinels (the normalisation self-test in `15_normalise.sql` owns those).
- **§11.6** operations (MV install order, parts explosion, mutation backlog, FINAL cost, dictionary
  refresh lag, cross-generation reads) — not hand-derivable golden material; belongs to
  `verify-env`, `publish-test.sh` and the scale gates (`evidence/scale.txt`).
