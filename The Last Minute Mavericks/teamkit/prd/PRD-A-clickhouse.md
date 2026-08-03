# PRD-A — ClickHouse / `sql/` (the analytical engine)

**Owner:** A · **Directory:** `sql/` · **Consumes:** nothing (you are the source) ·
**Produces:** every computed number, each with a ClickHouse `query_id`.

## Mission
25% of the score is "is ClickHouse genuinely central." Your job makes it yes: **all** detection,
decomposition, attribution, and verification are SQL over a pre-aggregated cube. The LLM does zero
arithmetic. Success = the pipeline reproduces the 4 seen incidents (`prd/README.md`) with the
numbers in `docs/DATA.md`.

## Deliverables (files in `sql/`, referencing `CONTRACTS.md`)
| File | Implements | Contract |
|---|---|---|
| `01_schema.sql` | DDL + **schema-tolerant loader**; date-range branch (continuation→append, overlap→separate DB) | §1 |
| `01_cube.sql` | `AggregatingMergeTree` MV, **sums only**, ratios `sum/sum` at read time | §2 |
| `02_detect.sql` | STL-residual baseline + MAD (`1.4826/b_n`, MAD=0 fallback, floors) + the 4 gates | §3 |
| `03_decompose.sql` | LMDI split across requests/fill/eCPM + Shapley cross-check + edge-case guards | §4 |
| `04_attribute.sql` | Counterfactual contribution + **rate/mix split** + purity descent; Adtributor as cross-check | §5, §5.1 |
| `05_verify.sql` | Uniformity gate + exclusion (Simpson's) + verdict state machine | §6, §6.5 |
| `06_ruled_out.sql` | The ruled-out ledger (near-zero factors + cleared hypotheses, with numbers) | §6 |

## Sequence (timeboxed)
1. **Load + validate (15m).** `count()=9,000,000`; dates Jun 1–Jul 5; **CTR=1.088%** (`sum(is_click)/sum(is_impression)`, not the `is_click` mean); `NAM` intact; `advertiser_id=''` on unfilled. Any mismatch → stop and fix.
2. **Cube (15m).** Build it; **measure a detection query's wall-clock** and post the real number (that's our "~4s" claim — benchmark, don't assert).
3. **Detection (30m).** Baseline + MAD + gates. Emit candidates across the key metrics (revenue, requests, fill_rate, render_rate, ctr, eCPM) — not revenue only.
4. **Reproduce the 4 (20m) — the gate to "real".** Confirm INC-A..D land with the right segments and numbers, and iPhone 14 is subordinated as a dilution artifact. Commit this as a checked-in query with expected results.
5. **Decompose → attribute → verify.** Layer them; each must keep the 4-incident test green.

## Acceptance criteria
- [ ] All 4 incidents reproduced with `docs/DATA.md` numbers; artifacts subordinated
- [ ] INC-A returns `GLOBAL_UNLOCALIZED` (no fabricated culprit); INC-D returns the 2-D cell, not a parent
- [ ] Every query is parameterized (metric, window) and returns its `query_id` for the evidence store
- [ ] Detection query wall-clock measured and posted in `DECISIONS.md`

## Landmines specific to you
- **STL isn't native in ClickHouse.** Implement it in SQL: seasonal = median by `(hour-of-day, day-of-week)`, trend = moving avg, residual = observed − seasonal − trend, MAD on residuals. Flag in `DECISIONS.md` if this diverges from C's simulation.
- **sum/sum, never avg-of-ratios** (rollups break otherwise).
- **Metric-aware dims:** fill_rate/requests attributed by request-side dims only — never advertiser `vertical`/`campaign_type` (empty on unfilled).
- **MAD=0 / contamination:** apply the fallback chain and exclude prior incident windows from baselines, or the emptiest segments rank as top causes.

## Handoff
The moment the cube + detection are stable, help B swap the fixture for live SQL in `run_incident.py`.
