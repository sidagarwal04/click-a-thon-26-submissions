# DECLINE_ALERTING — detecting concurrency decline, and telling apart WHY

> **Summary:** The statement's one optional item (`docs/upstream/PROBLEM_STATEMENT.md:42`) is
> detecting and alerting on concurrency decline, caused by *the asset ending*, *a system issue*, or
> *the content not being engaging*. Concurrency declines constantly and legitimately, so detection is
> the easy half and **discrimination is the deliverable**. Detector: below 80% of a 15-minute trailing
> median, lagged 3 min, floored at 100 concurrent and 50 sessions — **28 firing minutes** on the
> delivered file where a naive "down 20% in 5 minutes" fires **962**. Classifier: `end_coverage` and
> heartbeats-per-session — **both thresholds are FITTED to a 46× separation in the delivered file, not
> derived from measured semantics.** This document claimed otherwise until 2026-08-02; the claim was
> false and §3.1 shows why. Live in hosted HyperDX as
> 3 alerts over 7 tiles. **We deliberately did not put an LLM in the detection path** — see §6.
> Regenerate every number here: `tools/clickstack-alerts.sh --validate`.

Owned by `tools/clickstack-alerts.sh`. Evidence: [`evidence/alerting/`](../evidence/alerting/).

---

## ⚠ CORRECTION 2026-08-02 — the `hb_per_session` anchor is inverted

This document claimed the classifier's thresholds are anchored to semantics rather than fitted,
specifically that **`hb_per_session < 1.0` sits below the fully-paused heartbeat rate ADR 0007
measured (0.756/min), so tripping it cannot be viewer behaviour.**

**That is backwards, and it is arithmetic, not opinion: 1.0 > 0.756.**

The threshold sits **above** the paused rate. A fully-paused session heartbeats at 0.756/min, which
is below 1.0, so it **does** trip the alert — meaning tripping it is *exactly* viewer behaviour, the
opposite of what was claimed. Measured alongside: **94,472 of 843,600 heartbeats (11.2%) occur while
a session is paused**, so this is not a rare corner.

Found by Codex audit 005. **The orchestrator then repeated the claim in a merge commit without
checking it** — an unverified claim inherited and amplified, which is the failure this repo keeps
re-learning.

**Status of the threshold itself: unresolved.** It may still be a *useful* discriminator — a genuine
outage drives heartbeats far below 0.756 — but the value is **fitted, not anchored**, and this
document must not claim otherwise until someone derives one that is. A fitted threshold openly
labelled is defensible; a fitted one described as principled is not.

## 1. Why this is not a threshold problem

The naive reading of "alert on concurrency decline" is a threshold on rate of change. It does not
survive contact with the data, because **concurrency falls constantly and legitimately**: every asset
ends, every prime time ends, every night happens. An alert that fires on all of them is worse than no
alert, because people learn to ignore it — and this repo already has a rule about exactly that
(`AGENT_WORKFLOW.md`: don't add a gate you won't maintain).

Measured over all 6,195 minutes of the delivered file's spine:

| detector | firing minutes | verdict |
|---|---:|---|
| "down >20% versus 5 minutes ago" | **962** | unusable — fires on 15.5% of all minutes |
| median baseline, **not** lagged | 22 | usable, but detects late (§2) |
| mean baseline, lagged 3 min | 30 | usable; one spike minute moves the reference |
| **median, lagged 3 min, floored — SHIPPED** | **28** | — |

The naive detector's noise is almost entirely in the overnight tail, where a 20% move is two viewers:

| baseline band | minutes | naive fires | shipped fires |
|---|---:|---:|---:|
| `<10` concurrent | 5,804 | **918** | 0 |
| 10–99 | 327 | 27 | 0 |
| 100–999 | 12 | 1 | 5 |
| `>=1000` | 52 | 16 | 23 |

That is what the two floors buy. `baseline >= 100` refuses to have an opinion about a handful of
viewers; `baseline - concurrent >= 50` refuses to call a 20% move on 120 concurrent an incident.

## 2. The detector

For minute `M`:

```
baseline B(M) = median( concurrent ) over minutes [M-17, M-3]
fire iff   B >= 100
     and   concurrent < 0.8 * B
     and   B - concurrent >= 50
```

Three choices, each with a reason and a measurement:

- **Median, not mean.** The heartbeat stream is bursty (inter-arrival p50 0 s, p99 49 s —
  [DATA_DICTIONARY.md](DATA_DICTIONARY.md) trap 6), so single-minute spikes are ordinary. A mean
  baseline lets one spike move the reference; measured, it fires 30 times to the median's 28.
