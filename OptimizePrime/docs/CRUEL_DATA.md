# CRUEL_DATA — the adversarial-day generator and what it broke

> **Summary:** `tools/cruel-gen.sh` manufactures a FAMILY of hostile day-files — one hazard per knob
> (malformed strings, embedded newlines, unicode, aliases, numeric extremes, unparseable types, time
> hazards, epoch bombs, structural abuse, unknown vocabulary, skew, and two file-shape mutations) —
> each shipping an analytically known answer from a THIRD implementation of the counting spec
> (Python sets vs the model's arraySplit vs the gate's window functions). Hazards with NO defensible
> answer are marked `SPEC_ONLY` and carried as organiser questions, never invented. Evidence of what
> actually broke: `evidence/cruel/` (`<knob>.run.txt`, `<knob>.verify.txt`, `<knob>.manifest.txt`).

The judges said the unseen day will be *"more real and cruel"*. `tools/unseen-gen.sh` manufactures a
**well-formed** tricky day; this generator manufactures **malformed** ones. It grounds every hazard
in the edge-case register at [codex-validation/003.md §11](codex-validation/003.md) and in measured
behaviour (`doubts/11` fail-open vocabulary, ADR 0009 same-second ties, ADR 0022 sentinel collision).

## Verified: the source-contract gate catches the worst hazard here

Checked after both landed, because they were built in separate lanes and nobody had confirmed they
connect. **They do.**

The most dangerous finding in this catalogue is the **seconds-vs-milliseconds** session: `load.sh`
divides `event_timestamp` by 1000, so a seconds-valued input lands in **1970**, the model happily
derives intervals there, and **the gate stays green** — truth and serving agree, both in the wrong
year. We would submit a confidently wrong answer with a passing correctness gate.

`queries/validate_source_contract.sql` probe 3 catches it: `toYear(event_timestamp) NOT BETWEEN 2020
AND 2035`, reported as *"epoch-zero or millis-not-divided"*. It is a **FAIL**, not a warning.

And the ordering is right, which is the part that could easily have been wrong. The gate queries
`ev_raw`, so it can only run after a load — but `docs/RUNBOOK_UNSEEN.md` loads the unseen file into a
**throwaway contract database** first, validates there, drops it, and only then does the real run.
So the check happens before we trust the file, not after we have built the answer on it.

**The residual risk is procedural, not technical:** this only protects us if the runbook is followed
in order under time pressure. That is precisely the scenario the unseen day creates.

## How to use it

```bash
tools/cruel-gen.sh list             # the knob table
tools/cruel-gen.sh gen all          # data/cruel-<knob>-raw.csv + truth + manifest per knob
tools/cruel-gen.sh run <knob>       # full pipeline in SCRATCH (CRUEL_DB, default cruel_scratch,
                                    #   NEVER sonyliv) via tools/unseen-run.sh, then verify
tools/cruel-gen.sh verify <knob>    # served minutes vs designed truth + probes
```

Dial **one hazard at a time**: each knob is a self-contained file whose sessions live in their own
hour of 2026-08-22 UTC, so a reviewer sees exactly what one hazard costs. `worst` is every loadable
hazard in one file.

## The rule that makes this useful

Every file ships its analytically known answer (`evidence/cruel/<knob>.truth.tsv`), computed by a
third, independent implementation of the counting spec — the same discipline as `unseen-gen.sh`, so
a shared blind spot between model and gate shows up as a designed-truth mismatch. Two statuses:

- **`TRUTH`** — a defensible designed answer. A mismatch here is a bug, full stop.
- **`SPEC_ONLY`** — the spec's *projection* onto a hazard that has **no defensible answer** (an end
  before its start; one session id live on two devices at once; time granted only by unknown event
  types). Recorded so the pipeline can be checked for self-consistency; the manifest carries the
  exact question for the organisers. A "truth" nobody can defend tests nothing.

`badtypes` ships **no truth at all**: its designed outcome is a loud load failure.

## The knobs, and where each answer comes from

