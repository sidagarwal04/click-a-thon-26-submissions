# BUSINESS_RULES — which sessions count, and who loses money when we get it wrong

> **Summary:** The commercial reading of the concurrency model. **Part 1** is the inclusion ledger —
> every state a session can be in, whether it counts, and why in business terms. **Part 2** prices
> being wrong in *both* directions: over-counting sells impressions to players nobody is looking at
> (21.3% of the naive peak, 33.6% of apparent watch time), under-counting is inventory never sold and
> capacity never provisioned. **Part 3** maps each commercial decision to the tier that answers it and
> says whether peak or average is the right statistic. **Part 4** answers "would you bill on this?" —
> yes, with one convention written into the contract first. Every figure was re-measured live on
> 2026-08-02 or is cited to a file; the workings are in [evidence/business/](../evidence/business/README.md).

**Verified:** 2026-08-02, read-only against the graded `sonyliv` database (ClickHouse Cloud
26.2.1.525) after the rebuild that closed the promotion incident. Headline reproduces exactly:
**1,978.1 h counted against 2,976.9 h naive (33.6% excluded); peak 2,917 against a naive 3,708.**

> **Second pass, same day (Codex 005 §5.1).** Every figure in this document was then re-measured
> line by line rather than re-read. **The headline, the CPM arithmetic, the waterfall, the ledger
> counts, the grain split and the serving latencies all held.** Six statements did not and are
> corrected in place: the share of `VideoSessionEnd` runs that actually collect tail (**7,454 of
> 10,758**, not all of them), the peak cost of that tail (**−3.9%**, not −4.8%), the count of runs
> forfeiting tail (**5,794 / 39.2%**, not 5,699 / 38.6%), the sessions emitting events after their
> own end (**111 / 1.0%**, not 239 / 2.2%), the raw pause-window total (**834.1 h**, not 816.1 h),
> and `VideoError`'s effect on liveness (**1 run**, not 2 gaps). Part 3's decline-alerting row was
> stale — that consumer is now built. Workings:
> [evidence/business/](../evidence/business/README.md).

> ⚠️ Do **not** quote `evidence/reconcile.txt` for headline numbers. That file is the *failing* gate
> run committed as the record of the 2026-08-02 corruption (`1760.2` hours, 970 minutes mismatched)
> and has not been regenerated since the rebuild. The live database is correct; that file is not.

---

## Part 1 · The inclusion ledger

What the model actually does, from `sql/30_build_intervals.sql`. **Active = a run of events with no
gap over 150 s, minus explicit pause windows, plus 60 s of tail credit at each run's end.** Rows
marked **policy** are choices we made, not facts the data settled — each points at its dossier.

