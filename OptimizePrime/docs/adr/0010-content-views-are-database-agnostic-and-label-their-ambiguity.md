# ADR 0010 — Content views name no database, keep the title grain, and label the blank `video_type`

> **Summary:** `sql/80_content.sql` hard-coded `dictGet('sonyliv.dict_content', …)` in six places, so
> every content view built in the unseen-day database `sonyliv_unseen` would have answered from
> **production's** catalog — reproduced, and now fixed by writing every name **unqualified**, the
> pattern the rest of `sql/` already uses. Measured: ClickHouse **bakes** the resolved dictionary name
> into a view at `CREATE VIEW` time, so an unqualified view is permanently pinned to its own database.
> `v_concurrency_minute_title` is **kept** (option (a)) with a new `catalog_content_ids` column —
> **568 of 3,325** served titles (17.1%) name more than one asset, including the **#1 title at peak
> 433**. The blank `video_type` — **1,089** catalog rows, **25,810 events (2.85%)**, peak **97** — is
> emitted as `'(blank)'`, kept distinct from `'(unknown)'`. Zero concurrency numbers moved. Status:
> accepted, 2026-08-01.

**Status** Accepted · 2026-08-01 · gate re-run green (`make reconcile`, TARGET=cloud, **17,028 minutes
compared, zero mismatches**, peak 2,887 @ 2026-07-26 10:56 — identical before and after)

## Context

`sql/80_content.sql` is additive: one dictionary and nine views over `cc_minute_delta`. It never
touches the graded model. Three faults in it were all about *which* data a view reads and *what the
answer is called* — none about the concurrency arithmetic, and none of them error.

---

## 1 · The cross-database leak

### The bug

Six `dictGet` calls and the dictionary's `SOURCE` named `sonyliv` literally:

```sql
SOURCE(CLICKHOUSE(TABLE 'content_dim' DB 'sonyliv'))
dictGet('sonyliv.dict_content', 'title', tuple(content_id))
```

The graded database *is* `sonyliv`, so production was always right and nothing ever complained. But
`tools/unseen-run.sh` builds the entire model in `sonyliv_unseen`, and
`sonyliv_unseen.v_concurrency_minute_title` would have resolved titles out of **production's**
catalog — plausible names, wrong day, no error. `unseen-run.sh` carries an `assert_isolated` guard
that `sed`s the string out *precisely because of this file*; the guard is a workaround for a defect,
not a fix.

**Reproduced**, ClickHouse Cloud 26.2.1.525, in a scratch database whose catalog is deliberately
unmistakable:

| view built in `sonyliv_scratch80` | reads title for `content_id 2078158293` |
|---|---|
| old, `dictGet('sonyliv.dict_content', …)` | `rolel lej` ← **production's catalog** |
| new, `dictGet('dict_content', …)` | `SCRATCH-ONLY-A` ← its own |

The old form also folded `content_id` 999 and −42 into one `(unknown)` bucket of 6, because neither
exists in production's catalog. Every content-level answer on the unseen day would have been wrong in
this shape.

### The decision

**Name no database anywhere in the file** — the pattern every other file in `sql/` already uses. The
database comes from `clickhouse-client --database "$DB"` (`tools/apply-sql.sh`,
`tools/unseen-run.sh`), never from the text.

The non-obvious part is that this is safe *inside a view*. A dictionary name is a string literal, so
it looks like it must survive verbatim. It does not — **measured**, two scratch databases:

```
probe_a.content_dim -> 'FROM_A'          probe_b.content_dim -> 'FROM_B'

CREATE VIEW v_probe AS SELECT dictGet('dict_content','title',tuple(toInt64(1)))

  stored in probe_a as:
  CREATE VIEW probe_a.v_probe AS SELECT dictGet('probe_a.dict_content', 'title', tuple(toInt64(1)))

  SELECT * FROM probe_a.v_probe   -- session attached to probe_b  -> FROM_A
  SELECT * FROM probe_b.v_probe   -- session attached to probe_a  -> FROM_B
```

ClickHouse resolves the name against the session database at `CREATE VIEW` time and **bakes** it in.
Each view is therefore pinned to its own database's dictionary forever, whatever database the *caller*
is attached to — which is the property we want and the hard-coded name destroyed. The dictionary's
`SOURCE` resolves the same way: `TABLE 'content_dim'` with no `DB` clause loaded `probe_a`'s table in
`probe_a` and `probe_b`'s in `probe_b` (`default` holds no `content_dim` at all, so it cannot have
fallen through).

