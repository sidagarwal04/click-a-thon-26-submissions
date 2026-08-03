# Judge-Facing Investigation Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure Langfuse tracing so a judge opens one trace and reads the investigation as a story — phases (detect → decompose → drill-with-decisions → ruled-out → narrate), named SQL spans, verdict outputs, trace-list scores — with orphan dev-query noise eliminated.

**Architecture:** A `phase()` context manager in `narrator/tracing.py` opens nested Langfuse spans via the existing OTEL context (so `run_query` spans nest under the innermost phase automatically). `run_query` and `phase()` both no-op outside an active trace, which kills orphan traces at the source. `pipeline.py` stamps trace-level tags/output/scores. Spec: `docs/superpowers/specs/2026-08-02-judge-facing-tracing-design.md`.

**Tech Stack:** Python 3.11, Langfuse SDK 4.x (v4 APIs verified on 4.14.2: `get_current_trace_id`, `score_current_trace(name, value, data_type)`, `set_current_trace_io(input, output)`, `propagate_attributes(tags=...)`, `span.update(...)`), pytest, FastAPI.

## Global Constraints

- Config-driven, no magic strings: new knobs go in `backend/config.json`; phase names live in one constants map in `tracing.py`.
- Concise code, comments only on non-obvious logic (docs/CODING_STANDARDS.md rules 7 & 8).
- All work under `backend/`; run commands from `backend/` with `./.venv/Scripts/python.exe`.
- Tracing must degrade to a no-op when Langfuse keys are unset AND when no trace is active — library code never crashes or emits orphans.
- Tests must not require a live Langfuse or ClickHouse.
- Commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- The repo working tree has unrelated staged changes — commit ONLY the files each task names (use explicit `git add <paths>` then `git commit -- <paths>`... plain `git commit` after `git add` of only your files is fine as long as you `git restore --staged` nothing; verify with `git status` before committing that only your files are staged for the commit pathspec).

---

### Task 1: `phase()` context manager + config knob

**Files:**
- Modify: `backend/narrator/tracing.py` (append after `narration_span`)
- Modify: `backend/config.json` (add `tracing` block)
- Test: `backend/tests/test_phase_tracing.py` (create)

**Interfaces:**
- Consumes: `obs.langfuse()` singleton (returns `Langfuse | None`), `config.config()`.
- Produces: `phase(name: str, input: dict | None = None)` context manager yielding a `Phase` object with `.verdict(**kw) -> None` (sets span output) and `.enabled: bool`. `PHASES` dict of canonical phase names: `{"detect": "detect", "decompose": "decompose", "drilldown": "drilldown", "depth": "depth-{depth}:{dim}", "ruled_out": "ruled-out"}`. Later tasks import `from narrator.tracing import phase, PHASES`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_phase_tracing.py`:

```python
"""phase(): nested judge-readable spans. No Langfuse / no active trace => clean no-op."""
from contextlib import contextmanager

import pytest

from narrator import tracing


class FakeSpan:
    def __init__(self, tree, name):
        self.tree, self.name, self.updates = tree, name, []

    def update(self, **kw):
        self.updates.append(kw)


class FakeLangfuse:
    """Minimal v4 surface: records a flat list of (event, payload) in order."""

    def __init__(self, active_trace="trace-1"):
        self.events = []
        self._active = active_trace

    def get_current_trace_id(self):
        return self._active

    @contextmanager
    def start_as_current_observation(self, *, name, as_type):
        span = FakeSpan(self.events, name)
        self.events.append(("open", name, as_type))
        yield span
        self.events.append(("close", name, span.updates))

    def flush(self):
        self.events.append(("flush", None, None))


@pytest.fixture
def fake_lf(monkeypatch):
    lf = FakeLangfuse()
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    return lf


def test_phase_opens_named_span_and_records_verdict(fake_lf):
    with tracing.phase("decompose", input={"metric": "revenue"}) as p:
        p.verdict(primary_factor="fill_rate", decision="descend")

    opens = [e for e in fake_lf.events if e[0] == "open"]
    assert opens == [("open", "decompose", "span")]
    closes = [e for e in fake_lf.events if e[0] == "close"][0]
    updates = closes[2]
    # input recorded at open, verdict recorded as output
    assert {"input": {"metric": "revenue"}} in updates
    assert {"output": {"primary_factor": "fill_rate", "decision": "descend"}} in updates


def test_phase_flushes_on_exit_when_live_flush(fake_lf, monkeypatch):
    monkeypatch.setitem(tracing._TRACING, "live_flush", True)
    with tracing.phase("detect"):
        pass
    assert fake_lf.events[-1] == ("flush", None, None)


