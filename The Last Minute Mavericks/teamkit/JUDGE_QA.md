# Judge Q&A — prep sheet

Scale, timing, findings, blind-test scores, validator behaviour and noise floors were re-measured
today against the live service. Four baseline-comparison figures (§2: −45.0 vs −43.5, the +25.4%
phantom, the 1.7pp leakage, the +191% on a 14-day slice) come from measurements the team recorded
in `run_incident.py`'s comments — cite them as "we measured this earlier", not as fresh numbers.

Where a claim in `CLAUDE.md` or the published brief is **not** backed by code, it is marked ❌ — say
the honest version, never the brochure version. One bluffed answer costs more than one missing
feature.

---

## ⚠️ Read this before anything else — 3 things to fix or stop saying

**1. ~~The LLM narration path is dark.~~ FIXED 2026-08-02.** `.env` defines `LLM_API_KEY` (the name
`CLAUDE.md`'s connection block specifies), but `agent/narrate.py`, `ui/llm.py` and
`tests/e2e/adjudicate.py` all read only `OPENAI_API_KEY` — so a correctly-filled `.env` sent every
call to the deterministic fallback, silently, because that fallback is grounded and looks fine.
All three now accept either name. Verified: narration returns `source: "llm+validator"`,
`ui.llm.resolve()` returns `openai`, and the adjudicator lists OpenAI as its first backend.

Re-check after any `.env` change: `python run_incident.py --db rca --narrate` must print
`[llm+validator, cites N evidence ids]`, not `[deterministic, …]`.

⚠️ **The deployed VM has its own `.env`** — this fix only reaches the demo after a redeploy
(`scripts/deploy_mercury.sh`). Until then the API's narration is still the template.

**2. Four named methods in our own docs do not exist in code.** If a judge has read the brief and
asks, answer with what we built — it is strong on its own.

| Claimed | Reality |
|---|---|
| Adtributor (Explanatory Power + JS-divergence surprise) | ❌ nowhere in the codebase |
| LangGraph orchestration | ❌ not a dependency, not imported |
| STL-on-residuals baseline | ❌ it's a same-weekday median + multiplicative detrend |
| Detection "as a materialized view" | ❌ `rca.cube` is a plain MergeTree filled by `INSERT … SELECT` |
| Benjamini–Hochberg FDR gate | ❌ we gate on effect size + volume, not FDR |
| ClickStack / OTel → HyperDX | ✅ **landed 2026-08-02** — `integrations/otel.py` + `clickstack/`, spans in `api/server.py`, off unless `CLICKSTACK_ENABLED=1` |

`CLAUDE.md` now carries this same ✅/❌ split in its "The method" section, so it can't drift back.

**3. LibreChat is not currently running.** Docker isn't up. The shim (`:8601`) *is* running and
answers `/v1/models`. Either `docker compose -f integrations/librechat/docker-compose.yml up -d`
before the demo, or present LibreChat as "wired, shown via the shim" and don't click into it.

---

## The numbers to have in your head

| | |
|---|---|
| Raw data | **9,000,000** events → **4,511,141** cube rows, 35 days (Jun 1 – Jul 5 2026) |
| Full scan, real data | **20.5 s** wall clock, end to end, from cold |
| Findings on `rca` | **6 real incidents, 93 ruled out** (live API) |
| Blind test slices | 2 × **10,000** rows, 6 planted incidents + 3 controls |
| Blind test result | **6/6 localized, magnitudes exact, 0 false positives** — on *both* engines |
| Clean slice (no anomalies) | **0 investigations** — no self-inflicted false positives |
| Live API | `http://23.101.175.68:8077` — `/scan`, `/health`, `/docs` |
| Langfuse | public trace per scan, span per incident |

The 6 live findings, in case you're asked to narrate them cold:

```
ecpm      Jun 16–18  +23.5%  ad_format=native × region=EU          LOCALIZED_2D
ecpm      Jun 16–20  -30.6%  ad_format=interstitial × region=EU    LOCALIZED_2D
ecpm      Jun 19–22  -34.8%  category=finance                      LOCALIZED_1D
requests  Jun 21     -45.0%  — no segment —                        GLOBAL_UNLOCALIZED
fill_rate Jun 23–25  -44.6%  os_version=Android 15                 LOCALIZED_1D
fill_rate Jun 28–30  -50.4%  region=APAC × os_version=iOS 18.1     LOCALIZED_2D
```

---

## 1. Scope and framing

**Q: What does this actually do?**
A key ad metric moves. We find which segment is responsible, prove it with SQL, and write a
diagnosis where every number was computed rather than guessed. All the analysis is ClickHouse SQL;
the model only turns a structured evidence bundle into English.

**Q: Why only revenue? Isn't a general any-metric framework more impressive?**
Revenue decomposed through fill rate and eCPM is the tree that pays. A generic framework looks
identical to a specific one in a 5-minute demo — but a judge can instantly tell shallow from deep.
We went deep on one tree: three metrics scanned, 2-D and 3-D cross-cuts, look-alikes peeled and
disproved. *(Fill rate = share of ad requests that got an ad back. eCPM = revenue per thousand
impressions.)*

**Q: Why isn't CTR in scope?**
This is a CPM model — advertisers pay per impression, so clicks buy nothing. CTR moving is context,
not a cause. We prove we mean it: one of our test controls halves CTR in India and the engine
correctly reports nothing. Scanning it would let us "find" incidents that cost zero rupees.

**Q: Who is this for?**
Whoever gets paged at 3am when revenue drops. Today they open a dashboard and eyeball 40 charts.
This says "it's Android 15 fill, down 44.6%, here's the query" in 20 seconds.

---

## 2. Detection

**Q: How do you decide something is anomalous?**
Each segment is compared to its *own* normal, not to a global average. We take the same weekday
from the 3 preceding weeks, compute the median, then measure how far today sits from it in units of
MAD. *(MAD = median absolute deviation: the typical distance from the middle. Unlike a standard
deviation, one wild day doesn't inflate it, so the outlier can't hide itself.)* Flag at |z| > 3.5,
and only if the relative move also clears a floor — 5% for ratio metrics, 10% for volume.

**Q: Why same-weekday instead of a simple average of recent days?**
The data has a −20% weekend dip. Against a flat mean, every Saturday is an incident. Concretely: on
this data a flat "all other days" baseline reports one of our incidents at −45.0% when the truth is
−43.5%, and another at −50.4% against a true −50.7%. Same-weekday, preceding-only.

**Q: Why preceding-only? You have the later days sitting right there.**
A live run doesn't have next week. Letting future days in is leakage, and it's worth 1.7pp on one
of our incidents. We also drop any baseline day that belongs to *another* incident — otherwise a
prior −40% window becomes the next window's "normal" and the same segment comes back as a phantom
+25.4% spike that outranks the real cause. That's measured, not theoretical.

**Q: Two thresholds and a volume floor sounds arbitrary. Where did they come from?**
The floors are set from measured noise, not taste. On a clean slice with nothing planted, 2-D eCPM
cells wobble p50 0.35%, p99 1.94%, max 4.32%. A 5% floor is ~2.5× the p99. The volume floor
(1500 requests/day) exists because a ratio computed on 200 requests is noise by construction.

**Q: What if the anomaly is smaller than your floor?**
We miss it, deliberately — and the deployed engine softens exactly this. It runs in "recall mode":
the floor drops to 5%, and anything landing in the 5–10% band goes to an adjudicator that sorts it
into reported / needs-review / suppressed rather than being silently dropped. Anything ≥10% or
global is reported no matter what the adjudicator says — the LLM is not allowed to suppress a solid
incident.

**Q: ❌ Your doc says STL decomposition.**
It doesn't do STL. It's a same-weekday median plus a robust multiplicative detrend for the ~+0.3%/day
growth. I'd rather tell you what it is than what we planned.

---

## 3. Decomposition

**Q: Revenue moved. How do you split the blame across the funnel?**
LMDI — the log-mean Divisia index. *(Plain version: when several factors multiply together to make
a total, LMDI splits the change in that total into one number per factor, and the parts add up to
the whole exactly.)* Revenue per day = requests × fill rate × render rate × eCPM/1000, so we get an
exact split: this much of the drop is traffic, this much is fill, this much is price.

**Q: Any decomposition sums to the total if you define the residual as "everything else". How is
yours better?**
It isn't better because it sums — it sums *by construction*, and we say so in the output. The
residual being zero validates nothing. What we validate is LMDI against Shapley: we recompute every
factor's contribution as the mean of all 24 orderings of the four factors, and report the maximum
divergence between the two methods as a percentage. If the two disagree by more than 10% we mark
the decomposition unstable rather than quoting it.

**Q: Why do you need the ruled-out factors at all?**
That *is* the answer, usually. "Traffic was normal, price was normal, fill collapsed" is the
diagnosis. A near-zero LMDI contribution is a factor eliminated with a number attached, not a factor
we forgot to check. Every investigation carries all five funnel factors, each with its own verdict.

---

## 4. Attribution and Simpson's paradox

**Q: How do you find the responsible segment?**
Bottom-up. Every segment of every scanned dimension is tested against its own baseline, then gated
on effect size — a segment must explain at least 0.5% of the metric's movement (its share of volume
times its relative move) to survive. Then we descend: if a sub-cell inside the winner concentrates
the move at least 1.4× while its siblings stay normal, we go deeper, up to 3 dimensions.