Verified end to end by applying the committed file, unmodified, with `--database sonyliv_scratch80`:

```
system.tables      : 14/14 objects, 0 occurrences of "sonyliv."
baked dictGet name : dictGet('sonyliv_scratch80.dict_content'  (all four views)
system.dictionaries: source = ClickHouse: sonyliv_scratch80.content_dim, LOADED
read from a session attached to `sonyliv`: still returns SCRATCH-ONLY-A
```

Re-applied to `sonyliv`, the same file bakes `sonyliv.dict_content` and every number is unchanged.

`sql/70_truncation_test.sql` stays fully qualified to `sonyliv_trunc` on purpose: it is a test that
exists to run against exactly one database, and its unqualified `TRUNCATE` in the wrong session
context would destroy graded state. Qualification belongs in that file and nowhere else.

### One more change this forced

`CREATE DICTIONARY IF NOT EXISTS` → **`CREATE OR REPLACE DICTIONARY`**. `IF NOT EXISTS` is a no-op
against a dictionary that already exists, so a server still holding the old `DB 'sonyliv'` definition
would keep it forever while the committed file claimed otherwise — the same silent divergence between
text and running state that the hard-coded database *was*. Re-applying the file must make the server
match it. Cost: one reload of 33,464 rows (10.48 MB).

---

## 2 · `title` is not a key — keep the grain, label the ambiguity

### The finding

`content_id` is a true primary key (33,464/33,464 unique). `title` is not:

```
 33,464 content_ids  ->  30,508 distinct titles
  2,773 titles name MORE THAN ONE content_id   (2,596 x2 · 171 x3 · 6 x4)
  1,418 of those span DIFFERENT CATEGORIES · 198 span DIFFERENT video_types
```

The file's existing header analyses a *different* trap correctly — can one session be open under two
`content_id`s at once? (no: `sql/30_build_intervals.sql` collapses to `any(content_id)` upstream, so
summing deltas across `content_id` cannot double-count a viewer). That reasoning is sound and **does
not cover this**. Title collision is not a double count; it is a **merge of distinct assets under one
label**. The arithmetic is right; the name on the number is ambiguous.

Measured against the serving layer, not just the catalog:

| | |
|---|---:|
| titles served by `v_concurrency_minute_title` | 3,325 |
| …naming **more than one** catalog asset (ambiguous label) | **568 (17.1%)** |
| …that actually **add up two live assets** today (arithmetic merge) | 32 |
| …of the **top 50** titles by peak, ambiguous | **7** |
| …with no catalog row at all | 0 |

It is not a long-tail problem. The **#1 title in the dataset** is one of them:

```
'wekek ked'  peak 433  — the catalog gives that name to two content_ids:
    2078157818   video_type live   category cdbgg   3,302 starts
      21350117   video_type vod    category cddgn       0 starts
```

Today only the live asset draws traffic, so 433 happens to be one asset — but the answer is silently a
claim about whichever of the two the grader meant, across both a `video_type` and a `category`
boundary. `'rolel lej'` shows the arithmetic form: its 12 is 11 + 1 across categories `bjdbj` and
`bjbbb`.

### The decision — option (a), keep the view, and carry the merge in the data

Rejected **(b) drop the title grain in favour of `v_concurrency_minute_content`**, for two reasons:

1. *"Understand demand by title **or** content identifier"* is the deliverable's own wording. Both
   grains are asked for; deleting one deletes half the answer.
2. `v_concurrency_minute_content` is **not** a drop-in replacement. Its grain is
   `(minute, platform, country, content_id)`, so a per-asset answer still needs a roll-up across
   platform and country. The two views answer different questions; the redundancy is only apparent.

Chose **(a)**, but not documentation alone — a comment in a `.sql` file cannot be read at query time.
The view gains **`catalog_content_ids`**: how many `content_id`s in `content_dim` carry this title.

- `1` → the label names exactly one asset; the row is per-asset.
- `>1` → the label names that many. The number may still be one asset's traffic today (`wekek ked`)
  or genuinely several added together (`rolel lej`). Either way, do not quote it as "the asset".
- `0` → the title came from a dictionary **miss**; no catalog row. Cross-check `v_content_orphan_check`.