def test_phase_no_flush_when_disabled(fake_lf, monkeypatch):
    monkeypatch.setitem(tracing._TRACING, "live_flush", False)
    with tracing.phase("detect"):
        pass
    assert ("flush", None, None) not in fake_lf.events


def test_phase_noop_without_langfuse(monkeypatch):
    monkeypatch.setattr(tracing, "langfuse", lambda: None)
    with tracing.phase("detect") as p:
        p.verdict(anything=1)  # must not raise
    assert p.enabled is False


def test_phase_noop_without_active_trace(monkeypatch):
    lf = FakeLangfuse(active_trace=None)
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    with tracing.phase("detect") as p:
        p.verdict(anything=1)
    assert p.enabled is False
    assert lf.events == []  # no orphan span created
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_phase_tracing.py -q`
Expected: FAIL / ERROR with `AttributeError: module 'narrator.tracing' has no attribute 'phase'` (and `_TRACING`).

- [ ] **Step 3: Add the `tracing` config block**

In `backend/config.json`, add a top-level key (alongside `detection`, `rca`, `bedrock`):

```json
"tracing": {
    "live_flush": true
}
```

- [ ] **Step 4: Implement `phase()` in `narrator/tracing.py`**

Append to `backend/narrator/tracing.py` (and add `from config import config as _config` to the imports; keep the existing `from config import LANGFUSE`):

```python
_TRACING = _config()["tracing"]

# Canonical phase names — the judge-facing vocabulary, defined once.
PHASES = {
    "detect": "detect",
    "decompose": "decompose",
    "drilldown": "drilldown",
    "depth": "depth-{depth}:{dim}",
    "ruled_out": "ruled-out",
}


class Phase:
    """Handle yielded by phase(). verdict() writes the decision (and its numbers) as span output."""

    def __init__(self, span=None):
        self._span = span

    @property
    def enabled(self) -> bool:
        return self._span is not None

    def verdict(self, **kw) -> None:
        if self._span is not None:
            self._span.update(output=kw)


@contextmanager
def phase(name: str, input: dict | None = None):
    """One investigation phase as a nested Langfuse span.

    Nests under the current OTEL context (root trace or an outer phase), so run_query spans
    land inside the innermost phase automatically. No Langfuse client or no ACTIVE trace =>
    inert Phase — the guard that keeps untraced calls (dev console, benchmarks) orphan-free.
    Flushes on exit when tracing.live_flush, so spans appear in the UI mid-investigation.
    """
    lf = langfuse()
    if lf is None or lf.get_current_trace_id() is None:
        yield Phase()
        return

    with lf.start_as_current_observation(name=name, as_type="span") as span:
        if input is not None:
            span.update(input=input)
        try:
            yield Phase(span)
        finally:
            if _TRACING["live_flush"]:
                lf.flush()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_phase_tracing.py -q`
Expected: 5 passed.

- [ ] **Step 6: Run full suite + ruff, then commit**

Run: `./.venv/Scripts/python.exe -m pytest -q tests/test_pipeline.py tests/test_narrate.py -q` (tracing consumers) and `./.venv/Scripts/python.exe -m ruff check narrator/tracing.py tests/test_phase_tracing.py`
Expected: pass / All checks passed.

```bash
git add backend/narrator/tracing.py backend/config.json backend/tests/test_phase_tracing.py
git commit -m "feat(tracing): phase() spans with verdicts, live flush, no-trace guard

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- backend/narrator/tracing.py backend/config.json backend/tests/test_phase_tracing.py
```

---

### Task 2: `run_query` orphan guard

**Files:**
- Modify: `backend/data/client.py:32-58` (`run_query`)
- Test: `backend/tests/test_client.py` (append)

**Interfaces:**
- Consumes: `obs.langfuse()`.
- Produces: unchanged `run_query` signature; new behavior — span created ONLY when `lf.get_current_trace_id()` is not None. Callers unaffected.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_client.py`:

