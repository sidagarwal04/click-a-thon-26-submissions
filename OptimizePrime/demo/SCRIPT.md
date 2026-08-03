# demo/SCRIPT.md — the five-minute demo, word for word

> **Summary:** The talk track for `demo/run.sh` — five beats, per-beat second budgets that sum to
> 5:00, what is on screen during each, and a rehearsed recovery line for every known failure mode
> (cold service, dropped network, wrong model generation on the graded DB). Everything is READ-ONLY
> against `sonyliv`; the runner refuses writes by construction. Every beat has a committed fallback
> in `evidence/demo/` that `run.sh` plays automatically if the live query fails; `--offline` plays
> the whole demo from fallbacks. Machine time is ~14 s total (measured, `evidence/demo/rehearsal.txt`)
> — the five minutes are talk time. This is **not** the final submission video: the current official
> contract requires 2–3 minutes and a live ClickStack dashboard walkthrough before the **12:00 PM
> IST, 2026-08-02** portal close, while this script keeps
> dashboards outside the main path. Use it as technical rehearsal material only.

## How to drive it

```bash
demo/run.sh --pace        # the presenting path: ENTER advances between beats
demo/run.sh --offline     # no network at all — every beat from committed artifacts
```

Run `demo/run.sh` once ~10 minutes before presenting: it warms the Cloud service (auto-suspend
makes the first query ~29 s) and sanity-checks that `sonyliv` still answers 905,558 events /
peak 2,917. **If the sanity check warns, present with `--offline` and say nothing that the
committed artifacts do not say.** After beat 4 the runner restores `evidence/reconcile.txt`
itself; the tree stays clean.

Timing discipline: the budgets below sum to 5:00 **with the encore cut**. If beat 2 ran long,
drop the encore *and* compress beat 5 to its last two sentences (worth ~45 s back).

---

## BEAT 0 · pre-flight — 0:15

**On screen:** version line, warm-up seconds, `905558 events · day-tier peak 2917 · sanity OK`.

**Say:** "This is the graded ClickHouse Cloud service — the actual database, not a copy. One
sanity line: 905 thousand events, peak 2,917. Everything you'll see is read-only and served
from tables built before this demo started."

**If the warm-up took ~30 s:** "That pause was Cloud auto-suspend waking the service — that's
the one and only cold query; everything from here is milliseconds." (The delay is part of the
story, not a failure.)

## BEAT 1 · the problem — 0:55

**On screen:** minute-by-minute table 10:52→11:00, naive vs actual, phantom-viewer column; then
the one-row hours summary.

**Say:** "A cricket match is streaming — how many people are watching right now? The obvious
answer counts every open session. The left column is that answer; the right column is people
actually watching — foreground, not paused, heartbeats alive. At the peak minute the naive
count says 3,708. The truth is 2,917 — it invented **791 viewers, a 21% over-count**. Summed
across the file, **33.6% of apparent watch time is nobody watching** — a phone in a pocket, or
a paused player. Ad rates and server capacity are priced off this number. That over-count is
the whole problem."

## BEAT 2 · the two signals — 1:15  ← the insight the model rests on; give it the time

**On screen:** one real session's complete raw event list (37 rows), with the three things to
watch printed above it.

**Say:** "Why is this hard? We are not handed an `is_watching` flag — just breadcrumbs. This is
one real session, unedited. Three things. **First**: at 10:31:49 the viewer hits pause — and
look at the telemetry: network-bandwidth pings keep arriving, every 40 seconds, all the way
through the pause. A silence detector sees *nothing*. **Second**: at 10:46:04 the app is
backgrounded — and now, genuine silence, three and a quarter minutes of nothing. **Third**,
bottom two rows: the session emits its end event, then *keeps talking* — 239 sessions do this.

Fleet-wide: an active viewer emits 4.7 pings a minute; backgrounded, 0.05 — silence a gap
detector catches; paused, **0.76 — one ping every 79 seconds, which slips under any sane gap
threshold**. So one signal cannot work. The model is a hybrid: a 150-second heartbeat gap
closes an interval for backgrounding, and explicit pause→resume windows are subtracted on top.
Either signal alone is roughly 10% wrong."