| State | Counts? | Business reasoning |
|---|:---:|---|
| **Playing, foreground, heartbeating** | **yes** | The viewer you sold the impression to. Nothing else in this table is more defensible. |
| **Paused** (heartbeats continue) | **no** | A paused player renders no frames — an impression served against it cannot be seen. Heartbeats *survive* a pause (0.756/min, one every ~79 s), so a gap rule alone would never catch this and would book it as watching. Excluding it explicitly is the single most valuable rule we have: **286.2 h net**, and it is why the model needs two signals rather than one (ADR 0007). |
| **Backgrounded** (heartbeats stop) | **no** | The app is not on screen. Detected by the 150 s gap — beats drop 100× when backgrounded (4.72/min → 0.047/min), so the silence is unambiguous. **862.2 h**, the largest single exclusion. ⚠️ *policy*: the run still earns 60 s of tail before closing, and 3,634 runs' final second contains an `AppBackgrounded`, so roughly a minute of known-background time is booked per such run — [doubts/11](../doubts/11-liveness-allow-list-unknown-events.md), [doubts/12](../doubts/12-explicit-background-events.md). |
| **Buffering / seeking** | **yes** | Buffering is the platform failing the viewer, not the viewer leaving. Excluding it would let a CDN incident *reduce* reported audience — the dashboard would go quiet exactly when it should be screaming. ⚠️ *policy*: the fail-closed reading excludes it and costs −10.7% of peak — [doubts/10](../doubts/10-fail-closed-state-gates.md). |
| **Ad break playing** | **yes** | The break *is* the inventory being consumed; a model that stopped the clock during ads could not measure ad delivery at all. Correct — but correct by **exact lowercase string match** on `pause`/`resume`, so `AdPause` (45) and `AdResume` (27) are deliberately not matched. A vocabulary change on the unseen day breaks this silently. |
| **Errored** (`VideoError`) | **yes**, while events keep arriving | A viewer sitting through an error is still present and still owed a working stream. One who abandons goes silent, and the 150 s gap closes them within a minute. Self-correcting and cheap — deleting **every** `VideoError` row from the file changes the run count by exactly **one** (14,954 → 14,955), so it is very nearly inert for liveness. |
| **Ended, later events arrive** | run closes, later events open a **new** interval | "Ended" is a client's claim, not a fact — **111 sessions (1.0%)** emit **740** events after their own `VideoSessionEnd`, up to 2,081 s later. Treating the claim as final would discard real watch time. ⚠️ *policy*: **71.9% of runs (10,758)** end at a `VideoSessionEnd`, and **7,454 of them (69.3%) collect 60 s of tail** we know was not watched; the other **3,304 collect none**, because their final segment closes at an unresumed pause rather than at the run end — [doubts/07](../doubts/07-tail-credit-at-explicit-stops.md), worth **−3.9%** of peak (2,917 → 2,804). |
| **Open at file end** | **would count**, `is_open = 1` | Live dashboards are mostly made of these — a model that waits for a session to close under-reports the present minute, which is the only minute an operations team cares about. ⚠️ **Zero of 10,866 sessions are open on the graded file**; every one carries a `VideoSessionEnd`. The path that matters most for a live dashboard is exercised by **no row of the graded data**. |
| **Single lone event / zero-span run** | **no — counts zero** | A viewer who demonstrably acted is billed as nothing. **182 runs across 175 sessions** collapse to a single truncated second and are dropped by `arrayFilter(x -> x.2 > x.1, …)`; 75 are literally one event, the other 107 are several events inside one second. Keeping them moves peak **2,917 → 2,927** and adds 5.0 h ([evidence/property](../evidence/property/README.md)). A small, real under-count — ours to fix or defend, not a mentor question. |
| **Unknown / new event type** | **yes — fails OPEN** | Any `(event_type, event)` pair we have never seen renews liveness and can earn tail credit. **This is the one row where our default is the risky one**: a chatty non-playback event on the unseen day would inflate the number, and no gate would notice, because `90_reconcile.sql` shares the model's vocabulary. Bounded at −1.3% on *this* file, unbounded on the next — [doubts/11](../doubts/11-liveness-allow-list-unknown-events.md). |

**Where the 998.8 excluded hours actually go** — measured by replicating the whole derivation from raw
events, which reproduces the live total to the decimal:

```
  naive session span                                    2,976.9 h
  − silence gaps > 150 s   (backgrounded or gone)         −862.2
  + tail credit            (60 s × 8,978 segments)        +149.6
  − pause windows          (explicit, net of silence)     −286.2
  = counted watch time                                  1,978.1 h ✓
```

Three things a commercial reader should take from that. **7.6% of what we count is tail credit** —
grace after the last observed event, not observed watching. **39.2% of runs forfeit even that**:
**5,794 of 14,772** end inside a pause that never resumed, and the tail is only ever paid to a segment
that runs to the end of its run, so those get nothing. And the pause rule's *net* contribution is
286.2 h, not the **834.1 h** of raw pause windows (21,068 closed `pause`→`resume` pairs), because most
paused time overlaps silence the gap rule had already removed — we are not double-counting the
exclusions. That 286.2 h independently matches a figure already recorded in
`sql/30_build_intervals.sql`'s own comments, and the 834.1 h matches
[ADR 0007](adr/0007-gate-answers-pause-needs-explicit-handling.md)'s paused-time total to the decimal.

> The 834.1 h figure supersedes the **816.1 h** this document previously carried.
> [doubts/02](../doubts/02-resume-semantics.md) measured 816.1 h over 21,216 windows against the
> `csv_audit.raw_str` staging table; re-run against the graded `ev_raw` the same Rule A returns
> **834.1 h over 21,068 windows**. Both are "Rule A"; they differ because the source tables do. The
> graded-database figure is the one a reader can reproduce, so it is the one quoted here.

---

## Part 2 · The cost of being wrong, in both directions

### Over-counting — the naive number

At the peak minute the naive session-span count reports **3,708** viewers where **2,917** were
actually watching. **791 phantom viewers, 21.3% of the reported number.** Across the file, **33.6% of
apparent watch time** is backgrounded or paused.

