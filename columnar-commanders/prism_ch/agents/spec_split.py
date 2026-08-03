"""Splitting one feature spec into one table per user action.

**The spec decides how many tables exist, not the data.** `spec.md` lists the
raw events a feature emits under "User actions"; each becomes its own table,
mirroring how the eight existing Atlys source tables are built - one table per
event, joined on `user_id` / `application_id`. The events file is then
*correlated* onto that list by matching each record's action field.

Reading the spec first, rather than deriving tables from whatever event values
happen to appear, is what makes a mismatch visible: an action the spec promises
but the data never emits is a gap, and an event in the data the spec never
mentions is instrumentation nobody documented. A data-driven split silently
papers over both, and on the unseen spec that is exactly the kind of silence
that costs a table.

Nothing here is specific to a known spec - the section heading, the bullet
shape, and the action field are all discovered, not hardcoded.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# "## User actions (raw events emitted)" - matched on the words, not the exact
# heading, so a spec that phrases it differently still parses.
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
# "- `event_name` — description". The action is the first backticked token;
# everything after it is prose that may name columns in backticks too.
_ACTION = re.compile(r"^\s*[-*]\s+`([A-Za-z0-9_.]+)`")

_SECTION_HINT = "user action"


def parse_user_actions(spec_md: str) -> list[str]:
    """The event names declared under the spec's "User actions" heading.

    Order is preserved and duplicates dropped. Lines that are not bullets -
    the trailing "Events carry the usual raw envelope..." paragraph, or a
    wrapped continuation of the previous bullet - are skipped, so only the
    declared actions come back.
    """
    actions: list[str] = []
    in_section = False

    for line in spec_md.splitlines():
        heading = _HEADING.match(line)
        if heading:
            in_section = _SECTION_HINT in heading.group(1).lower()
            continue
        if not in_section:
            continue
        match = _ACTION.match(line)
        if match and match.group(1) not in actions:
            actions.append(match.group(1))

    return actions


def infer_actions_from_data(
    spec_md: str, events: list[dict[str, Any]], *, field: str = "event"
) -> list[str]:
    """Fallback when no "User actions" heading was found.

    Still spec-led - the data only *proposes* candidates and the spec has to
    confirm each by naming it - but it does not depend on the heading or the
    bullet shape. A brief pasted without its heading, or a sixth spec that
    phrases the section differently, still splits into the right tables.

    An event the spec never mentions is still excluded, which is the property
    that keeps this from collapsing into a data-driven split.
    """
    if not spec_md or not events:
        return []
    text = spec_md.lower()
    seen: list[str] = []
    for event in events:
        value = event.get(field)
        if isinstance(value, str) and value not in seen and value.lower() in text:
            seen.append(value)
    return seen


def flatten_event(event: dict[str, Any], *, sep: str = "_") -> dict[str, Any]:
    """Flatten nested objects into scalar columns: {"payment": {"amount": 1}}
    becomes {"payment_amount": 1}.

    Per `schema-json-when-to-use`, a known fixed shape belongs in typed columns
    - the JSON type is for genuinely dynamic data, and storing a known object
    as an opaque String gives up field-level querying entirely. Lists are left
    alone: a repeated structure is not a fixed shape, so the schema step
    decides what it deserves.
    """
    flat: dict[str, Any] = {}
    for key, value in event.items():
        if isinstance(value, dict) and value:
            for inner, inner_value in flatten_event(value, sep=sep).items():
                flat[f"{key}{sep}{inner}"] = inner_value
        else:
            flat[key] = value
    return flat


def detect_action_field(
    events: list[dict[str, Any]], actions: list[str], *, default: str = "event"
) -> str:
    """Which field carries the action name.

    `event` in every spec seen so far, but the sixth is unseen - so pick the
    field whose values actually match the declared actions rather than trusting
    the convention to hold.
    """
    if not events or not actions:
        return default

    declared = set(actions)
    candidates = {key for event in events[:200] for key in event}
    best, best_hits = default, 0
    for key in sorted(candidates):
        hits = sum(1 for e in events if e.get(key) in declared)
        if hits > best_hits:
            best, best_hits = key, hits
    return best if best_hits else default


def split_by_action(
    events: list[dict[str, Any]], actions: list[str], *, field: str = "event"
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Correlate records onto the declared actions.

    Returns `(groups, undeclared)`. `groups` has one key per declared action in
    spec order, **including actions with no matching rows** - a table the spec
    promises and the data never delivers is a finding, not something to drop
    quietly. `undeclared` counts event values the spec never mentioned.
    """
    groups: dict[str, list[dict[str, Any]]] = {action: [] for action in actions}
    undeclared: Counter[str] = Counter()

    for event in events:
        value = event.get(field)
        if isinstance(value, str) and value in groups:
            groups[value].append(event)
        else:
            undeclared[str(value)] += 1

    return groups, dict(undeclared)