- **Lagged 3 minutes.** A baseline window that includes the minutes under test is dragged down by the
  very decline it is supposed to measure. Measured on the real episode: the un-lagged form first
  detects at **11:16**, the lagged form at **11:13** — same episode, **three minutes earlier**.
- **15-minute span.** Long enough to survive minute-to-minute jitter, short enough to track a
  prime-time ramp rather than fighting it.

**Rejected: same-time-yesterday.** It is the textbook baseline for seasonal traffic and it is useless
here — the delivered file is a single live event, not a repeating daily pattern:

| minute | today | same minute, previous day |
|---|---:|---:|
| 2026-07-26 09:00 | 29 | 5 |
| 2026-07-26 10:00 | 57 | 4 |
| 2026-07-26 10:56 | **2,917** | **5** |
| 2026-07-26 11:20 | 1,656 | 4 |

A day-over-day baseline would treat the entire event as a 58,000% anomaly and then treat its end as
normal. Noted as a real limitation: on a service with genuine daily seasonality, a trailing median
under-reacts to a scheduled evening ramp-down, and a seasonal baseline would be the better choice.
The delivered data cannot justify one, so we did not ship one.

## 3. The classifier — the actual deliverable

Evaluated **only** on minutes the detector fired. Two features carry it:

- **`end_coverage` = `ends / (net_drop + starts)`** — roughly, how much of this minute's departure is
  explained by explicit `VideoSessionEnd` events. **It is not a share and does not top out at 1.0** —
  measured, it exceeds 1.0 on **81 of the file's 6,195 minutes and reaches 3.0** (§3.1).
- **`hb_per_session` = heartbeats / concurrent** — how loud the stream is per active viewer. Note the
  two halves come from different populations: the numerator counts **every** `VideoHeartbeat` in the
  wall-clock minute, including from paused and backgrounded sessions; the denominator is **active**
  concurrency, which excludes the paused.

### 3.1 · The thresholds are fitted, and this document used to claim they were not

Until 2026-08-02 the text above read: *"a threshold of **1.0 sits above the fully-paused rate**
(0.756/min, [ADR 0007](adr/0007-gate-answers-pause-needs-explicit-handling.md)): tripping it means the
fleet is quieter than it would be if every remaining viewer had hit pause."* **That argument is
backwards, and it was repeated in a merge commit without being checked.** Measured evidence:
[`evidence/alerting/anchor-audit-2026-08-02.txt`](../evidence/alerting/anchor-audit-2026-08-02.txt).

**ADR 0007's rates are fine** — re-derived live, they reproduce to the digit: **0.756**/min paused
(21,068 closed pairs, 3,002,604 s, 37,854 beats) and **0.047**/min backgrounded. The fault is in the
inference drawn from them, twice over:

1. **The inequality is the wrong way round.** The trip condition is `hb_per_session < 1.0`, and the
   fully-paused reference is 0.756. Since **0.756 < 1.0, a fully-paused fleet *satisfies* the trip
   condition** — it does not sit safely above it. For "quieter than fully paused" to follow from
   tripping, the threshold would have to be **below** 0.756.
2. **The two numbers are not comparable.** ADR 0007's 0.756 is beats per *paused session-minute*; the
   alert's ratio divides *all* heartbeats in a minute by *active* concurrency. Different populations,
   so no threshold on the second is justified by a rate measured on the first. The hypothetical is not
   even representable: if every viewer paused, active concurrency → 0, `greatest(concurrent,1)` floors
   the denominator at 1, and the ratio reads **high**, not low.

**What is actually true, and is enough.** The two observed classes are separated by a factor of **46**
— the worst outage minute reads 0.071, the best ending minute 3.248 — and **every threshold from 1.00
down to 0.25 classifies the delivered file identically** (11 OUTAGE, 17 ENDING, measured). So the
threshold is *fitted to a very wide gap*, which is a defensible thing to ship and an indefensible
thing to dress up as a derivation.

**Recommended, not applied: move the OUTAGE threshold to 0.5.** It costs nothing on this file and puts
the number below the fully-paused rate, which is what the original sentence needed. It would make the
anchor *directional* — reason 2 above still stands, so it would never be exact. The change lives in
`tools/clickstack-alerts.sh`, which this task does not own; it is recorded here as the fix.

> ⚠ **The same false claim is still printed by the tool.** `tools/clickstack-alerts.sh --validate`
> emits *"Anchors (NOT fitted) … The OUTAGE threshold of 1.0/session/min sits ABOVE the fully-paused
> rate"* in its own output. That file is not owned by this task; until it is corrected, **trust this
> section over the banner the script prints.**

