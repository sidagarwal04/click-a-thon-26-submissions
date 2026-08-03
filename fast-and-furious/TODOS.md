# TODOS

Deferred work, captured with enough context to pick up cold.

---

## Confirm the receipt statement does not full-scan on incremental runs

**What:** `solution/sql/10_reference_intervals.sql:360-372` — the `oracle_run_manifests`
INSERT recomputes `deduplicated_events` over all of `raw_events` with no `full_scan`
predicate and no session scoping. The result is discarded on scoped runs by
`WHERE {full_scan:UInt8} = 1` at line 442.

**Why:** if ClickHouse does not fold that constant before planning, every incremental
correction run pays a full table scan. Incremental update handling is a scored axis and
the whole claim is "corrections only read the sessions that changed." Judges read
`system.query_log`, which would show the scan and disprove the claim.

**Pros of doing it:** five minutes with `EXPLAIN` either removes the concern permanently
or finds a real defect on a scored dimension.
**Cons:** the statement is currently deferred out of stage 01, so it fixes nothing today.

**Context:** found by the outside-voice pass during the stage 01 engineering review
(1 Aug 2026). Stage 01 deploys without this statement — three parameters, no manifest,
no oracle IDs — so the issue only returns when the control plane is deployed. If the
constant does not fold, the fix is to add the same scope predicate the interval builder
uses at lines 79-89.

**Verify:** `EXPLAIN` the second statement with `full_scan=0` and check whether a scan
over `events_raw` / `raw_events` appears in the plan.

**Depends on / blocked by:** control-plane deployment. No blocker to checking it early.

---

## Collapse the unseen-day runbook into one tested script

**What:** `solution/README.md`'s unseen-day runbook is eight steps, including a fenced
compactor lease, a bootstrap ingestion-quiesce window, and an "if step 25 fails after
writing staging rows, abandon that snapshot ID" branch. It has never been executed.

**Why:** it will be run once, under time pressure, by one person who is also recording a
demo video, on the highest-weighted scoring axis — where hand-computed answers score
nothing. An eight-step procedure with conditional failure branches is not executable in
that state.

**Pros of doing it:** the rehearsal doubles as the pipeline-evidence bundle and as demo
footage. Removes the single largest execution risk left in the window.
**Cons:** thirty minutes that only pays off if stages 02-04 are finished in time.

**Context:** raised by the outside-voice pass during the stage 01 engineering review
(1 Aug 2026). The collapsed sequence is: load -> intervals -> deltas -> minutes -> run
benchmark -> dump answers plus `system.query_log`. Prove it by wiping and re-running it
end to end on the tuning day.

**Depends on / blocked by:** stages 02, 03 and 04 existing on Cloud.

---

## Stage 02 note (not a TODO — an input to the next stage)

`policy.yaml` materializes rollup masks `0,1,2,4,8,3,5,9,12,15`. Masks 6, 7, 10, 11, 13
and 14 are unmaterialized. A missing mask's *deltas* can be re-derived from mask 15 by
summing; its *peak* cannot, because two dimension values can peak at different minutes
and peaks do not sum. Decide the mask set before writing the deltas DDL — the mask is
part of the sort key and cannot change after rows exist. The benchmark query set was
never published, so the combinations that will be asked are unknown.