## BEAT 3 · the answer — 1:10

**On screen:** peak-per-day from the hour tier; rolling 15/60-minute trend around the peak;
platform drilldown at 10:56.

**Say:** "The serving layer answers, not a rescan. A session becomes 'active intervals'; each
interval becomes +1 where it opens and −1 where it closes, clipped at hour boundaries — 28
thousand delta rows serving 905 thousand events, and every query here is milliseconds.

Peak per day straight from the hour tier: **2,917, on July 26th at 10:56** — reading 8,192 rows,
not the raw events. The trend view: rolling 15- and 60-minute peaks and averages — the peak
holds 2,917 across the window. And the drilldown: inside that peak minute, 1,837 on Android
phones, 355 on iPhone, then the TV platforms. Same table, any dimension."

**ENCORE if ahead of schedule (+0:20):** "One trap worth showing: 'Hindi' is spelled four ways
in the raw feed. Filter `audio_language = 'hin'` and you find 1,759 of 2,187 Hindi viewers —
you silently lose 20%. Our normalised view folds the spellings at query time; storage stays
raw, and the decision is an ADR."

## BEAT 4 · the proof — 0:50

**On screen:** the gate output — five sampled minutes PASS, three definitions side by side,
the PASSED line with 17,028 minutes.

**Say:** "Why believe 2,917? The reconcile gate recomputes concurrency **from the raw events,
with a different algorithm** — window functions, where the pipeline uses array splitting — and
never reads the serving layer as input. Same spec, independent implementation. It just ran,
live, against the graded database: **17,028 minutes compared — idle minutes included — zero
mismatches**, and it exits non-zero on a single disagreement. This gate has caught real bugs:
a fabricated row, a flipped pause rule, a same-second tie. A green run means something."

## BEAT 5 · scale — 0:35

**On screen:** the 100× excerpt of `evidence/scale.txt` — serving-query table, row-count
summary vs the ceiling.

**Say:** "Does it survive success? We measured — same pipeline, synthetic audience at 10× and
100×: 89.85 million events, 1.09 million sessions, peak 251,668 — **and the gate still passes
on every minute**. The day-grain peak reads 176 KiB at 1× and at 100× — the hour tier makes
that query scale-invariant. What breaks first is derivation *memory*, not serving — and the
fix is measured too: fewer threads, which is leaner *and* faster. The numbers are committed in
`evidence/scale.txt`; this beat re-runs nothing."

**Close:** "Foreground-only concurrency, proven against raw on every minute, on ClickHouse,
with the failure modes measured before they happened. Questions."

---

## Recovery lines — rehearse these too

| Failure | What happens | What you say |
|---|---|---|
| Service cold at beat 0 (~29 s) | pre-flight absorbs it | "Auto-suspend waking up — the one cold query. Now it's warm." |
| Network drops mid-beat | `run.sh` prints the committed fallback with a banner | "The connection dropped — this is the same query's saved output, committed before the demo. The pipeline is unchanged; I'll re-run it live for you afterwards." |
| No network at all | start with `demo/run.sh --offline` | "We're on the committed evidence files — every number here was captured from the live service and is in the repo history." |
| Beat-0 sanity MISMATCH (wrong model generation on `sonyliv` — happened once already today) | runner warns loudly | Switch to `--offline`. "We'll drive from the committed artifacts — they're self-consistent." **Never improvise numbers against a database in an unknown state.** |
| Someone asks to see a dashboard | not in the 5:00 path | open `docs/artifacts/2026-08-01-clickstack-dashboards.html` as a fallback only. The official video must instead walk through the real ClickStack UI live. |
| Reconcile takes longer than expected | 240 s cap, then fallback | "It compares seventeen thousand minutes — while it runs: the point is that it's a *different implementation* of the same spec." |

## The one absolute rule

Everything in this demo is a `SELECT`. **Never** run `make model`, `tools/build-model.sh`,
`tools/publish.sh`, or any INSERT/TRUNCATE/ALTER/CREATE/DROP/OPTIMIZE against `sonyliv`.
`run.sh` refuses write statements by construction — do not work around it, on stage or off.