Likewise the `end_coverage` boundaries of 0.2/0.7 are fitted, not meaning-fixed. The ratio runs above
1.0 because its numerator counts **raw** `VideoSessionEnd` rows — **14 sessions emit more than one** —
while its denominator is **modelled** net concurrency loss, whose minute is tail-adjusted and does not
line up with the raw event's minute.

**One thing the audit did not find: a false positive.** Across every minute where heartbeats were
still arriving, only **3 of 3,816** read below 1.0, and those 3 are in the truncation tail. Normal
viewer behaviour was never shown to trip OUTAGE. The threshold is not demonstrably unsafe — it is
demonstrably not justified by the argument that was given for it.

| class | condition | response |
|---|---|---|
| **OUTAGE** (system issue) | `hb_per_session < 1.0` **and** `end_coverage < 0.2` | **page someone** |
| **ENDING** (asset ended) | `end_coverage >= 0.7` | none — expected |
| **DISENGAGEMENT** (not engaging) | `hb_per_session >= 2.5` **and** `pausebg_per_session >= 1.5 ×` its own trailing median | a content decision, not an ops one |
| **UNCLASSIFIED** | anything else | look at it |

`OUTAGE` is tested first, because a dead fleet can produce any coverage ratio at all.

**`UNCLASSIFIED` is a deliberate output, not a gap.** A decline that is 20–70% explained is genuinely
ambiguous, and saying so is more useful than forcing it into a bucket. The 0.2/0.7 boundaries are the
edges of that ambiguous band, chosen for margin: the observed ending minutes range 0.92–1.70 and the
observed outage minutes 0.00–0.03, so nothing in the delivered file sits anywhere near either edge.

Feature separation by phase of the delivered day — this is the gap the thresholds are fitted to, and
the margin is what makes fitting them acceptable (§3.1):

| phase | minutes | `hb_per_session` | `end_coverage` | `pausebg_per_session` |
|---|---:|---:|---:|---:|
| pre-surge (flat) | 90 | 6.76 | 0.50 | 0.272 |
| the RISE | 30 | 5.97 | 0.52 | 0.526 |
| **the DECLINE** | 30 | 5.90 | **1.17** | 0.595 |
| after the file truncates | 16 | **0.00** | 0.00 | 0.000 |

Note that `hb_per_session` does **not** separate ending from normal (5.9 vs 6.8) — only
`end_coverage` does. And `end_coverage` does not separate outage from ending on its own either; the
pair does. That is why both are required rather than either alone.

## 4. Tested against the real episode — including what failed

The delivered file contains exactly one large decline: **2026-07-26 11:00 → 11:30**, from a peak of
2,917. All 28 firing minutes and their verdicts are in
[`evidence/alerting/detector-validation.txt`](../evidence/alerting/detector-validation.txt) §5.

**ENDING — verified, 17 of 17 minutes.** 11:13 → 11:29 classify as `ENDING` with `end_coverage`
0.92–1.70 while heartbeats stay healthy at 3.25–6.09/session. This is a true decline correctly
called expected. It is **platform-wide, not a single content boundary**: 2,318 distinct assets close
sessions in that window and the biggest accounts for only **19.2%** of the 6,963 closes. So the right
reading is "a scheduled event ended across the platform", and a per-asset alert would have missed it
by looking at any one title.

**OUTAGE — fires correctly on the signal, but the episode is not a real outage.** 11:30 → 11:40
classify as `OUTAGE` with `hb_per_session` 0.07 → 0.00 and `end_coverage` 0.03 → 0.00. Read honestly:
**the file simply stops.** The last event in the whole dataset is `2026-07-26 11:30:04.847`;
everything after it is the model's tail-grace decaying to zero. So this is a **true positive for
"ingestion stopped"** — which in a real deployment genuinely is a page-worthy system issue — but it is
**not** a validated example of a playback outage where viewers drop while ingestion continues. We
have no such example and did not manufacture one.

> Corroborating the same limit from the other side: the file has **0 unclosed sessions** and **0 open
> intervals** across all 10,866 sessions. Every session in the delivered data closes properly. The
> single strongest signature of a real outage — a population of sessions that stop heartbeating and
> never close — **does not occur in this dataset at all**.

**DISENGAGEMENT — implemented, never observed, therefore UNVALIDATED.** No minute in the delivered
file classifies as disengagement, and this is not a tuning failure: `pausebg_per_session` never rises
against its own trailing baseline during the decline (0.526 during the rise, 0.595 during the
decline — it moves with load, not against the baseline). The delivered day contains no gradual
mid-asset audience-loss episode to test against. **The rule is shipped unproven.** Per the brief, we
report that rather than lowering thresholds until something lights up.

