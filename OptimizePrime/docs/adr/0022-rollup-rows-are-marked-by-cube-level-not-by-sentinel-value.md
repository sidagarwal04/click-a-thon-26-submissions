# ADR 0022 — Rollup rows are marked by `cube_level` in the key, not by a sentinel value

> **Summary:** `cc_hour_agg` marked its all-content rollup rows with `content_id = -1`, so a session
> whose *real* content_id is −1 merged into the rollup silently — rehearsal R9 measured hour 17
> served as one row 2/4080 where truth was 2/3060 (rollup) + 1/1020 (content): the curves added.
> Fixed structurally: `cube_level UInt8` (which dims are REAL) joins the ORDER BY; sentinels become
> display-only; `tools/unseen-run.sh` now asserts at load that no value collides with a sentinel.
> **The graded data is unaffected** — `sonyliv.ev_raw` has 0 rows at −1/'*' (re-checked read-only
> this session); this was latent, fired only by the manufactured day. Status: accepted, 2026-08-01.

**Status** Accepted · 2026-08-01 · fixes rehearsal finding R9 (`evidence/unseen/rehearsal.txt`);
amends the cube design in ADR 0003's hour tier; the publisher contract of
[ADR 0016](0016-publisher-owns-the-user-and-hour-tiers.md) is preserved and re-verified.
Proof: `evidence/unseen/adr-0022-sentinel-collision.txt` (+ `adr-0022-{before,audit-fires,after}.txt`).

## Context

The hour cube stores a separately-computed curve for each of the 8 subsets of
(platform, country, content_id). Coarser levels collapsed a dimension to a sentinel — `'*'` for the
strings, `-1` for content — and the file argued the collision away: *"the smallest real content_id
in the file is 20,971,538, so −1 is unambiguous."* That is a claim about **one delivered file**,
promoted into a schema invariant nobody checked. The unseen-day rehearsal manufactured the
counterexample (block I, RUNBOOK A10): one genuine `content_id = -1` session, 17:30–17:46.

The mechanism is exact. Each delta row fans out to all 8 cube levels before the running sum. A real
−1 row lands on the display tuple `('*','*',-1)` twice — as its g=0 grand-total copy and as its g=4
content-grain copy — and the `GROUP BY` on the display tuple summed the two curves:

|  | peak | integral |
|---|---|---|
| served, pre-fix, one merged row | 2 | **4080** |
| truth, all content (hour 17) | 2 | 3060 |
| truth, content −1 alone | 1 | 1020 |

4080 = 3060 + 1020, literally. Every `({platform,'*'},{country,'*'},-1)` pair collided the same
way. The minute-tier gate stayed green throughout — it does not read the hour cube — which is why
this survived until a rehearsal that carried the designed per-level answer.

**Severity, honestly:** latent, not live. `sonyliv.ev_raw` holds 0 events at `content_id = -1`,
0 at `-987654399`, 0 with platform or country `'*'` (re-verified read-only this session). Nothing
served today is or was wrong. The trap fires only if the unseen day carries such a row — the one
scenario with no time to debug, which is why it is fixed now.

## Decision

**1 · The marker moves out of the value domain and into the key.** `cc_hour_agg` gains
`cube_level UInt8` — bit 0 platform real, bit 1 country real, bit 2 content_id real; 7 = full
grain, 0 = grand total — and the key becomes
`ORDER BY (platform, country, content_id, cube_level, hour)`. A rollup row is now *structurally*
not a content row: the two can never merge in the INSERT's GROUP BY / window partitions, and
`ReplacingMergeTree` can never collapse one onto the other. Sentinels remain as display values
only. `cube_level` sits after the dims so every existing (dims, hour-range) read keeps the
identical sort-key prefix; on collision-free data the dim tuple ↔ cube_level bijection holds, so
un-migrated equality reads still match exactly one row per hour — behaviour unchanged.

**2 · The canonical INSERT stays canonical.** The fan-out mask `g` is carried through as
`cube_level`; the `PUBLISH_EXTRACT` markers and the literal `ARRAY JOIN` anchor line that
`tools/publish.sh` sed-templates are byte-identical. Verified live, not assumed: the publisher's
exact extraction + hour-scope templating was executed against the scratch DB — parsed, ran,
12 FINAL rows before and after (superseded, not doubled), identical values on re-run (idempotent).
One derivation, two callers, one key shape — the two-writer divergence ADR 0016 warns about cannot
open here.

**3 · The invariant that remains is asserted, not trusted.** The cube no longer needs the
"ids are never −1" guarantee — but the repo's *query API* still speaks it (see Consequences), so
`tools/unseen-run.sh` now audits `ev_raw` immediately after load: any row with `content_id = -1`
or platform/country `'*'` prints the exact list of still-ambiguous paths and **fails the run**
(exit 1) unless `UNSEEN_ACK_SENTINEL=1` is set. Demonstrated in
`evidence/unseen/adr-0022-audit-fires.txt`. `tools/unseen-verify.sh` probe 5 flipped from
"demonstrate the collision" to a PASS/FAIL assertion (rollup 2/3060 · content −1 1/1020, separate
rows) that feeds the script's exit code.

