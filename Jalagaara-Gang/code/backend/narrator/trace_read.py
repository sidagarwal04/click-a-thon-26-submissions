"""JAL-88: read a finished investigation trace back out of Langfuse, shaped for the dashboard.

`tracing.py` WRITES spans; this READS them. The Langfuse UI is comprehensive but developer-facing
— a customer wants the story, not a span tree. So each phase span becomes one step with a
plain-language headline composed from its verdict, and the `sql:*` children become the evidence
underneath it. The raw trace stays one click away for anyone who wants it.

Never raises: an absent trace id, tracing switched off, or an unreachable Langfuse all return
`{"available": False, "reason": ...}` so the drawer can say so instead of the API 500-ing.
"""
from __future__ import annotations

from typing import Any

from obs import langfuse

_ROOT_PREFIX = "investigation:"
# The judge-facing phases, in the vocabulary tracing.py writes. Anything else under a phase
# (sql:*, scan:*) is evidence, shown inside its step rather than as a step of its own.
_PHASES = ("detect", "decompose", "drilldown", "depth-", "ruled-out", "narrate")


def _is_phase(name: str) -> bool:
    return name.startswith(_PHASES)


def trace_view(trace_id: str | None) -> dict[str, Any]:
    """The dashboard's view of one investigation trace."""
    lf = langfuse()
    if lf is None:
        return {"available": False, "reason": "Langfuse is not configured"}
    if not trace_id:
        return {"available": False, "reason": "This investigation has no trace"}
    try:
        return shape(lf.api.trace.get(trace_id))
    except Exception as exc:  # noqa: BLE001 - any transport/API failure degrades, never raises
        return {"available": False, "reason": str(exc)}


def shape(trace) -> dict[str, Any]:
    """Reshape a Langfuse trace into ordered steps with their queries. Pure — unit-tested."""
    observations = sorted(trace.observations, key=lambda o: o.start_time)
    queries_by_parent: dict[str, list] = {}
    for obs in observations:
        if not _is_phase(obs.name) and not obs.name.startswith(_ROOT_PREFIX):
            queries_by_parent.setdefault(obs.parent_observation_id, []).append({
                "name": obs.name,
                "sql": obs.input if isinstance(obs.input, str) else "",
                "ms": _ms(obs.latency),
                "summary": obs.output if isinstance(obs.output, dict) else {},
            })

    steps = [
        {
            "phase": obs.name,
            "ms": _ms(obs.latency),
            "headline": _headline(obs),
            "verdict": obs.output if isinstance(obs.output, dict) else {},
            "queries": queries_by_parent.get(obs.id, []),
        }
        for obs in observations
        if _is_phase(obs.name)
    ]
    return {
        "available": True,
        "total_ms": _ms(trace.latency),
        "scores": {s.name: s.value for s in (trace.scores or [])},
        "steps": steps,
    }


def _ms(latency: float | None) -> int:
    return round((latency or 0) * 1000)


def _headline(obs) -> str:
    """One customer-readable sentence per phase, composed from the span's own verdict.

    Falls back to the phase name rather than inventing text, so a span we do not recognise
    still shows up honestly instead of being dropped.
    """
    out = obs.output if isinstance(obs.output, dict) else {}
    name = obs.name

    if name == "detect":
        metric = (obs.input or {}).get("metric", "metric") if isinstance(obs.input, dict) else "metric"
        if not out.get("detected", False):
            return f"No anomaly in {metric} — {_num(out.get('observed'))} is within its normal range"
        return (f"Confirmed anomaly — {metric} {_num(out.get('observed'))} vs "
                f"{_num(out.get('expected'))} expected ({_num(out.get('score'), 1)}σ, {out.get('direction', '')})")

    if name == "decompose":
        factors = out.get("factors", {})
        others = ", ".join(f"{k} {_pct(v)}" for k, v in factors.items() if k != out.get("primary_factor"))
        return f"{out.get('primary_factor', '?')} drove the move ({_pct(factors.get(out.get('primary_factor')))}) — {others}"

    if name == "drilldown":
        segment = out.get("localized_segment") or {}
        if not segment:
            return "No single segment responsible — the move is population-wide"
        return f"Localized to {_segment(segment)} after {out.get('depth', 0)} level(s)"

    if name.startswith("depth-"):
        if out.get("decision") == "descend":
            # The dimension is already in the "Split by" clause — name only the value here.
            winner = ", ".join(str(v) for v in (out.get("winner") or {}).values())
            return (f"Split by {name.split(':', 1)[-1]} → {winner} explains "
                    f"{_pct(out.get('contribution_pct'))} of the gap at {out.get('lift')}× its share")
        return f"Search stopped — {out.get('reason', 'no further split')}"

    if name == "ruled-out":
        cleared = out.get("cleared") or {}
        if not cleared:
            return "Nothing further to rule out"
        return "Checked and cleared: " + "; ".join(f"{k} ({v})" for k, v in cleared.items())

    if name.startswith("narrate"):
        return "Diagnosis written from the evidence above"

    return name


def _segment(segment: dict) -> str:
    return " and ".join(f"{k} = {v}" for k, v in segment.items())


def _num(value, places: int = 3) -> str:
    return f"{value:.{places}f}" if isinstance(value, (int, float)) else "—"


def _pct(value) -> str:
    return f"{value * 100:.1f}%" if isinstance(value, (int, float)) else "—"