**Q: ❌ The brief says Adtributor.**
We didn't build Adtributor. What we built is the effect-size gate plus greedy cross-cut descent and
a peel test. I'd rather show you the peel test — it's the part that actually changes answers.

**Q: What's the peel test?**
Suppose fill collapses in EU on Android 14. Three things light up: the 2-D cell at −50%, region=EU
at −16.1%, and os_version=Android 14 at −13.2%. A naive tool reports three incidents. We re-run
each candidate with the culprit's rows removed. EU's residual becomes **+0.0%** and Android 14's
becomes **+0.1%** — they were never independent, they were the same incident seen from two angles.
They move to the ruled-out list with those numbers attached. That's Simpson's paradox handled with
a query instead of a hand-wave.

**Q: Can you find something that's invisible at the single-dimension level?**
That's exactly the test above. A −50% drop in a cell that's ~10% of traffic dilutes to −16% at its
parent — under a naive threshold it's just a bad week for EU. We scan dimension pairs directly and
keep a pair only if no already-flagged 1-D parent explains it, or if it's at least 1.4× worse than
its parent.

**Q: What if there is no responsible segment?**
Then we say so. `GLOBAL_UNLOCALIZED` is a first-class verdict, not an error. One of the six live
findings is exactly that — requests down 45% on Jun 21, uniform across every dimension. Blaming a
segment there would be the failure mode. One of our test fixtures plants a global drop specifically
to check we don't invent a scapegoat.