| Knob | Hazard isolated (codex 003 §11 refs) | Answer provenance |
|---|---|---|
| `malformed` | empty/whitespace/`NULL`/`null`/`NaN` strings, `\N` CSV null, 500-char value, embedded commas and quotes, empty `user_id`, empty `event_type`/`event` (§11.5) | designed; the two-devices-one-empty-sid merge is `SPEC_ONLY` |
| `newline` | ONE quoted embedded newline in a field — valid CSV, but one extra physical line (§11.5) | designed; the harness's `wc -l` row assert is the target |
| `unicode` | RTL mark, ZWJ emoji, NFC-vs-NFD é, zero-width space in dimensions | designed |
| `aliases` | five spellings of Hindi, three of ANDROID_PHONE, two of india (§11.5 case/spelling aliases) | designed for totals; filter grain is an organiser question (doubts/04) |
| `numeric` | `content_id` −1 (ADR 0022 sentinel), −987654399, 0, ±Int64 extremes, all absent from `content_dim` | designed; sentinel refusal (`UNSEEN_ACK_SENTINEL`) is itself the designed behaviour |
| `badtypes` | `NaN`/`12.5` in Int64, `not-a-time` in UInt64 (§11.1 invalid epoch) | **none — the truth is the ERROR**; a silent load is the bug |
| `time` | end-before-start, events before `session_start_epoch`, clock rollback, same-second AND same-millisecond pause/resume in reverse file order (ADR 0009, §11.1), tail landing EXACTLY on a minute boundary, midnight/file-boundary crossing (§11.3) | designed; end-before-start is `SPEC_ONLY` |
| `timebomb` | epoch-0 event, whole session in epoch SECONDS not ms, EMPTY timestamp field, future-dated session (+1 y), pause+resume both at epoch second 0 (§11.1 future/invalid/rollback) | designed, including an **expected model divergence** (z4, below) |
| `structural` | byte-duplicate rows, 3× starts / 2× ends, events after end, orphan resume/pause/background, sid reused after silence AND simultaneously on two devices, one user × 8 sessions (§11.1, §11.2) | designed; simultaneous sid reuse is `SPEC_ONLY` |
| `vocab` | unknown event types keep sessions alive: `SystemSleep` (sole liveness for 20 min), `WidgetPing` (bridges a 600 s gap), `PAUSE` uppercase (NOT a pause), `VideoPause`+`pause` (IS a pause, by accident) — doubts/11 | **dual truth**: fail-open (`vocab.truth.tsv`) vs allow-list (`vocab.truth-closed.tsv`); the delta IS the measured exposure |
| `skew` | one 18,003-event session (plus a real pause inside it), 1,200 sessions starting in ONE minute, 400 unique app/player versions (§10.3) | designed (peak 1,200) |
| `newcol` | an extra CSV column (`experiment_id`) | designed; the hazard is the loader's silence |
| `misscol` | the `country` column missing entirely | designed; loader fills `''` silently — country filters die invisibly |
| `worst` | every loadable hazard in one file (excludes `newline`/`newcol`/`misscol`/`badtypes`, whose knobs each kill the harness before the model runs) | union of the above |

## What broke — the findings (2026-08-02, scratch `cruel_scratch`, commit at run in each `*.run.txt`)

Every knob ran end-to-end through **unmodified** `tools/unseen-run.sh` + `tools/load.sh` in scratch.
Breakage was the deliverable, and there is breakage:

### 1 · A seconds-vs-milliseconds session SILENTLY RELOCATES THE SUBMITTED ANSWER (timebomb, real bug)

One session whose timestamps are epoch seconds instead of milliseconds (`z1`) lands on
**1970-01-21** after the loader's `/1000`, and phase 7 of the run — *"the answer (this is what we
would submit)"* — printed **`peak 1 @ 1970-01-21 16:30:00`** as the day's answer. No error, no
warning, and **the gate went GREEN over it** (30,315,496 minutes compared, 0 mismatched): the gate
recomputes truth from the same poisoned `ev_raw`, so it proves self-consistency, not sanity. One
mis-united producer on the unseen day poisons the headline number invisibly. Defence: assert the
data's time span is inside the expected day at load (the same place the sentinel audit lives).

### 2 · The `arrayFirst` 0-sentinel eats a run when a resume exists at epoch 0 (timebomb z4, real model bug)

`sql/30_build_intervals.sql` resolves a pause's close with `arrayFirst(x -> x >= p, resumes)` and
treats `0` as "no resume". A resume that legitimately lands at epoch second 0 is indistinguishable
from "none": the conservative unclosed-pause rule then eats the entire run.
**Confirmed live:** designed truth 1 active across 1970-01-01 00:00–00:06, served 0 — and the gate
stayed green while the third implementation caught it (`timebomb.verify.txt`, the only TRUTH
mismatches in the whole family). Absurd input today, but the idiom is the bug: any future refactor
that maps "not found" to a valid domain value inherits it.

### 3 · One quoted embedded newline makes the harness kill a CORRECT load (newline, harness bug)

The file is valid CSV — ClickHouse parsed all 98 records — but `unseen-run.sh` asserts
`loaded rows == wc -l − 1`, counted 99, and **aborted a correct run** with "a partial or doubled
load is worse than no load". On the real unseen day, a single quoted newline anywhere in the file
aborts the rehearsal path at phase 2 with a false diagnosis. Count records with the parser, not
with line counts.

### 4 · Unknown event vocabulary can be 100% of the served peak (vocab, confirms doubts/11 at full scale)

The pipeline reproduced the fail-open projection exactly: for 21 minutes the entire served
concurrency (4 of peak 4) exists **only** because `SystemSleep`/`WidgetPing` — event types that do
not exist — renewed liveness. Also planted and confirmed: uppercase `PAUSE` is silently *not* a
pause, while unknown-type `VideoPause`+`pause` silently *is* one (the model matches `event` alone).
The verify's vocabulary probe caught all 4 unknown pairs (plus the empty-string pair in
`malformed`) against `evidence/liveness/vocabulary.tsv` — that ~15-line check belongs in the loader,
as doubts/11 proposed; nothing in the pipeline runs it today.

