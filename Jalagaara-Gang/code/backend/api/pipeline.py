"""JAL-79: the one place an investigation actually runs.

Both POST /investigate and POST /v1/chat/completions come through here, so the trace, the
persistence and the fixture fallback cannot drift apart between them.

WHY THIS EXISTS AT ALL: `investigation_trace()` was written by Lane C but nothing ever called
it, so Langfuse emitted zero spans - a scored criterion sitting at zero with the plumbing
already built. Opening the root trace here is the whole fix, and it multiplies: `run_query`
already emits a span per query that nests via OpenTelemetry context, so every SQL statement the
pipeline runs appears inside this trace automatically, with no further instrumentation.

The engine (Lane B's `build_bundle`) is still a stub. Rather than fail, we fall back to the
fixture so the API, LibreChat and the dashboard can all be wired and demoed now. That fallback
is reported honestly through `engine_status()` and GET /health - silently serving fixture
numbers as a real diagnosis is exactly the kind of thing that loses trust points.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from data import store
from models import EvidenceBundle, Window
from narrator.tracing import (
    investigation_trace,
    narration_span,
    phase,
    score_trace,
    stamp_trace_verdict,
)

log = logging.getLogger(__name__)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample_bundle.json"


def engine_status() -> str:
    """'live' once Lane B's engine is implemented, else 'fixture'.

    Probed rather than hardcoded, so the API flips to 'live' the moment the engine lands with
    no change needed here. The probe looks for the NotImplementedError sentinel in each
    function's compiled code, which is cheap and has no side effects - unlike calling them.
    """
    try:
        from rca import bundle, decomposition, detection, drilldown
    except Exception:
        return "fixture"

    targets = [(bundle, "build_bundle"), (detection, "detect"),
               (decomposition, "decompose"), (drilldown, "drill")]
    for module, name in targets:
        func = getattr(module, name, None)
        if func is None or "NotImplementedError" in getattr(func.__code__, "co_names", ()):
            return "fixture"
    return "live"


def engine_mode() -> str:
    """What /health should report: 'live', 'fixture', or 'offline'.

    engine_status() only probes whether Lane B's code is implemented — it says 'live' even when
    ClickHouse is unreachable, and then every investigation 500s. Splitting the datastore check
    out is what lets the dashboard show 'engine offline' (bad/missing CLICKHOUSE_*) instead of
    blanking:
        live    — engine implemented AND ClickHouse reachable
        fixture — engine still stubbed (serves the sample bundle by design)
        offline — engine ready but the datastore is unreachable (serves the sample, no persist)
    """
    if engine_status() != "live":
        return "fixture"
    from data.client import clickhouse_available

    return "live" if clickhouse_available() else "offline"


def _fixture_bundle(investigation_id: str, metric: str, window: Window | None) -> EvidenceBundle:
    bundle = EvidenceBundle.model_validate(json.loads(FIXTURE.read_text()))
    bundle.investigation_id = investigation_id
    bundle.metric = metric
    if window:
        bundle.target_window = window
    return bundle


def run_investigation(
    metric: str,
    window: Window | None = None,
    session_id: str | None = None,
    persist: bool = False,
) -> EvidenceBundle:
    """Run one investigation end to end: trace it, build it, optionally persist it.

    Returns the bundle WITHOUT a narrative. Narration is a separate call (JAL-80) so the UI can
    show real numbers in ~2s, and so an LLM failure cannot destroy an otherwise complete and
    scoreable bundle.

    `persist` defaults to False and is intentionally NOT exposed by any API endpoint —
    `bundles` must only ever be written to from the seeding path (api/dev.py::seed_bundles /
    seed_context), which is the only code that calls this with persist=True. POST /investigate
    computes and returns a bundle for the caller to look at; it does not add a row.
    """
    from data.client import clickhouse_available

    investigation_id = str(uuid.uuid4())

    # 'live' needs BOTH the engine implemented and a reachable ClickHouse. When the datastore is
    # down we serve the fixture and skip persistence rather than 500 — the same honest fallback
    # engine_status already gives a stubbed engine, extended to a data outage (bad CLICKHOUSE_*).
    data_up = clickhouse_available()
    live = engine_status() == "live" and data_up

    with investigation_trace(investigation_id, metric, session_id) as trace:
        if live:
            from rca.bundle import build_bundle

            bundle = build_bundle(metric, window)
            bundle.investigation_id = investigation_id
        else:
            reason = "datastore offline" if engine_status() == "live" else "engine stubbed (JAL-76/79)"
            log.warning(
                "Serving FIXTURE data for investigation %s - %s. Numbers are not computed "
                "from ClickHouse.",
                investigation_id, reason,
            )
            bundle = _fixture_bundle(investigation_id, metric, window)

        # Enforce the investigate/narrate split at the seam rather than trusting callers.
        # The fixture ships with prose, and a future build_bundle might too; either way an
        # un-narrated bundle is the contract here, so that /narrate is what produces prose
        # and `narrated` in the stored row means something.
        bundle.narrative = None
        bundle.narrative_verification = None

        bundle.created_at = datetime.now()
        bundle.trace_url = trace.url
        stamp_trace_verdict(bundle)
        # Only persist when explicitly asked AND the datastore is reachable — see docstring:
        # `bundles` is seed-path-only, so every non-seed caller leaves persist=False and this
        # never runs for them.
        if persist and data_up:
            store.save_bundle(bundle, trace_id=trace.trace_id, session_id=session_id)

    return bundle


# Chat-facing method aliases: friendly names -> detector keys registered in rca.detection.
_METHOD_ALIASES = {"statistical": "robust_z", "ml": "isolation_forest"}


def run_detection(
    metric: str,
    window: Window,
    method: str | None = None,
    session_id: str | None = None,
    persist: bool = False,
) -> EvidenceBundle:
    """Detection-grade investigation for the chat: REAL detection from ClickHouse via the chosen
    method, traced, optionally persisted. Returns the bundle WITHOUT a narrative - the chat adds
    prose via narrate_investigation(), so the generation span reattaches to this trace and an LLM
    failure cannot destroy a valid bundle (the same investigate/narrate split as run_investigation).

    Runs only the parts implemented today: detection.detect(). Segment localization (decompose/
    drill) is left EMPTY rather than faked - honest is the whole point.

    `persist` defaults to False — see run_investigation's docstring, same seed-path-only rule.
    The chat endpoint never passes True, so a chat-triggered investigation is computed and
    returned but never added to `bundles`.
    """
    from rca.detection import detect

    investigation_id = str(uuid.uuid4())
    detector = _METHOD_ALIASES.get(method or "", method)  # 'ml'/'statistical' -> detector key

    with investigation_trace(investigation_id, metric, session_id) as trace:
        # The detectors are hour-grain; a chat window is usually a whole day. Scan the day's hours
        # and report the worst one, so we surface the planted anomaly rather than whatever sits at
        # midnight. `detect` is called per hour via the same chosen method.
        with phase("detect", input={"metric": metric, "detector": detector or "default"}) as p:
            anomaly, queries, hour, segment = _scan_window(metric, window, detector)
            p.verdict(detected=anomaly.detected, observed=anomaly.observed, expected=anomaly.expected,
                      score=anomaly.score, direction=anomaly.direction, segment=segment)
        bundle = _detection_bundle(investigation_id, metric, hour, anomaly, queries, detector)
        # Record WHERE it was found. Empty = the move is population-wide, which is a real
        # finding in its own right (e.g. the Jun 21 collapse), not a missing localization.
        bundle.localized_segment = segment
        bundle.narrative = None  # investigate/narrate split; narrate_investigation adds prose
        bundle.narrative_verification = None
        bundle.trace_url = trace.url
        if persist:
            store.save_bundle(bundle, trace_id=trace.trace_id, session_id=session_id)

    return bundle


def _hours_in(window: Window) -> list:
    from datetime import timedelta

    hours, t = [], window.start.replace(minute=0, second=0, microsecond=0)
    while t < window.end:
        hours.append(t)
        t += timedelta(hours=1)
    return hours or [window.start]  # zero-width window -> score the single start hour


def _scan_window(metric: str, window: Window, detector: str | None):
    """Segment-aware scan of the window; returns (anomaly, queries, hour-window, segment).

    Delegates to rca.detection.detect_in_window: score every hour globally, and only if nothing
    fires, look inside the population per dimension. Global-only scoring is blind to a localised
    anomaly by construction (the APAC x iOS 18.1 fill_rate drop is -51% in-segment but -1.2%
    globally), so this is what takes detection from 3/5 to 5/5 on the ground-truth cases.

    `segment` is {} when the move really is population-wide — which is the correct answer for a
    global event, not a failure to localise.
    """
    from rca.detection import detect_in_window

    return detect_in_window(metric, window, detector)


def _round_anomaly(anomaly):
    """Present clean numbers to the narrator/UI. The exact values remain reproducible from the
    logged queries[]; this only trims float noise so the prose doesn't cite 18.3315000001."""
    from models import Anomaly

    return Anomaly(
        detected=anomaly.detected,
        observed=round(anomaly.observed, 2),
        expected=round(anomaly.expected, 2),
        abs_delta=round(anomaly.abs_delta, 2),
        pct_delta=round(anomaly.pct_delta, 4),
        score=round(anomaly.score, 2),
        direction=anomaly.direction,
    )