---

## 5. The trust layer — narration

**Q: How do I know the model didn't make up these numbers?**
The model never sees a raw row and never does arithmetic. It gets a facts block and an evidence
list — each item `{id, label, value, sql, query_id}` — and is told to write numbers as `{{ev_N}}`
placeholders. We resolve the placeholders and then run a validator: any numeral in the output that
isn't in the evidence or facts is treated as invented, and the whole draft is discarded. One retry,
then we fall back to a deterministic template built from the same evidence.

**Q: Show me the validator actually rejecting something.**
Four cases, run today against a real bundle:

| draft | outcome |
|---|---|
| "fill_rate fell 62.7%, costing $18,400" | **REJECTED** — neither number exists in evidence |
| "fill_rate moved {{ev_99}}" | **REJECTED** — unresolved placeholder |
| "fill_rate at region=LATAM was {{ev_2}}" | accepted → resolves to 0.4125 |
| "fill_rate moved -45.0% at region=LATAM" | accepted — −45.0 is a computed value |

The UI also has a one-click fabrication demo that doctors a grounded answer with
"confidence 99.97% (p < 0.001)", runs it through the same validator, and shows the rejection plus
the clean replacement. It's deterministic and offline, so it can't flake on stage.

**Q: Be precise — what exactly does the guarantee cover?**
It covers numbers: **the model cannot state a figure we didn't compute.** It does not stop the model
writing a bad sentence with correct numbers. Note the fourth row above — a raw number that matches a
computed value is accepted, so the `{{ev_N}}` citation trail is encouraged, not enforced, and
`citations` can come back empty even on a valid answer. That's the honest boundary of the claim.

