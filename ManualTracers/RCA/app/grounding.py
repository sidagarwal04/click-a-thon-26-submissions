"""Mechanical grounding for the narrator (architecture.md §4, narration rules):
every number the LLM writes must already exist in the ledger, at some rounding, or the
narrative is discarded in favor of a plain summary built straight from the ledger."""

import re

from app.utils import iter_leaves

NUMBER_RE = re.compile(r"-?\d+\.\d+|-?\d+")
ROUND_NDIGITS = 6  # matches the 0-6dp range allowed_numbers() already tolerates


def round_floats(obj, ndigits: int = ROUND_NDIGITS):
    """Round every float leaf in a nested ledger structure before it reaches the model.

    ClickHouse floats carry 15-17 significant digits raw. The narrator's system prompt tells
    the model to copy numbers verbatim rather than round — correct behavior once the number
    it's copying is already clean, but a 17-digit echo of raw ClickHouse output reads as
    fabricated (allowed_numbers only recognizes 0-6dp roundings). Rounding once, here, before
    building the prompt AND before computing the allowed set keeps both sides looking at the
    same figure, and produces prose someone would actually want to read.
    """
    if isinstance(obj, dict):
        return {k: round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, ndigits) for v in obj]
    if isinstance(obj, float):
        return round(obj, ndigits)
    return obj


def fallback_summary(ledger: dict) -> str:
    """Built directly from the ledger, no LLM — used when narrate has nothing to say
    (unreproduced/undecomposed alerts) or when the LLM's output fails the grounding check."""
    lines = [
        f"Diagnosis for {ledger.get('metric_id')}: verdict={ledger.get('verdict', 'unknown')}."
    ]

    window = ledger.get("window")
    if window:
        lines.append(f"Window: {window['start']} to {window['end']}.")

    decomposition = ledger.get("decomposition")
    if decomposition:
        for f in decomposition["factors"]:
            lines.append(
                f"  factor={f['metric_id']} contribution_rel={f['contribution_rel']:.4f} "
                f"verdict={f['verdict']}"
            )

    for finding in ledger.get("findings", []):
        g = finding["global"]
        lines.append(
            f"  {finding['factor']}: actual={g['actual']:.4f} expected={g['expected']:.4f} "
            f"peak|z|={g['peak_abs_z']:.2f} verdict={finding['verdict']}"
        )
        holdout = finding.get("holdout")
        if holdout:
            lines.append(
                f"    top candidate: {_slice_name(holdout['candidate'])} "
                f"(holdout: {holdout['verdict']})"
            )
        interaction = finding.get("interaction") or {}
        if interaction.get("top"):
            lines.append(
                f"    crossed with {interaction['child_dim']}={interaction['top']['child_value']}: "
                f"top_share={interaction['top_share']:.2f} of {interaction['strata_tested']} strata, "
                f"{interaction['verdict']}"
            )
            crossed = interaction.get("holdout")
            if crossed:
                lines.append(
                    f"    crossed candidate: {_slice_name(crossed['candidate'])} "
                    f"(holdout: {crossed['verdict']})"
                )

    return "\n".join(lines)


def _slice_name(conditions: list[dict]) -> str:
    """holdout candidates are a list of ANDed conditions — one entry at depth 1, two crossed."""
    return " AND ".join(f"{c['dim_name']}={c['dim_value']}" for c in conditions)


def allowed_numbers(ledger: dict) -> set[str]:
    """Every number a grounded narrative is allowed to contain — raw ledger values plus the
    forms prose commonly renders them in (percentage/pp, sign dropped). Also pulls digit
    runs out of string leaves (dim values like 'Android 15', ISO timestamps) so a mention
    of the window date or segment name isn't flagged as fabricated."""
    allowed = set()
    for leaf in iter_leaves(ledger):
        if isinstance(leaf, bool):
            continue
        if isinstance(leaf, (int, float)):
            for v in (leaf, leaf * 100, abs(leaf), abs(leaf) * 100):
                # 0-6dp: covers both a verbatim echo of ClickHouse's raw float precision
                # and prose that rounds to 1-2 significant digits for readability
                for nd in range(7):
                    allowed.add(f"{v:.{nd}f}")
                if float(v).is_integer():
                    allowed.add(str(int(v)))
        elif isinstance(leaf, str):
            allowed.update(NUMBER_RE.findall(leaf))
    return allowed


def check_grounding(text: str, allowed: set[str]) -> list[str]:
    normalized = text.replace("−", "-")  # unicode minus, in case the model writes one
    found = NUMBER_RE.findall(normalized)
    return sorted({n for n in found if n not in allowed})