Deliberately **catalog-wide**, not per-minute. A per-minute fan-in reads `1` whenever only one merged
asset emitted a delta that minute — most minutes, and exactly the `wekek ked` case where the label is
most misleading. It would hide the thing it exists to expose.

Two supporting pieces: `v_content_title_collisions` (every colliding title, its ids, and whether they
span categories/video types) so a flagged title can be split; and `catalog_content_ids` carried
through `v_concurrency_title_now`, because a "now" tile for a merged title must not look like a "now"
tile for one asset.

`category` gets **no** fan-in column: it is a genuine many-to-one *label*, so merging several
`content_id`s under one category is the point of that view, not a defect. `title` is different
because it *looks* like an identifier.

---

## 3 · The nameless third `video_type`

### The finding

```
 vod   32,182 catalog rows (96.17%)  ->  778,455 events (85.96%)
 ''     1,089 catalog rows ( 3.25%)  ->   25,810 events ( 2.85%), 142 content_ids
 live     193 catalog rows ( 0.58%)  ->  101,293 events (11.19%)
```

The empty string is **real source data**, not a join failure: `dictGet`'s `'(unknown)'` default fires
only on a key **miss**, and there are 0 orphan `content_id`s on this file. The file already reasoned
that correctly. What was missing was the decision about how it is **labelled** — so `GROUP BY
video_type` produced a blank third bar and `WHERE video_type IN ('vod','live')` would silently drop
2.85% of events. That bucket peaks at **97 concurrent**; it is not noise.

### The decision — emit `'(blank)'`

- **Not left as `''`** — an empty label is invisible in a `GROUP BY` result, a HyperDX legend and a
  benchmark answer. A reader sees a nameless bar and cannot tell it from a rendering artefact.
- **Not folded into `'(unknown)'`** — that string is reserved, exclusively, for a dictionary key miss.
  Merging them would let a real orphan hide inside a bucket worth 2.85% of events, which is precisely
  the silent join failure the `DEFAULT` clause exists to prevent. Two different faults must not share
  a name. (Checked: 0 catalog rows carry `'(unknown)'` or `'(blank)'` as a literal value, so neither
  sentinel can collide with real data.)
- **Not filtered out** — dropping 25,810 events from a content rollup is the opposite of this file's
  job.

Applied to `title` and `category` too, not only `video_type`. Measured on this file: 0 blank titles,
0 blank categories — so nothing changes today, and a blank on the unseen day is named instead of
rendering as a nameless bar.

**This is a defensible default, not a settled answer.** `doubts/03-content-catalog.md` asks the
mentors whether the blank should be a third reported category, is meaningful, or should be excluded,
and that question is **open**. Both alternatives are one-line changes *because* the blank is labelled
rather than filtered: change the literal (one string, four views), or add
`WHERE video_type != '(blank)'` to the video-type view only — never to the totals.

---

## Consequences

**Nothing moved.** The file is additive and this change is additive to it. Before and after, on Cloud:

| | before | after |
|---|---|---|
| `make reconcile` (TARGET=cloud) | PASS · 17,028 minutes · 0 mismatches | **PASS · 17,028 minutes · 0 mismatches** |
| headline peak | 2,887 @ 2026-07-26 10:56 | 2,887 @ 2026-07-26 10:56 |
| peak by `video_type` | `vod` 2404 · `live` 468 · `''` 97 | `vod` 2404 · `live` 468 · **`(blank)`** 97 |
| top-3 peak by title | wekek ked 433 · dijoj jeh 102 · verar feg 77 | identical, **+ `catalog_content_ids` 2 · 1 · 1** |
| `v_content_orphan_check` | 0 / 0 | 0 / 0 |

Every concurrency number is byte-identical. What changed is one label, one new column, one new
helper view — and which database the views read from.

- `tools/unseen-run.sh`'s `assert_isolated` guard now has nothing to rewrite in this file. **Keep it**:
  it is a cheap standing check against the defect coming back, and it still covers every other file.
- `tools/clickstack-cloud.sh` names its source columns explicitly, so the added column does not
  disturb the HyperDX sources. `catalog_content_ids` is available to add when the title chart is next
  touched.
- If the mentors answer `doubts/03`, the follow-ups are the one-liners named above. Until then the
  ambiguity is *stated in the data*, which is the difference between a defensible default and a guess.