**Q: So what happens if the LLM is down?**
Everything still works. The template writes "fill_rate moved −45.0% at region=LATAM, which is the
primary driver. requests, render_rate, ecpm were normal over the same window — ruled out." Same
evidence, same numbers, no prose flair. The diagnosis degrades; it never fabricates. That's the
right failure direction, and it's why the missing env var went unnoticed.

**Q: Isn't the LLM doing anything real, then?**
Two jobs: narration, and adjudication of the 5–10% band in the deployed engine. Both are constrained
— the adjudicator can only move an existing candidate between trays, never create one, never change
a value, and never suppress anything ≥10% or global.

---

## 6. Traceability

**Q: Can I see how a conclusion was reached?**
Every scan emits a public Langfuse trace: a root chain per scan, one span per investigation carrying
the metric, window, verdict, culprit, the full LMDI/Shapley decomposition, the ruled-out list, and
the evidence objects with their ClickHouse `query_id`. Public means you open it without our
credentials.

```
test1  https://cloud.langfuse.com/project/cmsa4wcn20ah0ad0iy746nak4/traces/43fa3b34e4c35bd520869072820b827f
test2  https://cloud.langfuse.com/project/cmsa4wcn20ah0ad0iy746nak4/traces/06905a95b93ef7af363ccdbc7875105a
live   https://cloud.langfuse.com/project/cmsa4wcn20ah0ad0iy746nak4/traces/49de25066fcc1943af286637bc2f6f58
```

**Q: What's a `query_id` worth to me?**
It's the receipt. Every number in the bundle carries the id of the ClickHouse query that produced
it, so you can pull that query out of `system.query_log` and re-run it yourself. The claim isn't
"trust our pipeline" — it's "here's the SQL, check it".

**Q: Does tracing slow you down or break the run?**
Tracing is wrapped so a Langfuse failure can never take the scan down — the API catches it and
serves the bundle un-traced. We pin `langfuse==4.14.2` because the v4 SDK removed the v2/v3 APIs
outright.

**Q: Do you use ClickStack?**
Yes — landed 2026-08-02, and it's the second trace layer, not a duplicate of Langfuse. Langfuse
traces the *investigation* (why this segment, what got ruled out). ClickStack traces the *machine*
— OpenTelemetry spans for connect / detect / decompose, exported to HyperDX. The nice part is
where it lands: ClickStack stores its spans in ClickHouse tables, so our latency telemetry is
queryable with the same SQL as our business data. It's off unless `CLICKSTACK_ENABLED=1`, degrades
to a no-op tracer if the collector is down or the packages aren't installed, and writes to its own
bundled ClickHouse — never the competition service.

---

## 7. ClickHouse

**Q: Why is ClickHouse the engine and not just storage?**
Because the drill-down *is* the workload. Finding the culprit means aggregating 9M events by day
across nine dimensions, then re-aggregating for every candidate segment, then re-running each one
with the culprit excluded. That's hundreds of grouped aggregations — pulling rows into Python would
be slower and would put raw data in front of the model, which we've forbidden. Full scan: **20.5
seconds**.

