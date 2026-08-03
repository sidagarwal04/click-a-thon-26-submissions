# tests/edge — the executable edge-case matrix

> **Summary:** Codex 003 §11's edge-case register turned into 32 hand-auditable golden fixtures
> (§13.1), run through the REAL derivation (`sql/30_build_intervals.sql` + `sql/40_deltas.sql` + `sql/45_user_concurrency.sql`,
> sed-templated, never reimplemented) in scratch db `edge_matrix` by `tools/edge-test.sh`. Every
> expected interval and minute was derived **by hand from the spec, never from the model** — and
> every fixture family is **sabotage-checked**: 10 named mutations of the production SQL each turn
> their paired fixture red (ledger below). Catalogue + the §11 rows deliberately NOT implemented:
> `docs/TESTS.md` §H. Local-only; the graded `sonyliv` database is never named.

## Run it

```bash
tools/edge-test.sh            # the matrix — PASS/FAIL per fixture, exit 1 on any red
tools/edge-test.sh sabotage   # prove the fixtures can fail (see ledger), then a clean rebuild
```

Requires the local stack (`make stack-up`) and a UTC server (preflight enforces it). Everything
runs in `edge_matrix`, dropped and recreated per run. `TARGET=cloud` is refused outright.

## The rules that make a fixture admissible here

1. **One hazard per fixture.** A handful of events, on the fixture's own UTC date so minute
   windows never overlap.
2. **Expected values are derived by hand, from the spec** — the ADR'd semantics (ADR 0003/0007/
   0008/0009, the `interval-math` skill), walked through step by step in the fixture header.
   Codex 003 §13.1: *these fixtures must not reuse the production derivation as their
   expected-value generator.* If the expected answer comes from the code under test, the test
   only proves the code agrees with itself.
3. **The code under test is the production SQL**, templated with `sed` exactly as
   `evidence/adversarial/README.md` does (INSERT target + FROM source only), with an isolation
   grep before execution. The harness never reimplements the derivation it is testing.
4. **Where the spec itself is an open fork** (doubts/05 minute membership, doubts/07 tail at
   explicit stops, doubts/08 ms truncation, doubts/10–11 fail-open liveness), the fixture pins
   the SHIPPED reading and names the dossier in a `FORK` note — so a silent semantic change is
   caught, and a mentor ruling tells you exactly which expectations to rewrite.
5. **A fixture that cannot go red is decoration.** Every family carries at least one mutation in
   the sabotage ledger proving its fixtures detect the break they claim to cover.

## What the L family does and does not prove

`is_late=1` fixtures build the world twice (batch 1, then all batches) through the real
derivation, emit the ADR 0006 correction (negate every old row, append every new row), and assert
`old + (−old + new)` lands on the hand-derived truth — **including minutes and dimension tuples
that exist only on the old side and must net to zero**. The correction *constructor* here is the
harness's (mirroring ADR 0006); the production publisher's claim protocol, fencing, crash points
and prune phase are `tools/publish-test.sh` territory, deliberately not retested here.

## Sabotage ledger — measured 2026-08-02, all via the sed stream (disk never modified)

The final clean rebuild in the same run is the reversion proof: all 32 fixtures green again.

| Mutation | What it breaks in the production SQL | Caught by | Result |
|---|---|---|---|
| `resume-strict` | ADR 0009's `>=` resume lookup back to `>` (the historical bug) | O01 | red ✓ |
| `no-tail-credit` | drops the +60 s tail on run-end segments | B01 | red ✓ |
| `gap-inclusive` | run split at `>= GAP_S` instead of strict `>` | B05 (exact-150 gap) | red ✓ |
| `pause-permissive` | flips `UNCLOSED_PAUSE_TO_RUN_END` to the permissive reading | B02 | red ✓ |
| `tie-break-second` | dominant-dimension vote takes the 2nd sorted value | D01 | red ✓ |
| `no-minute-merge` | disables the same-minute interval merge entirely (the /reconcile-caught double count) | S08 | red ✓ |
| `merge-off-by-one` | merge predicate `x.1 > acc.2` — breaks only the touching-minute merge | D02 | red ✓ |
| `close-leaks-next-hour` | removes the ADR 0003 close-suppression at the hour's last minute | B06 | red ✓ |
| `corr-drops-vanished` | correction negates only old rows whose (minute, dims) key still exists in the new build | L02 | red ✓ |
| `user-fold-by-session` | folds multiple user identities under one session id, erasing the later user | U03 | red ✓ |

Instructive miss, kept on record: `merge-off-by-one` was first paired with S08 and **survived** —
S08's two intervals start in the *same* minute, so `x.1 > acc.2` still merges them. The mutation
actually breaks the *touching-minute* merge, which is D02's shape. The pairing was fixed, and the
always-split mutation added so S08 covers the double-count it exists for. A sabotage that stays
green is telling you which hazard the fixture actually covers — listen to it.

## Dynamic-field and user-tier fixtures

| Fixture | Hand-derived contract |
|---|---|
| D03 | An unseen `experiment_id` key and the released `video_resolution` alias survive interval attribution; the modal value wins deterministically. |
| D04 | Dynamic keys vote independently rather than as one composite `Map`; input key order cannot change the canonical result. |
| D05 | A missing key and an explicitly empty value are distinct; the presence-first tie rule retains `cohort=''`. |
| U01 | Two simultaneous sessions for one user in one dimension serve sessions=2 and exact users=1. |
| U02 | One user on web and TV serves total users=1 while each platform serves users=1; per-dimension distinct counts are not additive. |
| U03 | Two user identities on one session across a pause remain two users in the overlap minute; folding only by session would erase one. |

## Files

- `fixtures/b_boundaries.sql` — B01–B08, §11.3 (minute/hour/day boundaries, zero-length, exact-gap)
- `fixtures/s_state.sql` — S01–S08 (no S05), §11.2 (pause/background combinations, tails, dips)
- `fixtures/o_ordering.sql` — O01–O05, §11.1 (same-second ties, arrival order, ends, duplicates)
- `fixtures/l_late.sql` — L01–L04, §11.4 (extend, shrink, bridge/vanish, dimension flip)
- `fixtures/d_dimensions.sql` — D01–D05, deterministic fixed and dynamic dimension attribution
- `fixtures/u_users.sql` — U01–U03, exact user distinctness (same user/multiple sessions and dimensions; multiple users/one session)