```python
class _SpanRecorder:
    """Fake Langfuse: counts spans; get_current_trace_id switchable."""

    def __init__(self, active):
        self.active, self.spans = active, []

    def get_current_trace_id(self):
        return self.active

    def start_as_current_observation(self, *, name, as_type):
        from contextlib import contextmanager

        @contextmanager
        def cm():
            class S:
                id = "span-1"

                def update(self, **kw):
                    pass

            self.spans.append(name)
            yield S()

        return cm()


def _stub_execute(monkeypatch):
    monkeypatch.setattr(
        ch, "_execute",
        lambda sql, params: {"rows": [], "columns": [], "resolved_sql": sql, "elapsed_ms": 0.0},
    )


def test_run_query_emits_no_span_outside_a_trace(monkeypatch):
    """Dev-console/benchmark queries must not create orphan traces."""
    lf = _SpanRecorder(active=None)
    monkeypatch.setattr(ch, "langfuse", lambda: lf)
    _stub_execute(monkeypatch)

    out = ch.run_query("SELECT 1")

    assert lf.spans == []
    assert "langfuse_span_id" not in out


def test_run_query_spans_inside_a_trace(monkeypatch):
    lf = _SpanRecorder(active="trace-1")
    monkeypatch.setattr(ch, "langfuse", lambda: lf)
    _stub_execute(monkeypatch)

    out = ch.run_query("SELECT 1", name="sql:baseline")

    assert lf.spans == ["sql:baseline"]
    assert out["langfuse_span_id"] == "span-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_client.py -q`
Expected: `test_run_query_emits_no_span_outside_a_trace` FAILS (span created today); the other may pass.

- [ ] **Step 3: Implement the guard**

In `backend/data/client.py`, `run_query`, change the early-exit:

```python
    params = params or {}
    lf = langfuse()
    # Span only inside an active trace: untraced callers (dev console, benchmarker) would
    # otherwise each mint a single-span orphan trace and bury real investigations in the list.
    if lf is None or lf.get_current_trace_id() is None:
        return _execute(sql, params)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_client.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/data/client.py backend/tests/test_client.py
git commit -m "feat(tracing): run_query spans only inside an active trace (kills orphan noise)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- backend/data/client.py backend/tests/test_client.py
```

---

### Task 3: Phase-instrument `build_bundle` + name its SQL

**Files:**
- Modify: `backend/rca/bundle.py` (`build_bundle`, `_window_and_anomaly`, `_metric_over`, `_data_range`, `_ruled_out` call site)
- Test: `backend/tests/test_bundle_tracing.py` (create)

**Interfaces:**
- Consumes: `phase(name, input=None)` / `Phase.verdict(**kw)` from Task 1 (import `from narrator.tracing import phase`).
- Produces: `build_bundle` emits, under the root trace, ordered phases `detect` → `decompose` → `drilldown` → `ruled-out`, each with a verdict output. `drill()`'s own per-depth spans come in Task 4 and nest inside `drilldown`. Bundle content is unchanged.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_bundle_tracing.py`:

```python
"""build_bundle emits the judge-facing phase story. Engine internals are stubbed —
this tests ORCHESTRATION of spans, not the math (the math has its own suites)."""
import pytest

from models import Anomaly, DrilldownNode, Factor, FactorDecomposition, Window
from narrator import tracing
from rca import bundle as bb
from tests.test_phase_tracing import FakeLangfuse


@pytest.fixture
def spans(monkeypatch):
    lf = FakeLangfuse()
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    monkeypatch.setitem(tracing._TRACING, "live_flush", False)
    return lf


@pytest.fixture
def stubbed_engine(monkeypatch):
    from datetime import datetime

    win = Window(start=datetime(2026, 6, 23), end=datetime(2026, 6, 24))
    anomaly = Anomaly(detected=True, observed=90.0, expected=100.0, abs_delta=-10.0,
                      pct_delta=-0.1, score=-4.2, direction="drop")
    monkeypatch.setattr(bb, "_window_and_anomaly", lambda m, t: (win, anomaly, []))
    monkeypatch.setattr(bb, "baseline_window", lambda w: win)
    factors = FactorDecomposition(
        method="log_additive", primary_factor="fill_rate",
        factors=[Factor(factor="fill_rate", contribution_pct=0.9, **{"from": 0.8, "to": 0.6})],
    )
    monkeypatch.setattr(bb, "decompose", lambda m, w, b: (factors, [{"id": "q_d", "sql": "s", "result_summary": {}}]))
    node = DrilldownNode(depth=0, split_dimension="country", segment={"country": "IN"},
                        contribution_pct=0.87, status="culprit", query_id="q_0")
    monkeypatch.setattr(bb, "drill", lambda m, f, w, b: ([node], {"country": "IN"}, []))
    return win


def test_build_bundle_emits_phase_story_in_order(spans, stubbed_engine):
    bb.build_bundle("revenue", stubbed_engine)

    opened = [e[1] for e in spans.events if e[0] == "open"]
    assert opened == ["detect", "decompose", "drilldown", "ruled-out"]


def test_phase_verdicts_carry_the_why(spans, stubbed_engine):
    bb.build_bundle("revenue", stubbed_engine)

    closed = {e[1]: e[2] for e in spans.events if e[0] == "close"}
    detect_out = [u["output"] for u in closed["detect"] if "output" in u][0]
    assert detect_out["score"] == -4.2 and detect_out["direction"] == "drop"
    decomp_out = [u["output"] for u in closed["decompose"] if "output" in u][0]
    assert decomp_out["primary_factor"] == "fill_rate"
    drill_out = [u["output"] for u in closed["drilldown"] if "output" in u][0]
    assert drill_out["localized_segment"] == {"country": "IN"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_bundle_tracing.py -q`