**Q: What's the cube and why not query raw events?**
`rca.cube` pre-aggregates the 9M events by day × the nine low-cardinality dimensions — 4.5M rows of
sums. Every ratio is computed sum/sum at read time, never averaged from pre-computed ratios, so
roll-ups stay correct. High-cardinality ids (app, advertiser) are deliberately excluded: no anomaly
lives there and slicing them is pure false-positive surface.

**Q: A ratio of averages isn't the average of ratios. Did you get that right?**
Yes, and it's why the cube stores only sums. `fill_rate` for any group is `sum(fills)/sum(requests)`
computed at query time. If we'd stored per-row fill rates and averaged them, a 100-request segment
would carry the same weight as a 100,000-request one.

**Q: What happens when the unseen dataset arrives?**
It loads into a fresh database with no cube, so the scan builds its own on first run — otherwise it
would crash with `UNKNOWN_TABLE` the moment sealed data drops. Day counts come from the data, never
a constant: an earlier version assumed 35 days and reported +191% on a 14-day slice.

---

## 8. Integrations

**Q: How does LibreChat fit — is it your UI?**
No, and that's deliberate. LibreChat is self-hosted in `integrations/librechat/` and talks to our
shim on port 8601, which presents an OpenAI-compatible endpoint with one model,
`rootcauseos-rca`. Every answer routes through the same evidence-only prompting and the same numeric
validator as the dashboard. It's a fourth surface onto the same grounded engine, not a replacement
for the product. *(Right now the containers aren't up — see the top of this doc.)*

**Q: Why not just let people chat with the database?**
Because then the model is doing the analysis, and every number it says is a guess dressed as a
fact. The whole point is that the numbers come out of ClickHouse and the model only phrases them.

**Q: ❌ ClickStack?** — Not built. See §6.

---

## 9. Testing — the part most teams skip

**Q: How do you know it works on data you haven't seen?**
Three layers. `tests/e2e/` builds a ~10M-row synthetic slice with five planted incidents and a
quarantined ground-truth manifest. `test-sql/` is two small 10,000-row slices with anomalies hidden
in them and an answer key the engine is never allowed to read. `tests/battletest.py` plants *fresh*
random anomalies each run so we can't tune to a fixed set.

**Q: Results?**
Six planted incidents across the two blind slices: **6/6 detected, 6/6 localized to the exact
segment, magnitudes matching to 0.1pp, zero false positives**, and all three controls correctly
silent. Same result on both the local engine and the deployed one.

**Q: What are the controls?**
Things that *look* like incidents and must produce nothing: a −58% fill collapse in a segment doing
940 requests/day (under the volume floor); a −2% global eCPM dip (under the effect floor); and a
−40% CTR crash (out of scope by design). A detector that fires on these is crying wolf.

**Q: How do you know the fixtures aren't rigged in your favour?**
The grader failed loudly three times during development, each time on a real defect in the
*fixture*, which we fixed rather than hid:
- one ad format per segment let a fill drop yank the format mix and manufacture 4 phantom eCPM
  cells at −12%…+8%; every segment now serves all five formats;
- randomly-drawn segments left `region=LATAM` perfectly correlated with the categories it happened
  to carry, so a drop moved 15 dimension values equally and the engine correctly said "global" —
  replaced with an orthogonal design;
- one segment was accidentally sized at 27% of all traffic, where a drop genuinely stops being
  localizable.

Also: a clean slice with **zero** planted anomalies returns **zero** investigations, so nothing in
the results is the fixture talking to itself.

**Q: Isn't synthetic data too easy?**
It's calibrated to the real slice's profile — fill 78.1%, render 98.0%, eCPM ~2.47, −20% weekends,
+0.3%/day growth — and the anomalies are injected on the funnel, never on the ratio, so the identity
`requests × fill × render × eCPM/1000 ≡ revenue/day` still holds exactly. The hard cases are
deliberately hard: a 2-D interaction invisible at one dimension, a gradual ramp rather than a step,
and a baseline that overlaps another incident's window.

**Q: You tested one engine but deploy another. Doesn't that make the results meaningless?**
It would have, so we fixed it rather than argued it. The API now serves the same engine the tests
grade. We picked which one to keep by measuring both across 6 blind slices — 33 planted incidents:

| | detected | localized | false positives |
|---|---|---|---|
| **root engine (now everywhere)** | **33/33** | **33/33** | 1 |
| the `v2` fork we retired | 29/33 | 29/33 | 0 |

The fork missed 4 of 13 on the hardest slice and had no contamination exclusion. It did have one
thing worth keeping — `snr`, the deviation measured in the segment's own noise units — so we ported
that in first; the adjudicator's noise rules still work. Verified after the switch: same 6 incidents
on live data, 18.5s, snr present on all 5 localized ones.

One honest caveat: the adjudicator still wasn't exercised, because every planted incident is ≥23%
and nothing landed in its 5–10% band. A fixture in that band is the obvious next test.

**Q: Why is `snr` worth having when you already have the percentage?**
Because 6% means different things in different segments. A 6% move in a segment that normally
wobbles 0.3% is 20× its own noise; the same 6% in a jumpy segment is nothing. `snr` is that ratio,
and it's what lets the adjudicator call a small deviation real without lowering the floor for
everyone. On live data our incidents run snr 28–145.

---

## 10. Hostile questions

**Q: What's the weakest part of this?**
The named-method gap in our own documentation — we wrote a plan naming Adtributor, LangGraph and
ClickStack, and shipped something narrower and, I'd argue, better tested. Second weakest: the
adjudicator's 5–10% band is untested by our fixtures.

**Q: What breaks it?**
Three things. An incident under the volume floor — we won't see it, by design. An incident that's
truly 4-dimensional — we descend to 3. And a slice shorter than about four weeks, where the
same-weekday baseline runs out of history and falls back to fewer weeks.

**Q: Your incident magnitudes come from the same code that detects them. Isn't that circular?**
It would be, so we don't do it that way. Detection uses a median over the whole series. The
*reported* number is recomputed as sum/sum over the window against the like-for-like baseline —
and in the blind tests that reported number is checked against a deviation measured independently
from the source rows by the grader, which reimplements the baseline rule separately. They agree to
0.1pp.

**Q: If I gave you a dataset right now, what would you have to change?**
Nothing. `python run_incident.py --db <new_db> --json out.json --trace`. The loader reads column
names from the file, the cube builds itself if missing, and day counts come from the data. That's
the thing we optimised for above all else.

**Q: What would you build next, with a week?**
Adjudicator coverage in the 5–10% band with a fixture built for it, then ClickStack for the SQL-layer
trace, then the honest version of Adtributor's surprise score — an anomaly that's unusual for a
segment matters more than one that's merely large.

**Q: What are you actually proud of?**
That when we found a false positive we fixed the data model instead of raising the threshold, and
that the fallback path is grounded rather than clever. The system's worst behaviour is "says less
than it could", not "says something wrong".

---

## Traps — do not do these

- Don't say "the LLM writes the diagnosis" about the **deployed API** until it's been redeployed —
  the key-name fix is in this repo, not yet on the VM. Locally, confirm `llm+validator` prints.
- Don't say Adtributor, LangGraph, ClickStack, STL, materialized view, or Benjamini–Hochberg.
- Don't say "every number is a citation" — say "no number can appear that we didn't compute".
- Don't call `--rebuild-cube` on `rca_ts1`/`rca_ts2`; the cube *is* the dataset there.
- Don't claim precision numbers from `tests/README.md` — those are the old placeholder detector
  (recall 0.88, precision 0.12). Current blind results are in §9.