**What we would need to validate it:** a day containing an asset whose concurrency decays gradually
mid-run while its viewers stay connected. That is a plausible thing for the unseen day to contain,
and the rule is written to be checkable against it in one command.

## 5. Where it lives, and why it is not in `sql/`

The detector is **raw SQL in HyperDX dashboard tiles**, not a `CREATE VIEW`, because the graded
database `sonyliv` is read-only to us — it has been corrupted twice by stray writes, and this task
adds no write path to it. Everything lives in the ClickStack control plane and reads the same serving
views the other dashboards read (`v_cc_minute_series_total`, `v_cc_watermark`, `ev_raw`). On a
deployment we owned, the same SQL would be `sql/95_decline.sql` and the tiles would be plain builder
tiles over it; nothing about the model changes.

### The watermark anchor — why an alert on a frozen dataset is not a contradiction

[CLICKSTACK.md](CLICKSTACK.md) used to say *"No alerts, deliberately: the dataset is frozen, so a
threshold alert either never fires or fires forever."* That is true only of an alert anchored to
`now()`. Every window here is anchored to **`v_cc_watermark.sealed_watermark`** — the newest minute
the serving layer has actually sealed. On the frozen file that is `2026-07-26 11:32` and the alert
evaluates the real decline; on a live stream it tracks ingestion. **The watermark is the correct
anchor either way**, because "is concurrency falling?" is a question about the data's own clock, not
the operator's. As a side effect the alert also degrades usefully: if ingestion stalls, the window
stops advancing rather than silently sliding onto empty minutes and reporting all-clear.

### What is provisioned

`tools/clickstack-alerts.sh` — idempotent, converges the remote to the file, same pattern as
`tools/clickstack-cloud.sh`:

| | |
|---|---|
| dashboard | **SonyLIV concurrency decline** — 7 tiles: caption, the curve vs its baseline, four class counters, and a detail table showing the evidence behind every verdict |
| alerts | **SYSTEM ISSUE (page)** 5 min / 2 consecutive windows · **CONTENT NOT ENGAGING** 15 min · **UNCLASSIFIED** 15 min |
| webhook | `SonyLIV decline sink` — defaults to a documentation-reserved host that discards the payload. Set `DECLINE_WEBHOOK_URL` to deliver to Slack/PagerDuty for real |

> **A `WEBHOOK_ERROR` on every firing alert is expected with the default sink and is not a fault.**
> The default destination discards the payload by design, so delivery fails by design — we did not
> want a hackathon artifact posting to anyone's inbox or to a third-party collector. It does not
> affect evaluation: the alert still queries, still transitions state, and that state is what
> `--verify` reads back. Point `DECLINE_WEBHOOK_URL` at a real destination and the error clears.

Three alerts rather than one, because the three causes have completely different responses and
collapsing them into one notification throws away the entire point of the classifier. **Only the
system-issue one is a page**, and it requires two consecutive windows: one minute of unexplained
decline is noise, two is a trend. There is deliberately **no alert on ENDING** — the whole argument of
this document is that you must not page someone because an asset finished.

```bash
tools/clickstack-alerts.sh             # provision (idempotent)
tools/clickstack-alerts.sh --validate  # regenerate every number in this doc, read-only
tools/clickstack-alerts.sh --verify    # read the alerts back, signed-in
```

### The bug this found — an alert that fired permanently while its tile read zero

The first provisioned version put both the CONTENT-NOT-ENGAGING and UNCLASSIFIED alerts into
`state=ALERT` while their tiles demonstrably returned **0**
([`evidence/alerting/clickstack-alerts-BEFORE-having-fix.txt`](../evidence/alerting/clickstack-alerts-BEFORE-having-fix.txt)).
Two permanently-quiet alerts fired permanently — precisely the always-on alarm this document exists
to prevent, shipped by the document's own author.

**We did not prove which of two mechanisms caused it**, and would rather say so than write a
confident wrong sentence:

1. **`above` is inclusive.** The API's enum separately offers `above_exclusive`, which strongly
   implies `above` means `>=` — and `0 >= 0` fires.
2. **The engine trips on a row existing.** A bare aggregate with no `GROUP BY` always returns exactly
   one row, whatever its value.

Distinguishing them would mean deliberately mis-provisioning a live alert to watch it fail, so the
fix closes both doors instead:

- the alerting tiles carry **`HAVING <count> > 0`** and return **zero rows when healthy** — no row to
  count, and no value to compare;
- the alerts use **`above_exclusive`**, which states "fire when count > 0" in the API's own
  vocabulary rather than relying on how it reads `above`.

The visible cost is that a healthy alerting tile renders blank rather than `0`; the dashboard caption
says so. The ASSET-ENDED tile keeps its bare count precisely because nothing alerts on it.

**The fix was verified by watching the state change, not by re-reading the config.** Both 15-minute
alerts re-evaluated at `2026-08-01T21:45:03Z` and cleared to `OK`, while the 5-minute page
re-evaluated and *stayed* `ALERT` because its tile genuinely reads 3 outage minutes — so the fix
silenced the false alarms without silencing the real one. Before and after are committed side by side
in [`evidence/alerting/`](../evidence/alerting/).

**The lesson worth keeping:** a green `HTTP 200` from the alerts API proves the alert was *created*,
not that it *works*. Only reading the state back and comparing it against the tile's own value caught
this — which is why `--verify` prints alert state and tile inventory side by side, and why it is a
documented step rather than a thing you remember to do.

## 6. Where the LLM fits — a deliberate "nowhere in the detection path"

The statement offers this as an *"LLM & ClickStack use-case"*, and also says LLM layers *"will not
rescue a slow or wrong concurrency model."* Both are true here, and the honest answer is that **an
LLM adds nothing to detection or classification, and we did not put one there.**

Everything above is a comparison of counts against measured rates. It is deterministic, it is
auditable line by line in `--validate`, it costs one ClickHouse query per evaluation, and it is
correct or incorrect in a way you can *prove*. An LLM in that path would be slower, non-deterministic,
unauditable, and would fail in the one way an alerting system must never fail: plausibly. When the
question is *"is `end_coverage` above 0.7"*, a model that answers "probably" is strictly worse than
`>=`.

**Where an LLM would genuinely earn its place is explanation, and we did not build it.** The classifier
emits `OUTAGE, 3 minutes, end_coverage 0.03, hb_per_session 0.07`. What an on-call engineer at 3 a.m.
actually needs is *"concurrency fell 88% over three minutes; almost none of the departures are
explained by session closes and heartbeats have stopped entirely, which is an ingestion failure rather
than the audience leaving — the last comparable pattern was the 11:30 data cliff."* That is a
translation task with a deterministic, already-verified input, which is the shape of problem LLMs are
actually good at, and the failure mode is a badly-worded sentence rather than a missed outage.

We did not build it, for a reason we would rather state than disguise: it is a genuine improvement to
the alert's *ergonomics* and no improvement at all to its *correctness*, and correctness is scoring
criterion #1. It is scoped in [TODOS.md](../TODOS.md). If it is built, the right shape is to feed the
already-classified row into the LLM and let it write prose — **never** to let it decide the class,
because then the alert's correctness becomes a function of a sampling temperature.

## 7. Honest limits

1. **Disengagement is unproven.** Implemented, never observed in the delivered file (§4). Do not
   claim it works.
2. **The only outage-shaped episode is the file's own truncation.** Signal-identical to an ingestion
   failure, and correctly classified as one, but not a validated *playback* outage (§4).
3. **No seasonal baseline.** A trailing median under-reacts to a scheduled daily ramp-down. The
   delivered file has no daily seasonality to fit one against (§2).
4. **Thresholds are validated against one episode, and they are fitted to it.** 17 ending minutes and
   11 outage minutes from a single day. The margins are wide — 46× between the classes — but the
   sample is one event, and the claim that the thresholds were derived from ADR 0007's measured rates
   rather than fitted to this gap was **false and is withdrawn** (§3.1). The recommended
   `hb_per_session` threshold of **0.5** is not applied; the shipped value is still **1.0**.
5. **`end_coverage` is not a share.** It exceeds 1.0 on 81 of 6,195 minutes and reaches 3.0, so the
   documented reading "1.0 = every departure accounted for" does not hold (§3.1).
6. **Cost is bounded but not small on this file.** The 120-minute lookback reads ~6.3 MiB / ~21 ms,
   which is ~89% of `ev_raw` — because the file *is* a two-hour live spike. On a day with events
   spread evenly the same predicate reads 2h of 24h. It looks like a full scan; it is not one.
7. **The three-way split is the statement's taxonomy, not an exhaustive one.** A CDN failure in one
   region, a paywall bug, or a client-version regression would each present as `UNCLASSIFIED` — which
   is the correct behaviour, and also an admission that the taxonomy has only three boxes.