### 5 · File-shape mutations: the harness refuses, the bare loader swallows (newcol/misscol, measured)

`unseen-run.sh`'s header assert refused both reshaped files (designed). The bare
`tools/load.sh` path swallowed them: the extra `experiment_id` column is dropped without a word,
and a file with **no `country` column at all** loads with `country = ''` on every row — every
country-filtered answer dies invisibly while totals stay plausible. Anyone loading outside
`unseen-run.sh` has no shape protection.

### 6 · What did NOT break (the model earned these)

- **Hostile strings survived end-to-end**: empty/whitespace/`NULL`/`null`/`NaN` values, `\N`
  (→ `''` via CSV-NULL defaulting — silent but harmless here), a 500-char platform, embedded
  commas/quotes, RTL marks, ZWJ emoji, zero-width spaces, NFC-vs-NFD pairs — all loaded, stayed
  distinct raw buckets, and every TRUTH minute matched. The dashboards will render
  indistinguishable-looking duplicate rows (`ANDROID_PHONE` three invisible ways), but the counts
  are right.
- **`badtypes` failed loud and named the row**: `CANNOT_PARSE_INPUT_ASSERTION_FAILED`, row 35,
  column 0 — no silent partial state observed.
- **Sentinel discipline held** (numeric): the run *refused* until `UNSEEN_ACK_SENTINEL=1`, and
  `cube_level` kept the real `content_id=-1` session (peak 1) separate from the all-content rollup
  (peak 5) — ADR 0022 doing its job.
- **Skew held**: 18,003-event session, 1,200 sessions starting in one minute, 400-value
  cardinality bomb — peak exactly 1,200, 58 s wall clock, designed truth matched.
- **Structure held**: byte-duplicates inert; multi-start/end, after-end events, orphan
  pause/resume/background all matched the spec projection; 8-sessions-one-user showed session
  peak 10 vs user peak 5.
- **The 30.3M-minute gate spine survived** (114 s, no OOM) — slow, not broken; but see finding 1
  for what its green means.
- **`worst` (everything at once)**: the ONLY truth mismatches were finding 2's seven minutes;
  every other hazard co-existed and every other minute matched.

### Scorecard

| Knob | Run | Designed-truth verify |
|---|---|---|
| malformed | gate PASS | PASS (60 min) |
| newline | **died at phase 2 on a correct load** (designed) | n/a — finding 3 |
| unicode | gate PASS | PASS (60 min) |
| aliases | gate PASS | PASS (60 min) |
| numeric | refused → ack → gate PASS | PASS (60 min) |
| badtypes | **load rejected loudly** (designed) | n/a — no truth by design |
| time | gate PASS (1,331 min) | PASS (240 min) |
| timebomb | gate PASS over 30.3M minutes; **answer relocated to 1970** | **FAIL — 7 min, the z4 bug** |
| structural | gate PASS | PASS (120 min) |
| vocab | gate PASS | PASS; exposure = 100% of peak for 21 min |
| skew | gate PASS | PASS (180 min) |
| newcol | harness refused; **bare loader silently dropped the column** | truth defined; loader silence is the finding |
| misscol | harness refused; **bare loader filled `country=''`** | truth defined; loader silence is the finding |
| worst | gate PASS, peak 1,200 correct | FAIL only on finding 2's 7 minutes (1,027 min compared) |

## Questions for the organisers (raised by these files)

Collected from the manifests — each is a hazard with no defensible answer:

1. **Empty/garbage session id shared by two devices** — one viewer or two? The spec merges all
   rows with the same (empty) id into one session.
2. **A session id reused simultaneously on two devices** (interleaved events, two platforms) — one
   concurrent viewer or two?
3. **`VideoSessionEnd` timestamped before `VideoSessionStart`** — invalid session, ignored end, or
   reordered pair? Our spec treats both as bare timestamps.
4. **An interval ending exactly on a minute boundary** — does that minute count? Inclusive vs
   half-open moves 5 designed viewers at 15:40 in the `time` file (Codex 003 §12.3 Q11).
5. **Unknown event types on the unseen day** — extend activity by default (fail open) or excluded
   until reviewed (fail closed)? The `vocab` file makes the two readings differ by 4 sessions × 20
   minutes; on the provided file the strict reading was worth −1.3% of peak (doubts/11).
6. **Raw vs normalised dimension matching** — is private truth matched on `hin` or on
   case-normalised Hindi? Every filtered answer moves (doubts/04).

## Regenerating

Deterministic: seed 20260822, no wall clock. `data/` is gitignored (regenerate with `gen`);
`evidence/cruel/` is committed. The counting spec mirrored by the truth implementation is documented
in the header of `tools/cruel-gen.sh` and was verified line-by-line against
`sql/30_build_intervals.sql` on 2026-08-02.