Converting that to something a yield team recognises. **Assumptions, stated in the open so you can
substitute your own:** an ad load of **4 minutes per content-hour at 30-second spots = 8 impressions
per viewer-hour**, and an illustrative **₹200 CPM**. Neither is a SonyLIV figure; both are mainstream
premium-video planning numbers, and the arithmetic below is linear in each.

> **For every 1,000 concurrent viewers the naive count reports, 213 are not watching.**
> At 8 impressions per viewer-hour that is **1,704 phantom impressions per hour, per 1,000 reported
> concurrent viewers** — about **₹341/hour per 1,000** at a ₹200 CPM.
>
> Scale it yourself: at 1,000,000 reported concurrent — a level Indian live sport reaches — the same
> arithmetic gives **~1.7 million phantom impressions per hour, ≈ ₹3.4 lakh/hour**. The rate is the
> finding; the absolute is illustration, because our sample is 10,866 sessions.

**The impression revenue is not the expensive part.** The expensive part is what happens when a
third-party measurement disagrees with your own dashboard by 21% at peak: make-goods on the
shortfall, re-negotiated rates on the next flight, and an advertiser who now discounts every number
you publish. That asymmetry — cheap to be caught, expensive to be distrusted — is exactly why the
**IAB/MRC viewability standard** exists. We do not implement viewability: we have no viewport or
audibility signal, and it is a different measurement at a different layer. But foreground-only
concurrency is the same principle applied where we *do* have signal — do not claim an audience for a
surface nobody is looking at.

### Under-counting — not free either

Excluded time we should have counted is **inventory that was never sold and capacity that was
under-provisioned**. Honest accounting of what we may be losing:

| Where we may be under-counting | Cost if we are wrong | Status |
|---|---|---|
| **Point activity dropped** — 182 zero-span runs count zero | peak 2,917 → **2,927 (+10)**, +5.0 h | measured, [evidence/property](../evidence/property/README.md). Small, but it is the *shape* of the risk: a viewer who demonstrably acted is billed as nothing. |
| **Conservative unclosed-pause rule** — 23% of pauses never resume, and we exclude to the run's end | up to +4.5% peak, +99.3 h | ADR 0007. ⚠️ **measured before ADR 0009 and not re-run** — treat the size as indicative, not current. |

Against that, the risks that push the *other* way are much larger: if judges sample at the
instant a minute begins rather than counting any overlap, we are **14.1% high**
([doubts/09](../doubts/09-minute-membership-instant-reading.md)); if it requires foreground **and**
playing to both hold, we are **10.7% high** ([doubts/10](../doubts/10-fail-closed-state-gates.md)).

**The exposure is asymmetric, and it should be stated that way**: our known under-counts are worth
tenths of a percent, our open definitional forks are worth double digits. We are far more likely to
be over-counting than under-counting, and we are choosing to say so.

### The direction of a safe error is not the same for every decision

This is the part that gets missed. **For capacity, over-counting is safe** — you over-provision and
waste money, rather than dropping streams at peak. **For billing, over-counting is dangerous** — you
over-deliver on paper, then owe make-goods. The two decisions want their errors in *opposite*
directions, so no single "conservative" choice serves both. That is the argument for stating the
convention per decision rather than picking one global safety margin.

---

## Part 3 · Which decisions actually consume this