Expected: FAIL — no spans opened (phases not wired).

- [ ] **Step 3: Instrument `build_bundle`**

In `backend/rca/bundle.py`: add `from narrator.tracing import phase` to imports, then rewrite `build_bundle`:

```python
def build_bundle(metric: str, target: Window | None = None) -> EvidenceBundle:
    """Run one investigation into a schema-valid EvidenceBundle (no narrative — that's Lane C).

    Each stage runs inside a phase() span whose verdict records the decision AND the numbers
    that drove it — the trace must read as: what was checked, in what order, and why.
    """
    with phase("detect", input={"metric": metric}) as p:
        window, anomaly, q_detect = _window_and_anomaly(metric, target)
        p.verdict(detected=anomaly.detected, observed=anomaly.observed, expected=anomaly.expected,
                  score=anomaly.score, direction=anomaly.direction,
                  window=[_fmt(window.start), _fmt(window.end)])
    baseline = baseline_window(window)

    with phase("decompose", input={"metric": metric}) as p:
        factors, q_decomp = decompose(metric, window, baseline)
        p.verdict(primary_factor=factors.primary_factor,
                  factors={f.factor: f.contribution_pct for f in factors.factors})
    # Revenue investigations drill the factor that moved; a direct-metric investigation drills itself.
    factor = factors.primary_factor if metric == "revenue" else metric

    with phase("drilldown", input={"factor": factor}) as p:
        path, localized, q_drill = drill(metric, factor, window, baseline)
        p.verdict(localized_segment=localized, depth=len(path),
                  culprit_contribution_pct=path[-1].contribution_pct if path else None)

    with phase("ruled-out") as p:
        ruled = _ruled_out(factors, q_decomp[0]["id"])
        p.verdict(cleared={r.hypothesis: r.evidence for r in ruled})

    return EvidenceBundle(
        investigation_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        metric=metric,
        target_window=window,
        baseline_window=BaselineWindow(
            method="same_weekday_trailing_weeks",
            description=f"same window shifted back {_RCA['baseline_weeks']} weeks (weekday-aligned)",
            weeks=_RCA["baseline_weeks"],
        ),
        anomaly=anomaly,
        factor_decomposition=factors,
        drilldown=path,
        localized_segment=localized,
        ruled_out=ruled,
        queries=[*q_detect, *q_decomp, *q_drill],
    )
```

