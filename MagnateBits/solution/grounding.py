"""Numeric grounding: every asserted number must appear in a cited query result.

Why this exists. On the first clean end-to-end run the Analytics Agent produced a
fluent, well-argued, *false* finding -- it claimed a median was $0 "in every segment"
while the very queries it cited returned 37,536 / 29,926 / 26,127. It had conflated a
whole-column data-quality probe (which legitimately scans all rows) with the scoped
distribution query. Confidence was 0.77.

A wrong number delivered fluently is worse than no finding: a PM would act on it. So
before anything reaches a report, we check each finding's headline value against the
numbers actually present in the query results it cites. This is deterministic Python,
not a second LLM call -- cheap, fast, and a judge can re-run it.

Findings are demoted and caveated rather than deleted: a claim can be legitimately
derived (a ratio of two frame numbers) without appearing verbatim. Demotion makes the
failure visible without silently discarding a possibly-real signal.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from contracts import Finding, InsightReport, QueryRun

_NUM = re.compile(r"-?\d[\d,]*\.?\d*")
TOLERANCE = 0.01  # 1% relative


def _floats(value: Any) -> list[float]:
    """Every number reachable inside a query-result cell."""
    out: list[float] = []
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        out.append(float(value))
    elif isinstance(value, str):
        for tok in _NUM.findall(value):
            try:
                out.append(float(tok.replace(",", "")))
            except ValueError:
                pass
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_floats(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(_floats(v))
    return out


def evidence_pool(runs: Iterable[QueryRun]) -> set[float]:
    """Numbers a finding may legitimately assert, plus percent/fraction restatements."""
    pool: set[float] = set()
    for run in runs:
        for row in run.result:
            for f in _floats(row):
                pool.add(round(f, 6))
                pool.add(round(f * 100.0, 6))  # 0.1079 stated as 10.79%
                pool.add(round(f / 100.0, 6))
    return pool


def _matches(value: float, pool: set[float]) -> bool:
    if value in pool:
        return True
    scale = max(abs(value), 1.0)
    return any(abs(value - p) <= TOLERANCE * scale for p in pool)


def check_finding(finding: Finding, runs_by_name: dict[str, QueryRun]) -> tuple[bool, str]:
    """(grounded, reason). Ungrounded means: cited nothing, or asserted an absent number."""
    cited = [runs_by_name[n] for n in finding.supporting_queries if n in runs_by_name]
    if not cited:
        return False, "cites no query that ran"
    pool = evidence_pool(cited)
    if not pool:
        return False, "cited queries returned no numeric rows"
    if _matches(float(finding.value), pool):
        return True, ""
    return False, (
        f"asserts {finding.metric}={finding.value:g}, which does not appear in "
        f"{', '.join(finding.supporting_queries[:3])}"
    )


def verify(report: InsightReport, runs: list[QueryRun]) -> tuple[InsightReport, list[str]]:
    """Demote + caveat every ungrounded finding. Returns (report, human-readable notes)."""
    by_name = {r.name: r for r in runs if not r.error}
    notes: list[str] = []
    for f in report.findings:
        ok, reason = check_finding(f, by_name)
        if ok:
            continue
        notes.append(f"{f.headline[:70]} — {reason}")
        f.severity = "info"
        f.confidence.score = round(min(f.confidence.score, 0.25), 4)
        f.caveats.insert(
            0,
            f"UNVERIFIED: this finding's headline number could not be matched to its "
            f"own cited query results ({reason}). Treat as a lead, not a fact.",
        )
    if notes:
        report.caveats.insert(
            0,
            f"{len(notes)} finding(s) failed numeric grounding and were demoted to "
            f"informational; their numbers do not appear in the queries they cite.",
        )
    return report, notes
