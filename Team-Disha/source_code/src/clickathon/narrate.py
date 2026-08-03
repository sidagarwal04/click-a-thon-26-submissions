"""LLM narrator — only uses numbers present in findings JSON."""

from __future__ import annotations

import json
from typing import Any

from clickathon.llm import complete
from clickathon.telemetry import investigation_span


NARRATOR_SYSTEM = """You are the InMobi ad-metrics root-cause narrator for a hackathon demo.
You receive a findings JSON produced by ClickHouse queries.
Rules:
- Use ONLY numbers that appear in the JSON. Never invent metrics.
- Explain: what moved, which factor (requests/fill/eCPM), which segment, what was ruled out.
- Be concise (6–10 sentences). Lead with the diagnosis.
- If shape is global_uniform, say the drop is proportional across dimensions.
- Mention baseline = same weekday 7 days earlier.
"""

DETAILED_NARRATOR_SYSTEM = """You are the InMobi ad-metrics root-cause analyst for a hackathon demo.
You receive a DETAILED RCA pack from ClickHouse (eda.rca_*).
Write a thorough diagnosis the user can read in chat.

Rules:
- Use ONLY numbers present in the JSON. Never invent metrics, segments, or dates.
- Structure the answer with these headings:
  1. Executive diagnosis (2–3 sentences)
  2. Global WoW on the probe day (quote requests/fill/eCPM/revenue vs T−7)
  3. Factor decomposition (shares + why primary factor wins)
  4. Localization (primary segment + 2–4 supporting segments with numbers)
  5. Incident window (how the multi-day window behaves if present)
  6. Ruled out (and why, briefly)
- Baseline is always same weekday −7. Ratios are sum/sum.
- If hidden_globally is true, say the global series understates the segment hit.
- Keep it concrete and numeric; avoid fluff. About 15–25 sentences total is fine.
"""


def narrate_findings(findings: dict[str, Any]) -> str:
    # Strip narrative if present to avoid recursion
    payload = {k: v for k, v in findings.items() if k != "narrative"}
    prompt = (
        NARRATOR_SYSTEM
        + "\n\nFINDINGS JSON:\n"
        + json.dumps(payload, default=str)
        + "\n\nWrite the diagnosis now."
    )
    with investigation_span("narrate", metadata={"day": str(findings.get("day"))}):
        try:
            return complete(prompt)
        except Exception as exc:  # noqa: BLE001
            # Deterministic fallback without LLM
            d = findings.get("diagnosis") or {}
            det = findings.get("detection") or {}
            dec = findings.get("decomposition") or {}
            return (
                f"On {findings.get('day')} vs baseline {findings.get('baseline_day')} "
                f"(same weekday −7), primary factor is {dec.get('primary_factor')}. "
                f"Segment: {d.get('segment')}. "
                f"Deltas: {det.get('deltas')}. "
                f"Ruled out: {findings.get('ruled_out')}. "
                f"(LLM narration unavailable: {exc})"
            )


def narrate_detailed_rca(pack: dict[str, Any]) -> str:
    """Longer narration for explain_anomaly packs."""
    payload = {
        k: v
        for k, v in pack.items()
        if k not in ("narrative", "instructions_for_agent", "short_explanation")
    }
    # Prefer the deterministic explanation as scaffolding for the LLM
    prompt = (
        DETAILED_NARRATOR_SYSTEM
        + "\n\nDETAILED RCA JSON:\n"
        + json.dumps(payload, default=str)[:120000]
        + "\n\nWrite the full root-cause analysis now."
    )
    with investigation_span(
        "narrate.detailed",
        metadata={"day": str(pack.get("probe_day")), "incident_id": str(pack.get("incident_id"))},
    ):
        try:
            return complete(prompt)
        except Exception as exc:  # noqa: BLE001
            return (pack.get("explanation") or "") + f"\n\n(LLM narration unavailable: {exc})"