## Alternatives weighed

| Option | Verdict |
|---|---|
| **A · Structural marker in the key** (chosen) — `cube_level`, 3 bits because three dimensions collapse independently; a single `is_rollup` flag cannot say *which* dims are rolled up, and the string dims have the same value/marker flaw (`'*'` is a legal platform string) | **shipped** — removes the id-domain assumption from the cube entirely |
| B · Sentinel outside the id domain | No such value exists: `content_id` is Int64 end-to-end and upstream is uncontrolled. Widening the cube column (e.g. Int128 with a sub-Int64 sentinel) is arithmetically sound but changes the column type at every consumer and does nothing for the `'*'` string collisions. Rejected. |
| C · Documented, asserted reservation of negative ids | Weakest — relies on upstream behaviour we were never promised; the rehearsal exists precisely because such promises break. Rejected as the fix, but its *assertion half is kept* (decision 3): the reservation is still load-checked because the `-1`-means-all convention survives in files this change does not own. |

## What the fix costs

- **Storage/write:** one UInt8 key column (compresses to ~nothing at ~26K rows/12 days); the
  INSERT's GROUP BY and window partitions carry one more column — rehearsal phase 6 wall clock
  unchanged within run-to-run noise (17 s pre-fix, 15 s post-fix on the same 6,887-event day).
- **Migration:** an existing old-shape `cc_hour_agg` fails the new INSERT **loudly**
  (`cube_level` unknown) — never silently. Migration is DROP + re-apply, the exact ADR 0016
  precedent for `cc_user_minute`; scratch DBs rebuild from scratch and are unaffected. The graded
  `sonyliv` keeps its pre-0022 shape (and its correct data — no collision exists there) until the
  next operator-run rebuild.
- **A new knob on the unseen day:** if the real unseen data carries a colliding value, the run
  stops once and must be re-run with `UNSEEN_ACK_SENTINEL=1`. That is the point — the stop message
  is the operator's map of which query paths to distrust for that id.

## Consequences, and proposed changes to files this ADR does not own

The value-as-marker convention survives at the **query API** layer. On collision-free data every
one of these is exactly as correct as before (the bijection above); under a collision they read
*both* matching rows — `max(peak)`-style reads stay correct for the "all" intent, but
`sum(integral)` adds the two curves again. Proposed fixes, for their owners:

- **`sql/85_windows.sql`** — `v_cc_window_range`'s `whole` CTE queries `cc_hour_agg` by sentinel
  equality; `v_cc_tumbling_hour` exposes the cube with no level column. Proposal: derive the level
  from the existing params — `(p_platform != '*') + 2*(p_country != '*') + 4*(p_content_id != -1)`
  — pin `AND cube_level = <that>` in `whole`, and add `cube_level` to `v_cc_tumbling_hour`'s
  SELECT. Note the params themselves cannot *express* "content −1 as content"; that inherent limit
  should be documented in the file, and such a query routed via `cc_minute_delta` or a direct
  `cube_level = 4` read.
- **`tools/build-model.sh`** — the stage-4 status line pins `platform='*' AND country='*' AND
  content_id=-1`: add `AND cube_level=0`. Its TRUNCATE also cannot migrate the shape: adopt the
  ADR 0016 `cc_user_minute` pattern (detect old shape → DROP with a loud message → re-apply).
- **`tools/clickstack-cloud.sh`** — `CUBE_TOTAL = "platform = '*' AND country = '*' AND
  content_id = -1"`: append `AND cube_level = 0`.
- **`evidence/benchmark/`** — queries pin levels through the `v_cc_window_range` params (inherit
  that fix); `b13_hour_top_content.sql` excludes the rollup with `content_id != -1` and should use
  `cube_level = 4` instead — which also makes a real −1 content *appear* in the top-N, correctly.

No other `sql/` file reads `cc_hour_agg` in code (12/45/80 reference it in comments only;
`60_projection.sql` does not touch it). `sql/90_reconcile.sql` is minute-tier and unaffected — it
passed 1,080/0 before and after, which is exactly why it could never have caught this.

## Proof

`evidence/unseen/adr-0022-sentinel-collision.txt`: §1 pre-fix reproduction (merged 2/4080 rows),
§3 post-fix separation at all 8 levels + gate 1,080/0 + designed-truth 1,081/0, §4 the load audit
firing and stopping the run, §5 the publisher-templated re-derivation superseding idempotently,
§6 the graded-database zero-counts. The manufactured day regenerates byte-identically from
`tools/unseen-gen.sh` (seed 20260815), so the whole sequence is reproducible from a clean tree.
