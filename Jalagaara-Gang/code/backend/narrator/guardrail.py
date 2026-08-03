"""Lane C: hallucination guardrail. Every number in the prose must exist in the bundle,
AT THE MAGNITUDE THE BUNDLE STATES.

This is pure logic (no deps) so it works today. It is the trustworthiness backstop:
a single fabricated figure costs more than a missed anomaly.

Two independent checks, because digit-matching alone is not enough:

1. DIGITS - every numeric token in the prose appears somewhere in the evidence.

2. MAGNITUDE - a verified number must not be decorated with a scale suffix or currency
   symbol the bundle never carried. This caught a real failure: the bundle held
   `observed: 18.33` (one hour of revenue, correct - the dataset totals 17,020 over 840
   hours) and the narrator wrote "$18.33M". Every digit was genuine, so the digit check
   passed while the prose overstated revenue by a factor of a million. A judge reads that
   as a fabricated figure, and `passed: true` sitting beside it makes it worse, because it
   asserts the number was checked.

The rule is deliberately asymmetric: decorations are rejected unless the bundle itself
pairs that number with that decoration. Bundles here store bare floats, so in practice any
"$", "M" or "billion" attached to a figure is the model's invention.
"""
from __future__ import annotations

import re

from models import EvidenceBundle, NarrativeVerification

_NUM = re.compile(r"-?\d[\d,]*\.?\d*")

# A number immediately followed by a scale word/suffix, e.g. "18.33M", "18.33 billion".
# The suffix must be a whole word, so "18.33 metrics" is not a match.
_SCALED = re.compile(
    r"(-?\d[\d,]*\.?\d*)\s*(k|m|bn|b|mm|thousand|million|billion|trillion)\b",
    re.IGNORECASE,
)
# A currency symbol attached to a number, e.g. "$18.33".
_CURRENCY = re.compile(r"([$€£¥])\s*(-?\d[\d,]*\.?\d*)")


def _numbers(text: str) -> set[str]:
    return {_norm(m) for m in _NUM.findall(text or "")}


def _norm(token: str) -> str:
    return token.replace(",", "").rstrip(".").lstrip("-")


def _evidence_text(bundle: EvidenceBundle) -> str:
    return bundle.model_dump_json(exclude={"narrative", "narrative_verification"})


def _bundle_numbers(bundle: EvidenceBundle) -> set[str]:
    # Collect every numeric token that appears anywhere in the evidence.
    tokens = {_norm(m) for m in _NUM.findall(_evidence_text(bundle))}
    # Also allow the % form of any fraction (e.g. -0.152 -> 15.2) plus rounded variants.
    for t in list(tokens):
        try:
            f = float(t)
        except ValueError:
            continue
        tokens.add(_norm(f"{abs(f) * 100:.2f}"))  # 2dp % (e.g. -0.0332 -> 3.32)
        tokens.add(_norm(f"{abs(f) * 100:.1f}"))
        tokens.add(_norm(f"{abs(f) * 100:.0f}"))
        tokens.add(_norm(f"{f:.0f}"))
    return tokens


def _fabricated_magnitudes(bundle: EvidenceBundle, narrative: str) -> list[str]:
    """Scale suffixes and currency symbols the prose added that the evidence never had."""
    evidence = _evidence_text(bundle)
    found: list[str] = []

    for number, suffix in _SCALED.findall(narrative or ""):
        # Only flag when the evidence does not itself pair this number with that suffix.
        if not re.search(rf"{re.escape(number)}\s*{re.escape(suffix)}\b", evidence, re.IGNORECASE):
            found.append(f"{number}{suffix}")

    for symbol, number in _CURRENCY.findall(narrative or ""):
        if symbol not in evidence:
            found.append(f"{symbol}{number}")

    return found


def verify(bundle: EvidenceBundle, narrative: str) -> NarrativeVerification:
    """Fail if any number is absent from the evidence, or is restated at a magnitude the
    evidence does not support."""
    allowed = _bundle_numbers(bundle)
    unverified = sorted(n for n in _numbers(narrative) if n and n not in allowed)
    unverified += sorted(set(_fabricated_magnitudes(bundle, narrative)))
    return NarrativeVerification(passed=not unverified, unverified_numbers=unverified)