Also name this file's SQL spans:
- `_data_range`: add `name="sql:data-range"` to its `run_query(...)` call.
- `_metric_over`: `res = run_query(sql, {...}, name=f"sql:window-metric:{metric}")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_bundle_tracing.py tests/test_build_bundle.py tests/test_bundle.py -q`
Expected: all pass (existing bundle suites confirm content unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/rca/bundle.py backend/tests/test_bundle_tracing.py
git commit -m "feat(tracing): phase spans + verdicts around build_bundle stages

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- backend/rca/bundle.py backend/tests/test_bundle_tracing.py
```

---

### Task 4: Per-depth drill spans with descend/stop decisions + name remaining SQL

**Files:**
- Modify: `backend/rca/drilldown.py` (`drill`, `_pop`, `_by_dim`)
- Modify: `backend/rca/decomposition.py:95` (name its `run_query`)
- Test: `backend/tests/test_drilldown_tracing.py` (create)

**Interfaces:**
- Consumes: `phase()` from Task 1. `_pop`/`_by_dim` gain a `depth: int` param for span naming — internal to this module.
- Produces: inside the Task-3 `drilldown` phase, one span per recursion level named `depth-{N}:{dim}` (winner known) or `depth-{N}:stop` with output = the descend/stop decision. SQL spans named `sql:population:{depth}` / `sql:contribution:{dim}` / `sql:factor-sums`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_drilldown_tracing.py`:

```python
"""drill() emits one span per depth whose output is the descend/stop decision."""
import pytest

from narrator import tracing
from rca import drilldown as dd
from tests.test_phase_tracing import FakeLangfuse


@pytest.fixture
def spans(monkeypatch):
    lf = FakeLangfuse()
    monkeypatch.setattr(tracing, "langfuse", lambda: lf)
    monkeypatch.setitem(tracing._TRACING, "live_flush", False)
    return lf


@pytest.fixture
def two_level_engine(monkeypatch):
    """Stub the SQL layer: depth 0 finds country=IN (87%, lift 3.0); depth 1 finds nothing."""
    pops = {0: ({"revenue": 90.0}, {"revenue": 100.0}), 1: ({"revenue": 9.0}, {"revenue": 20.0})}
    monkeypatch.setattr(dd, "_pop", lambda w, p, depth: (*pops[depth], "SQL"))
    monkeypatch.setattr(dd, "measure_natural_noise", lambda f: 0.001)

    def by_dim(dim, w, p, depth):
        if depth == 0 and dim == "country":
            return [("IN", {"revenue": 9.0}, {"revenue": 20.0})], "SQL"
        return [], "SQL"

    monkeypatch.setattr(dd, "_by_dim", by_dim)
    monkeypatch.setattr(dd, "_score", lambda f, po, pe, so, se: (0.87, 3.0))
    monkeypatch.setattr(dd, "_metric_from_sums", lambda f, s: s.get("revenue", 0.0))
    return pops


def test_each_depth_gets_a_decision_span(spans, two_level_engine):
    from datetime import datetime

    from models import Window

    w = Window(start=datetime(2026, 6, 23), end=datetime(2026, 6, 24))
    dd.drill("revenue", "revenue", w, w)

    opened = [e[1] for e in spans.events if e[0] == "open"]
    assert opened[0] == "depth-0:country"
    assert opened[1] == "depth-1:stop"

    closed = {e[1]: e[2] for e in spans.events if e[0] == "close"}
    d0 = [u["output"] for u in closed["depth-0:country"] if "output" in u][0]
    assert d0["decision"] == "descend" and d0["winner"] == {"country": "IN"}
    assert d0["contribution_pct"] == 0.87 and d0["lift"] == 3.0
    d1 = [u["output"] for u in closed["depth-1:stop"] if "output" in u][0]
    assert d1["decision"] == "stop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_drilldown_tracing.py -q`
Expected: FAIL (TypeError on `_pop`/`_by_dim` arity or no spans).

- [ ] **Step 3: Implement per-depth spans**

In `backend/rca/drilldown.py`: add `from narrator.tracing import phase` to imports. Give the SQL helpers a `depth` param for naming:

```python
def _pop(where_sql: str, params: dict, depth: int) -> tuple[dict, dict, str]:
    sql = f"SELECT {_sum_cols()} FROM {_HOURLY} WHERE ({_TGT} OR {_BASE}){where_sql}"
    res = run_query(sql, params, name=f"sql:population:{depth}")
    obs, exp = _split(res["rows"][0], 0)  # equal-length windows -> baseline sums ARE the expectation
    return obs, exp, res["resolved_sql"]


def _by_dim(dim: str, where_sql: str, params: dict, depth: int) -> tuple[list, str]:
    sql = f"SELECT {dim} AS seg, {_sum_cols()} FROM {_HOURLY} WHERE ({_TGT} OR {_BASE}){where_sql} GROUP BY {dim}"
    res = run_query(sql, params, name=f"sql:contribution:{dim}")
    out = [(row[0], *_split(row, 1)) for row in res["rows"]]
    return out, res["resolved_sql"]
```

Then restructure the body of `drill()`'s `for depth in range(...)` loop so each iteration runs inside a span and every exit path records its decision. Replace the loop with:

```python
    for depth in range(_RCA["max_depth"]):
        where_sql, wparams = _where(filt)
        params = {**params_base, **wparams}
        pop_obs, pop_exp, pop_sql = _pop(where_sql, params, depth)
        queries.append({"id": f"q_drill_pop_{depth}", "sql": pop_sql,
                        "result_summary": {"filter": dict(filt), "observed": _metric_from_sums(factor, pop_obs)}})

        # Materiality gate: contribution is gap_closed / |total_gap|, so when the population
        # barely moved, |total_gap| ~ 0 and ANY segment's noise "explains" ~100% of it. Without
        # this the drill returns a confident 4-level culprit for a non-event: measured on ecpm
        # Jun 16-18 (a +0.4% move) it produced vertical=auto -> publisher_tier=tier_2 ->
        # region=NAM -> device_model=Redmi Note 12, all on a gap that does not exist.
        #
        # Gate on the gap relative to the metric's OWN natural noise, NOT on an absolute percent
        # floor. A localised anomaly is often small globally while being severe in its segment —
        # that is the entire reason to drill. Measured global gaps: fill_rate Jun 28-30 is only
        # -1.2% (yet APAC/iOS 18.1 inside it is -51%), ecpm Jun 19-22 is -4.2% (finance is -35%).
        # An absolute floor big enough to reject the +0.4% non-event would also reject both of
        # those. Against natural noise they separate cleanly: 3.4x and 7.0x versus 0.7x.
        if depth == 0:
            observed = _metric_from_sums(factor, pop_obs)
            expected = _metric_from_sums(factor, pop_exp)
            gap_pct = safe_div(observed - expected, abs(expected))
            noise = measure_natural_noise(factor)
            floor = (noise or 0.0) * _RCA.get("min_gap_noise_multiple", 2.0)
            if floor and abs(gap_pct) < floor:
                reason = (
                    f"population moved {gap_pct:+.2%}, under {floor:.2%} "
                    f"({_RCA.get('min_gap_noise_multiple', 2.0)}x {factor}'s natural noise of "
                    f"{noise:.2%}) — no material gap to localise"
                )
                queries[-1]["result_summary"]["skipped"] = reason
                with phase(f"depth-{depth}:stop", input={"filter": dict(filt)}) as p:
                    p.verdict(decision="stop", reason=reason)
                break

        best = None  # (contribution, lift, dim, val, seg_obs, seg_exp, sql)
        with phase(f"depth-{depth}", input={"filter": dict(filt), "factor": factor}) as p:
            for dim in (d for d in _RCA["drilldown_dimensions"] if d not in filt):
                rows, sql = _by_dim(dim, where_sql, params, depth)
                for val, seg_obs, seg_exp in rows:
                    if val in ("", None):  # empty dim value = "unknown/unfilled" artifact, never a culprit
                        continue
                    contribution, lift = _score(factor, pop_obs, pop_exp, seg_obs, seg_exp)
                    if contribution >= thr and lift >= min_lift and (best is None or contribution > best[0]):
                        best = (contribution, lift, dim, val, seg_obs, seg_exp, sql)

            if best is None:
                p.rename(f"depth-{depth}:stop")
                p.verdict(decision="stop",
                          reason=f"no segment clears contribution>={thr} and lift>={min_lift}")
                break

            contribution, lift, dim, val, seg_obs, seg_exp, sql = best
            filt = {**filt, dim: val}
            p.rename(f"depth-{depth}:{dim}")
            p.verdict(decision="descend", winner={dim: val},
                      contribution_pct=round(contribution, 4), lift=round(lift, 2))

        queries.append({"id": f"q_drill_{depth}", "sql": sql,
                        "result_summary": {"split": dim, "value": val, "contribution_pct": round(contribution, 4), "lift": round(lift, 2)}})
        path.append(DrilldownNode(
            depth=depth, split_dimension=dim, segment=dict(filt),
            metric_from=_metric_from_sums(factor, seg_exp), metric_to=_metric_from_sums(factor, seg_obs),
            contribution_pct=round(contribution, 4), status="contributor", query_id=f"q_drill_{depth}",
        ))
```

This requires one addition to `Phase` in `narrator/tracing.py` (the winner dim isn't known at span-open time):

```python
    def rename(self, name: str) -> None:
        if self._span is not None:
            self._span.update(name=name)
```

And in the Task-1 test file's `FakeSpan.update`, renames arrive as `{"name": ...}` updates — add to `FakeLangfuse` close handling nothing; instead have the drill test treat the LAST `{"name": ...}` update as the span's final name. Concretely, in `test_drilldown_tracing.py` replace the `opened` assertions with:

```python
    def final_name(close_event):
        names = [u["name"] for u in close_event[2] if "name" in u]
        return names[-1] if names else close_event[1]

    closes = [e for e in spans.events if e[0] == "close"]
    assert final_name(closes[0]) == "depth-0:country"
    assert final_name(closes[1]) == "depth-1:stop"
```

(and key `closed` lookups by `final_name` too — build `closed = {final_name(e): e[2] for e in closes}`).

Note the depth-0 materiality stop uses `phase(f"depth-{depth}:stop")` directly (name known up front), while the search loop opens `depth-{N}` and renames once the outcome is known.

Also in `backend/rca/decomposition.py` line 95, name the factor-sums query:

```python
    res = run_query(sql, params, name="sql:factor-sums")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_drilldown_tracing.py tests/test_drilldown.py tests/test_phase_tracing.py tests/test_decomposition.py -q`
Expected: all pass (existing drill/decompose math suites unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/rca/drilldown.py backend/rca/decomposition.py backend/narrator/tracing.py backend/tests/test_drilldown_tracing.py backend/tests/test_phase_tracing.py
git commit -m "feat(tracing): per-depth drill spans with descend/stop decisions, named SQL

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- backend/rca/drilldown.py backend/rca/decomposition.py backend/narrator/tracing.py backend/tests/test_drilldown_tracing.py backend/tests/test_phase_tracing.py
```

---

### Task 5: Trace-list surfacing — tags, verdict output, scores

**Files:**
- Modify: `backend/narrator/tracing.py` (`investigation_trace` gains tags; new `stamp_trace_verdict`, `score_trace`)
- Modify: `backend/api/pipeline.py` (`run_investigation`, `narrate_investigation`)
- Test: `backend/tests/test_phase_tracing.py` (append), `backend/tests/test_pipeline.py` (no changes — its FakeTrace already absorbs the new calls via `investigation_trace` stubbing; verify green)

**Interfaces:**
- Consumes: bundle fields (`anomaly.score`, `anomaly.detected`, `factor_decomposition.primary_factor`, `localized_segment`, `narrative_verification.passed`).
- Produces: `stamp_trace_verdict(bundle) -> None` (sets root trace output + `anomaly_score` NUMERIC score) and `score_trace(name: str, value, data_type: str) -> None` — both no-op without an active trace. `investigation_trace` passes `tags=[metric]` via `propagate_attributes`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_phase_tracing.py`:

```python
def test_stamp_trace_verdict_sets_output_and_score(fake_lf):
    calls = {}
    fake_lf.set_current_trace_io = lambda **kw: calls.setdefault("io", kw)
    fake_lf.score_current_trace = lambda **kw: calls.setdefault("score", kw)

    class B:  # duck-typed bundle
        class anomaly:
            detected, score, pct_delta = True, -4.2, -0.1

        class factor_decomposition:
            primary_factor = "fill_rate"

        localized_segment = {"country": "IN"}
        metric = "revenue"

    tracing.stamp_trace_verdict(B)

    assert calls["io"]["output"]["primary_factor"] == "fill_rate"
    assert calls["io"]["output"]["localized_segment"] == {"country": "IN"}
    assert calls["score"] == {"name": "anomaly_score", "value": -4.2, "data_type": "NUMERIC"}


def test_score_trace_noop_without_langfuse(monkeypatch):
    monkeypatch.setattr(tracing, "langfuse", lambda: None)
    tracing.score_trace("guardrail_passed", 1, "BOOLEAN")  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_phase_tracing.py -q`
Expected: FAIL with `AttributeError: ... has no attribute 'stamp_trace_verdict'`.

- [ ] **Step 3: Implement in `narrator/tracing.py`**

In `investigation_trace`, add tags to the existing `propagate_attributes` call:

```python
    with propagate_attributes(session_id=session_id, trace_name=f"investigation:{metric}",
                              tags=[metric]):
```

Append the two helpers:

```python
def score_trace(name: str, value, data_type: str) -> None:
    """Attach a Langfuse score to the current trace — shows as a trace-list column."""
    lf = langfuse()
    if lf is None or lf.get_current_trace_id() is None:
        return
    lf.score_current_trace(name=name, value=value, data_type=data_type)


def stamp_trace_verdict(bundle) -> None:
    """Write the investigation's conclusion onto the root trace, so the judge sees the verdict
    in the trace LIST before opening anything."""
    lf = langfuse()
    if lf is None or lf.get_current_trace_id() is None:
        return
    lf.set_current_trace_io(output={
        "detected": bundle.anomaly.detected,
        "primary_factor": bundle.factor_decomposition.primary_factor,
        "localized_segment": bundle.localized_segment,
        "score": bundle.anomaly.score,
        "pct_delta": bundle.anomaly.pct_delta,
    })
    score_trace("anomaly_score", bundle.anomaly.score, "NUMERIC")
```

- [ ] **Step 4: Wire into `api/pipeline.py`**

In `run_investigation`, inside the `with investigation_trace(...)` block, right before `store.save_bundle` (i.e., after `bundle.trace_url = trace.url`), add:

```python
        stamp_trace_verdict(bundle)
```

In `narrate_investigation`, inside the `with narration_span(...)` block's `else:` branch (successful narration), after the `span.update(...)` call, add:

```python
            verification = bundle.narrative_verification
            score_trace("guardrail_passed", 1 if (verification and verification.passed) else 0,
                        "BOOLEAN")
```

Update the pipeline import line:

```python
from narrator.tracing import investigation_trace, narration_span, score_trace, stamp_trace_verdict
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_phase_tracing.py tests/test_pipeline.py tests/test_narrate.py -q`
Expected: all pass (`test_pipeline` stubs `investigation_trace`; `stamp_trace_verdict` no-ops without a live client).

- [ ] **Step 6: Commit**

```bash
git add backend/narrator/tracing.py backend/api/pipeline.py backend/tests/test_phase_tracing.py
git commit -m "feat(tracing): trace-list verdicts — tags, root output, anomaly/guardrail scores

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- backend/narrator/tracing.py backend/api/pipeline.py backend/tests/test_phase_tracing.py
```

---

### Task 6: Live verification + `docs/langfuse.md` user guide

**Files:**
- Create: `docs/langfuse.md`
- Verify: full suite + one live investigation against the running Docker stack

**Interfaces:**
- Consumes: everything above, plus the running compose stack (backend on :8000, langfuse-web on :3000).
- Produces: the teaching doc the user asked for; a verified live trace exhibiting the phase story.

- [ ] **Step 1: Full test suite + lint**

Run: `./.venv/Scripts/python.exe -m pytest -q` and `./.venv/Scripts/python.exe -m ruff check narrator data rca api tests`
Expected: everything green (baseline was 207 passed / 1 skipped; now higher with the new suites).

- [ ] **Step 2: Rebuild backend container and run one live investigation**

The user runs the stack; ASK before rebuilding, or hand them the commands:

```bash
docker compose up -d --build backend
curl -s -X POST localhost:8000/investigate -H "Content-Type: application/json" -d '{"metric":"revenue","window":null}'
```

- [ ] **Step 3: Verify the trace structure in Langfuse's ClickHouse**

```bash
docker compose exec -T langfuse-clickhouse clickhouse-client --user clickhouse --password clickhouse --query "SELECT name, count() FROM observations WHERE project_id='rca' AND trace_id=(SELECT id FROM traces WHERE project_id='rca' AND name LIKE 'investigation%' ORDER BY timestamp DESC LIMIT 1) GROUP BY name ORDER BY name"
```

Expected: named phases (`detect`, `decompose`, `drilldown`, `depth-0:*`, `ruled-out`) and `sql:*` spans — zero bare `clickhouse-query`. Also verify no NEW orphan traces appeared:

```bash
docker compose exec -T langfuse-clickhouse clickhouse-client --user clickhouse --password clickhouse --query "SELECT count() FROM traces WHERE project_id='rca' AND name='clickhouse-query' AND timestamp > now() - INTERVAL 10 MINUTE"
```

Expected: `0`.

- [ ] **Step 4: Write `docs/langfuse.md`**

Sections (write actual content, aimed at the user demoing to judges):

1. **What Langfuse shows and why it's scored** — one paragraph tying to the rubric line "what was checked, in what order, and why. No trace, no credit."
2. **Logging in** — http://localhost:3000, `admin@clickathon.local` / `LANGFUSE_INIT_USER_PASSWORD` (default `clickathon123`); warning: sign IN, don't sign UP.
3. **Reading an investigation trace** — annotated walk of the phase tree (detect → decompose → drilldown → depth-N decisions → ruled-out → narrate); what each verdict output means; how `sql:*` child spans carry the exact SQL as span input.
4. **The trace list** — tags (metric), scores (`anomaly_score`, `guardrail_passed`), root output verdict; how to filter by session to follow one chat conversation.
5. **Live demo behavior** — `tracing.live_flush` makes phases appear while the investigation runs; where to toggle it (`backend/config.json`).
6. **For developers** — adding a phase to new code (`with phase("name") as p: ... p.verdict(...)`), naming SQL (`run_query(..., name="sql:...")`), degradation rules (no keys → no-op; no active trace → no span, which is why dev-console queries create no noise).

- [ ] **Step 5: Commit**

```bash
git add docs/langfuse.md
git commit -m "docs: Langfuse guide — reading investigation traces, scores, live demo, dev how-to

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- docs/langfuse.md
```

---

## Self-review notes

- Spec coverage: §1 phase() → Task 1; §2 orphan guard → Task 2; §3 instrumentation map → Tasks 3–4 (narrate phase already exists via `narration_span`; guardrail verdict added in Task 5); §4 surfacing → Task 5; §5 config → Task 1; §6 testing → Tasks 1–5; §7 doc → Task 6. Live+post-hoc goal → per-phase flush (Task 1) + live verify (Task 6).
- `Phase.rename` is introduced in Task 4 and tested there via the final-name helper; Task 1's `Phase` compiles without it.
- Types consistent: `phase(name, input=None)` / `verdict(**kw)` / `rename(name)` used identically in Tasks 3–4; `_pop`/`_by_dim` arity change is contained in Task 4 (both call sites are inside `drill`).