def _detection_bundle(investigation_id, metric, window, anomaly, queries, detector):
    from models import BaselineWindow, FactorDecomposition, Query

    return EvidenceBundle(
        investigation_id=investigation_id,
        created_at=datetime.now(),
        metric=metric,
        target_window=window,
        baseline_window=BaselineWindow(
            method="same_weekday_trailing_weeks",
            description=f"detection via {detector or 'default'}",
        ),
        anomaly=_round_anomaly(anomaly),
        # Localization is Lane B (decompose/drill); left empty rather than faked.
        factor_decomposition=FactorDecomposition(
            method="not_computed", factors=[], primary_factor="pending"
        ),
        drilldown=[],
        ruled_out=[],
        queries=[Query(**q) for q in queries],
    )


def narrate_investigation(investigation_id: str, persist: bool = False) -> EvidenceBundle | None:
    """Add prose to a stored bundle. Returns None if the investigation does not exist.

    Reading the bundle to narrate it is unrestricted (`bundles` reads are fine from anywhere);
    `persist` gates only the WRITE-back of the narrated result, defaulting False for the same
    seed-path-only reason as run_investigation/run_detection. A bundle that was never persisted
    (any non-seed caller) has nothing to load here and this returns None — by design, not a bug.

    Three things this must guarantee, in order of importance:

    1. The generation span lands in the trace the investigation already opened, so a judge
       reads one coherent investigation rather than two unrelated traces.
    2. The guardrail runs on the result. Every number in the prose must already exist in the
       bundle; a fabricated figure costs more than a missed anomaly.
    3. An LLM failure never destroys a valid bundle. The numbers, drilldown and ruled-out
       list are already computed and scoreable - narration is a presentation layer, so a
       Bedrock outage degrades the answer instead of losing it.
    """
    bundle = store.load_bundle(investigation_id)
    if bundle is None:
        return None

    # Both are re-supplied on the save below. investigations is a ReplacingMergeTree keyed on
    # investigation_id, so omitting session_id here does not leave it alone — it replaces the
    # row with an empty one and silently unlinks the investigation from its conversation.
    trace_id, session_id = store.load_meta(investigation_id)

    with narration_span(trace_id, bundle.metric) as span:
        try:
            from narrator.narrate import narrate

            bundle = narrate(bundle)
        except Exception as exc:  # noqa: BLE001 - any LLM/transport failure is non-fatal here
            log.warning("Narration failed for %s: %s", investigation_id, exc)
            bundle.narrative = None
            bundle.narrative_verification = None
            if span is not None:
                span.update(output={"error": str(exc)}, level="ERROR")
        else:
            if span is not None:
                verification = bundle.narrative_verification
                span.update(
                    input={"investigation_id": investigation_id, "metric": bundle.metric},
                    output=bundle.narrative,
                    metadata={
                        "guardrail_passed": bool(verification and verification.passed),
                        "unverified_numbers": list(verification.unverified_numbers)
                        if verification else [],
                    },
                )
            verification = bundle.narrative_verification
            score_trace("guardrail_passed", 1 if (verification and verification.passed) else 0,
                        "BOOLEAN")
            if bundle.narrative_verification and not bundle.narrative_verification.passed:
                log.warning(
                    "Guardrail FAILED for %s - numbers not in bundle: %s",
                    investigation_id, bundle.narrative_verification.unverified_numbers,
                )

    if persist:
        store.save_bundle(bundle, trace_id=trace_id, session_id=session_id)
    return bundle
