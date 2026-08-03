"""
correctness.py
--------------
Deterministic evaluators. No LLM, no opinion — either the agent reported the
right number or it did not.

Three scores:

  numeric_accuracy   Does the answer contain the true peak value? Tolerant of
                     thousands separators and small rounding, strict about the
                     value itself.
  reports_moment     Does it state WHEN the peak occurred? The single most
                     common failure: a correct number with no minute attached,
                     which quietly discards the fact that peak is a moment.
  rule_compliance    For trap questions, did it refuse the false premise
                     instead of producing a confident wrong number?

These run before the LLM judge and cost nothing. A run where numeric_accuracy
collapses is not a prompt-tuning problem, it is a broken pipeline — and you
want to know that without reading judge prose.
"""

import re


def _numbers(text: str) -> set[int]:
    """Every integer in the text, with 1,234 and 1234 treated as the same."""
    out = set()
    for m in re.findall(r"\d[\d,]*", text or ""):
        try:
            out.add(int(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _has_value(text: str, target: int, tol: float = 0.02) -> bool:
    """True if any number in the text is within tolerance of the target."""
    if target == 0:
        return bool(re.search(r"\b(no|zero|none)\b", (text or "").lower()))
    window = max(1, int(abs(target) * tol))
    return any(abs(n - target) <= window for n in _numbers(text))


_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _has_moment(text: str, expected_minute: str | None = None) -> bool:
    """A stated time counts; matching the expected minute counts for more."""
    text = text or ""
    if expected_minute:
        hhmm = expected_minute[11:16]          # 'YYYY-MM-DD HH:MM:SS' -> 'HH:MM'
        if hhmm and hhmm in text:
            return True
    return bool(_TIME_RE.search(text))


_REFUSAL_CUES = (
    "cannot", "can't", "not additive", "different minutes", "does not sum",
    "doesn't sum", "not meaningful", "misleading", "no such", "would be wrong",
    "not a valid", "peaks occur at different", "cannot be summed",
)


def correctness_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    """
    Dataset items carry their ground truth in metadata:
        kind          "value" | "moment" | "trap" | "open"
        peak          expected peak value      (kind=value)
        peak_minute   expected minute string   (kind=value/moment)
    """
    meta = metadata or {}
    kind = meta.get("kind", "open")
    text = str(output or "")
    evals = []

    if not text.strip():
        return [{"name": "numeric_accuracy", "value": 0.0, "comment": "empty output"}]

    if kind in ("value", "moment"):
        expected_minute = meta.get("peak_minute")

        if "peak" in meta:
            hit = _has_value(text, int(meta["peak"]))
            evals.append({
                "name": "numeric_accuracy",
                "value": 1.0 if hit else 0.0,
                "comment": f"expected {meta['peak']}; {'found' if hit else 'NOT found'} in answer",
            })

        moment = _has_moment(text, expected_minute)
        evals.append({
            "name": "reports_moment",
            "value": 1.0 if moment else 0.0,
            "comment": f"expected minute {expected_minute}; "
                       f"{'a time was stated' if moment else 'NO time stated'}",
        })

    elif kind == "trap":
        low = text.lower()
        refused = any(cue in low for cue in _REFUSAL_CUES)
        evals.append({
            "name": "rule_compliance",
            "value": 1.0 if refused else 0.0,
            "comment": "refused the false premise" if refused
                       else "ANSWERED a question with no valid answer",
        })

    if not evals:
        evals.append({"name": "answered", "value": 1.0, "comment": "open-ended item"})
    return evals


def word_budget_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    wc = len(str(output or "").split())
    return {"name": "word_count", "value": wc, "comment": f"{wc} words"}