| Decision | Tier that answers it | Grain | Latency | Peak or average? |
|---|---|---|---|---|
| **Ad load / yield** | `cc_minute_delta` (all 7 raw dimensions) | minute | **7.0–7.5 ms** (`b06`, `b07`) | **Average.** Inventory is time-integrated — how many impressions exist over a break, not the single highest instant. Peak matters only for guaranteed-delivery roadblocks, where you are selling a moment. |
| **Capacity / CDN** | `cc_hour_agg` (`peak` and `integral`) | hour → day | **12.2–44.5 ms** (`b05`, `b01`) | **Both, for different things.** Provision on **peak** — that is the moment that breaks. Bill and forecast egress cost on the **average** (the integral). Getting these backwards is the classic and expensive mistake: peak is **2.67× the average within the very hour it occurs**, so provisioning on the average under-provisions by 63% at peak, and billing on the peak over-bills by 2.67×. |
| **Content calls** (commissioning, licensing) | `cc_hour_agg` content cube + `dict_content` | title, hour | **14.3 ms** (`b13`) | **Average**, weighted by duration — a title that holds 500 viewers for two hours is worth more than one that spikes to 2,000 for four minutes. Peak is a launch-spike diagnostic, not a value measure. |
| **Anomaly response** (decline alerting) | `v_cc_minute_series_total` + `v_cc_watermark` | 1 min, 15-min trailing window | not benchmarked; the 120-min lookback reads ~6.3 MiB / ~21 ms | **Neither.** A decline alert reads the **shape**, not the level: concurrent against a **15-minute trailing median, lagged 3 minutes**, floored at 100 concurrent and 50 sessions. A drop from 2,900 to 2,400 is catastrophic mid-match and completely normal at the final whistle. **Built and live** — 3 HyperDX alerts over 7 tiles, 28 firing minutes on the delivered file where a naive rate-of-change detector fires 962: [DECLINE_ALERTING.md](DECLINE_ALERTING.md). Note it explicitly **rejects** same-time-yesterday as a baseline — the delivered file is one live event, not a repeating daily pattern. Its classifier thresholds are **fitted, not semantically anchored** (§3.1 there), and its DISENGAGEMENT class is shipped **unvalidated**. |

**Two caveats a buyer of this data should hear.** First, **freshness**: incremental publication is
proven byte-identical to a rebuild in a scratch database (ADR 0013/0016), but on the **graded**
database the publisher has never committed a run — every live number there comes from a batch
rebuild. Do not promise sub-minute freshness on that service today. Second, **dimension coverage is
not uniform**: `cc_minute_delta` carries all seven raw dimensions, but the hour/day, user, window and
stateless tiers carry only platform, country and content_id. "Day peak by app version" or "user
concurrency by audio language" needs custom SQL over the delta table, not a shipped serving shape.

---

## Part 4 · Would you bill on this number?

**Yes — with the minute-membership convention written into the contract, and one question we would
want the advertiser to agree to first.**

Two things are true at once, and a mature answer holds them together rather than choosing one.

**What we can prove.** The gate recomputes truth directly from raw events and compares **every minute
in the data — 17,028 of them, idle minutes included — with zero mismatches and a maximum absolute
difference of zero**, and it has been negative-tested to confirm it can actually fail. That was
**re-run read-only against the graded database on 2026-08-02 for this document**, not cited: the
serving layer is exactly the truth recomputed from `ev_raw`, and nothing between the events and the
invoice is approximating.

**What the gate cannot prove.** It recomputes truth using *our* definitions. A wrong shared convention
goes green on both sides by construction. The largest one is
[doubts/09](../doubts/09-minute-membership-instant-reading.md): we count a session at minute M if it
was active for **any part** of M; a sampled gauge would count it only if it was active **at the
instant M began**. Those two readings differ by **410 viewers — 14.1% — at the graded peak**, and
every internal check we have passes under either.

So the answer we would give an advertiser is:

> *"We would bill on this, and the definition goes in the contract: a viewer is concurrent at a given
> minute if they were actively watching — foreground, not paused — for any part of that minute. Under
> that definition we can reconstruct any minute from raw events and prove the number, and we have,
> across every minute in the data. The one thing we want you to agree before signing is that
> definition itself, because the alternative reading — sampling once at the top of each minute — is
> 14% lower and equally defensible. We would rather agree it now than discover it in a
> reconciliation."*

**And one more line belongs in the contract**, because we found it in the numbers rather than the
docs: **state the grain of "hours delivered".** The same pipeline reports **1,978.1 hours** at second
grain (the headline) and **2,338.4 hours** at the minute grain its own serving layer uses to compute
average concurrency — **18.2% apart**, both correct, answering different questions. Every benchmark
answer's `avg_concurrent` is derived from the larger one. A buyer who multiplies our average
concurrency by elapsed time and a buyer who quotes our headline hours will not reconcile, and until
now nothing in this repo explained why. They now differ by a stated convention rather than a surprise.

---

**Sources.** Live re-measurement, queries and outputs:
[evidence/business/](../evidence/business/README.md). Model: `sql/30_build_intervals.sql`,
[docs/ARCHITECTURE.md](ARCHITECTURE.md). Open conventions and what each is worth:
[doubts/](../doubts/README.md). Serving cost: [evidence/bench.txt](../evidence/bench.txt).
