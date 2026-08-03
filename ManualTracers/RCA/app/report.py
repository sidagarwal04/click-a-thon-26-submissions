"""Maps a ledger + narration into the UI report shape (docs/RCA_UI_TEMPLATE.md).

The narrator writes plain prose paragraphs, one per system-prompt section, in a fixed
count derived from the ledger's own shape — never guessed from paragraph count alone:
§1 (what happened) is always 1 paragraph, §2 (which factor) is 1 only when
decomposition is present, §3 (which segment) is one paragraph per finding, §4 (checked
and ruled out) is 1. Slicing on that known structure is what makes split_narrative
survive a multi-factor revenue decomposition (N findings), not just the single-finding
case every sample report happens to show.
"""

import uuid
from datetime import datetime, timezone

from app.schemas import ClickStackAlertPayload

EMPTY_SECTIONS = {
    "what_went_wrong": "",
    "why_it_happened": "",
    "supporting_data_summary": "",
}


def split_narrative(text: str, ledger: dict) -> dict:
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if not paragraphs:
        return dict(EMPTY_SECTIONS)

    # not_reproducible (or any other one-sentence narrative): nothing further to section.
    if len(paragraphs) == 1:
        return {**EMPTY_SECTIONS, "what_went_wrong": paragraphs[0]}

    has_decomposition = bool(ledger.get("decomposition"))
    n_findings = len(ledger.get("findings") or [])

    i = 0
    what_went_wrong = [paragraphs[i]]
    i += 1
    if has_decomposition and i < len(paragraphs):
        what_went_wrong.append(paragraphs[i])
        i += 1

    why_it_happened = paragraphs[i : i + n_findings]
    i += len(why_it_happened)

    supporting_data_summary = paragraphs[i:]

    return {
        "what_went_wrong": "\n\n".join(what_went_wrong),
        "why_it_happened": "\n\n".join(why_it_happened),
        "supporting_data_summary": "\n\n".join(supporting_data_summary),
    }


def _holdout_reason(finding: dict, ruled_out_entry: str) -> str:
    """Mirrors rca-api/sample-reports.js's buildReport() exactly, so the hand-written
    sample reports and the real pipeline produce the same reason shape."""
    dim_name, _, dim_value = ruled_out_entry.partition("=")
    candidate = next(
        (
            c
            for c in finding["candidates"]
            if c["dim_name"] == dim_name and c["dim_value"] == dim_value
        ),
        None,
    )
    if candidate is None:
        return (
            "Tested at depth 1; movement did not localize to this segment after "
            "conditioning on the primary culprit."
        )
    top = finding["candidates"][0]
    residual_delta = finding["holdout"]["residual_delta"]
    return (
        f"Holdout residual ({residual_delta:.4f}) did not move with this slice; "
        f"contribution {candidate['contribution']:.0f} is a correlated follower "
        f"of {top['dim_name']}={top['dim_value']}."
    )


def ledger_to_report(
    ledger: dict, alert: ClickStackAlertPayload, narrative: dict
) -> dict:
    """docs/RCA_UI_TEMPLATE.md §"Step 1 — Map ledger → report template". Only the first
    finding feeds the top-level candidates/holdout/ruled_out fields — the template's own
    schema is singular there, same simplification the doc's reference pseudocode makes."""
    findings = ledger.get("findings") or []
    finding = findings[0] if findings else None
    sections = split_narrative(narrative["narrative"], ledger)

    trigger = {
        "metric_id": ledger.get("metric_id"),
        "alert_title": alert.title,
        "alert_body": alert.body,
        "window": ledger.get("window"),
        "dimension_hint": ledger.get("dimension_id"),
    }
    if finding:
        g = finding["global"]
        trigger.update(
            {
                "actual": g["actual"],
                "expected": g["expected"],
                "peak_abs_z": g["peak_abs_z"],
                "hours": g["hours"],
            }
        )

    ruled_out = [
        {"segment": s, "reason": _holdout_reason(finding, s)}
        for s in (finding.get("ruled_out") if finding else []) or []
    ]

    return {
        "id": f"rca-{ledger.get('metric_id')}-{uuid.uuid4().hex[:8]}",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "title": f"{ledger.get('metric_id')} — {ledger.get('verdict')}",
        "status": ledger.get("verdict"),
        "trigger": trigger,
        "sections": sections,
        "ruled_out": ruled_out,
        "candidates": finding["candidates"] if finding else [],
        "holdout": finding.get("holdout") if finding else None,
        "ledger": ledger,
    }
