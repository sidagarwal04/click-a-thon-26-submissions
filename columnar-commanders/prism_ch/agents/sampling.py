"""Sampling event records before they are profiled.

The Instrumentation Agent never profiles a full ndjson dump - a 15% sample is
enough to see every field and a representative spread of values, and it keeps
LLM cost flat however large the file is.

**Sampling happens per user action, after the split.** A flat 15% of the whole
file would under-represent the rarer events: in the express-checkout spec,
`express_payment_confirmed` is 836 rows against `express_checkout_shown`'s
1,650, so one pooled sample gives the smaller table a thinner profile than the
larger one for no reason. Splitting first and sampling each group means every
table's profile is a representative slice of *that* action.

Index-based, not first-N: the head of an event log is usually one moment in
time and one code path, which would give a distorted view of cardinality and
null rates.
"""

from __future__ import annotations

import json
import random
from typing import Any

DEFAULT_SAMPLE_FRACTION = 0.15


def _sample_indices(total: int, fraction: float, seed: int | None) -> list[int]:
    if total == 0:
        return []
    fraction = min(1.0, max(0.0, fraction))
    keep = max(1, round(total * fraction))
    if keep >= total:
        return list(range(total))
    rng = random.Random(seed)
    return sorted(rng.sample(range(total), keep))


def sample_events(
    events: list[dict[str, Any]],
    *,
    fraction: float = DEFAULT_SAMPLE_FRACTION,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Sample an already-parsed list. Used per action group, after the split.

    Never returns empty for a non-empty input: a group of three rows still
    profiles those three, because a table with a thin profile beats a table
    designed from nothing.
    """
    return [events[i] for i in _sample_indices(len(events), fraction, seed)]


def sample_ndjson_text(
    text: str,
    *,
    fraction: float = DEFAULT_SAMPLE_FRACTION,
    seed: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Randomly sample ~`fraction` of records from NDJSON or a JSON array.

    Returns `(sampled_events, total_records_seen)`. Detection mirrors
    `parse_events_text`: try a whole-text JSON parse first (a single object or
    an array), then fall back to one JSON object per line. Unparseable lines
    are skipped, not fatal, same as the unsampled parser.
    """
    text = text.strip()
    if not text:
        return [], 0

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return [parsed], 1

    if isinstance(parsed, list):
        total = len(parsed)
        idx = _sample_indices(total, fraction, seed)
        return [parsed[i] for i in idx if isinstance(parsed[i], dict)], total

    lines = [line.strip().rstrip(",") for line in text.splitlines()]
    lines = [line for line in lines if line]
    total = len(lines)
    idx = _sample_indices(total, fraction, seed)

    events: list[dict[str, Any]] = []
    for i in idx:
        try:
            item = json.loads(lines[i])
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events, total
