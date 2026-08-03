"""One table per user action: parsing the spec, correlating the data onto it,
and flattening nested objects into typed columns."""

from __future__ import annotations

import json

from prism_ch.agents.spec_split import (
    detect_action_field,
    flatten_event,
    parse_user_actions,
    split_by_action,
)
from prism_ch.agents.types import load_spec

# The shape every provided spec uses: a "User actions" heading, one backticked
# event per bullet, then a non-bulleted paragraph about the envelope that must
# not be mistaken for an action.
SPEC = """# Feature spec — Express Checkout

## What it does
A one-tap checkout for returning travellers.

## User actions (raw events emitted)

- `express_checkout_shown` — express eligible, button rendered (`shown_amount`, `currency`)
- `otp_entered` — OTP submitted (`otp_attempts`, `otp_success`)
- `express_payment_confirmed` — payment succeeds (nested `payment`: `amount`, `latency_ms`)

Events carry the usual raw envelope (`device_type`, `os`, `geoip_country_code`,
`app_version`, `user_id`).

## Questions the PM will ask
- Does Express lift conversion?
"""


# --- parsing the spec ---------------------------------------------------------


def test_actions_come_from_the_spec_in_order() -> None:
    assert parse_user_actions(SPEC) == [
        "express_checkout_shown",
        "otp_entered",
        "express_payment_confirmed",
    ]


def test_the_envelope_paragraph_is_not_an_action() -> None:
    """It names columns in backticks too, but it is prose, not a bullet."""
    assert "device_type" not in parse_user_actions(SPEC)
    assert "app_version" not in parse_user_actions(SPEC)


def test_columns_named_later_in_a_bullet_are_not_actions() -> None:
    """Only the *first* backticked token on a bullet is the event name."""
    actions = parse_user_actions(SPEC)
    assert "shown_amount" not in actions
    assert "otp_attempts" not in actions


def test_a_wrapped_bullet_does_not_produce_a_second_action() -> None:
    spec = (
        "## User actions\n"
        "- `abandonment_detected` — a drop is detected (`drop_step`: card_clicked\n"
        "  / application_started / document_uploaded)\n"
        "- `reminder_sent` — a nudge is sent\n"
    )
    assert parse_user_actions(spec) == ["abandonment_detected", "reminder_sent"]


def test_bullets_outside_the_section_are_ignored() -> None:
    assert parse_user_actions("## What it does\n- `not_an_event` — prose\n") == []


def test_a_spec_with_no_user_actions_section_yields_nothing() -> None:
    assert parse_user_actions("# Feature\n\nJust prose, no event list.\n") == []


# --- flattening ---------------------------------------------------------------


def test_nested_object_becomes_one_column_per_leaf() -> None:
    flat = flatten_event({"event": "x", "payment": {"amount": 5.0, "latency_ms": 12}})
    assert flat == {"event": "x", "payment_amount": 5.0, "payment_latency_ms": 12}


def test_flattening_is_recursive() -> None:
    flat = flatten_event({"a": {"b": {"c": 1}}})
    assert flat == {"a_b_c": 1}


def test_lists_are_left_alone() -> None:
    """A repeated structure is not a fixed shape - the schema step decides."""
    flat = flatten_event({"tags": ["a", "b"]})
    assert flat == {"tags": ["a", "b"]}


def test_a_flat_event_is_unchanged() -> None:
    event = {"event": "x", "user_id": "u1"}
    assert flatten_event(event) == event


# --- correlating data onto the declared actions -------------------------------


def _events() -> list[dict]:
    return (
        [{"event": "express_checkout_shown", "i": i} for i in range(10)]
        + [{"event": "otp_entered", "i": i} for i in range(4)]
        + [{"event": "undeclared_thing", "i": 1}]
    )


def test_rows_are_grouped_by_their_declared_action() -> None:
    groups, _ = split_by_action(_events(), parse_user_actions(SPEC))
    assert len(groups["express_checkout_shown"]) == 10
    assert len(groups["otp_entered"]) == 4


def test_a_declared_action_with_no_rows_still_gets_a_group() -> None:
    """A table the spec promises and the data never delivers is a finding."""
    groups, _ = split_by_action(_events(), parse_user_actions(SPEC))
    assert "express_payment_confirmed" in groups
    assert groups["express_payment_confirmed"] == []


def test_events_the_spec_never_declared_are_reported_not_grouped() -> None:
    groups, undeclared = split_by_action(_events(), parse_user_actions(SPEC))
    assert "undeclared_thing" not in groups
    assert undeclared == {"undeclared_thing": 1}


def test_group_order_follows_the_spec_not_the_data() -> None:
    groups, _ = split_by_action(_events(), parse_user_actions(SPEC))
    assert list(groups) == parse_user_actions(SPEC)


def test_the_action_field_is_detected_not_assumed() -> None:
    """`event` in every spec so far - the sixth is unseen."""
    events = [{"action_name": "otp_entered"}, {"action_name": "otp_entered"}]
    assert detect_action_field(events, ["otp_entered"]) == "action_name"


def test_action_field_falls_back_when_nothing_matches() -> None:
    assert detect_action_field([{"x": 1}], ["otp_entered"]) == "event"


# --- end to end through load_spec ---------------------------------------------


def _write_spec(tmp_path, events):  # noqa: ANN001
    d = tmp_path / "spec_dir"
    d.mkdir()
    (d / "spec.md").write_text(SPEC)
    (d / "events.ndjson").write_text("\n".join(json.dumps(e) for e in events))
    return d


def test_load_spec_builds_one_group_per_action(tmp_path) -> None:  # noqa: ANN001
    spec = load_spec(str(_write_spec(tmp_path, _events())), sample_fraction=1.0)
    assert [g.action for g in spec.groups] == parse_user_actions(SPEC)


def test_each_group_is_sampled_from_its_own_rows(tmp_path) -> None:  # noqa: ANN001
    """The point of sampling after the split: a rare action is not thinned
    against the volume of a common one."""
    events = (
        [{"event": "express_checkout_shown", "i": i} for i in range(1000)]
        + [{"event": "otp_entered", "i": i} for i in range(100)]
    )
    spec = load_spec(str(_write_spec(tmp_path, events)), sample_fraction=0.15)
    by_action = {g.action: g for g in spec.groups}

    assert by_action["express_checkout_shown"].total == 1000
    assert by_action["otp_entered"].total == 100
    # Each group keeps ~15% of *itself*, not 15% of the pooled file.
    assert 130 <= len(by_action["express_checkout_shown"].events) <= 170
    assert 10 <= len(by_action["otp_entered"].events) <= 20


def test_every_group_loads_all_of_its_rows(tmp_path) -> None:  # noqa: ANN001
    """Sampling bounds what the LLM reads, never what reaches the table."""
    spec = load_spec(str(_write_spec(tmp_path, _events())), sample_fraction=0.15)
    by_action = {g.action: g for g in spec.groups}
    assert len(by_action["express_checkout_shown"].load_events) == 10
    assert len(by_action["otp_entered"].load_events) == 4


def test_load_spec_flattens_before_splitting(tmp_path) -> None:  # noqa: ANN001
    events = [
        {"event": "express_payment_confirmed", "payment": {"amount": 5.0, "latency_ms": 12}}
    ]
    spec = load_spec(str(_write_spec(tmp_path, events)), sample_fraction=1.0)
    row = next(g for g in spec.groups if g.action == "express_payment_confirmed").events[0]
    assert row["payment_amount"] == 5.0
    assert "payment" not in row


def test_a_spec_without_its_heading_still_splits() -> None:
    """The bullets pasted on their own, or a sixth spec that phrases its
    section differently. Still spec-led: the data proposes, the spec confirms."""
    from prism_ch.agents.types import build_spec

    bullets = "- `express_checkout_shown` — rendered\n- `otp_entered` — submitted\n"
    events = "\n".join(
        json.dumps(e)
        for e in [{"event": "express_checkout_shown"}, {"event": "otp_entered"}]
    )
    spec = build_spec(name="ec", brief=bullets, raw_events=events, sample_fraction=1.0)

    assert spec.action_source == "mentioned"
    assert [g.action for g in spec.groups] == ["express_checkout_shown", "otp_entered"]


def test_the_fallback_still_excludes_events_the_spec_never_mentions() -> None:
    """Otherwise it would collapse into the data-driven split we rejected."""
    from prism_ch.agents.types import build_spec

    events = "\n".join(
        json.dumps(e) for e in [{"event": "otp_entered"}, {"event": "secret_ping"}]
    )
    spec = build_spec(
        name="ec", brief="- `otp_entered` — submitted", raw_events=events, sample_fraction=1.0
    )

    assert [g.action for g in spec.groups] == ["otp_entered"]
    assert spec.undeclared_actions == {"secret_ping": 1}


def test_no_spec_text_is_reported_not_silently_one_table() -> None:
    """A single table that should have been five is the failure that looks
    like success - `action_source` is what makes it visible."""
    from prism_ch.agents.types import build_spec

    events = json.dumps({"event": "otp_entered"})
    spec = build_spec(name="ec", brief="", raw_events=events, sample_fraction=1.0)

    assert spec.action_source == "none"
    assert spec.groups == []


def test_a_parsed_heading_is_preferred_over_the_fallback() -> None:
    from prism_ch.agents.types import build_spec

    events = json.dumps({"event": "otp_entered"})
    spec = build_spec(name="ec", brief=SPEC, raw_events=events, sample_fraction=1.0)
    assert spec.action_source == "heading"


def test_load_spec_reports_undeclared_events(tmp_path) -> None:  # noqa: ANN001
    spec = load_spec(str(_write_spec(tmp_path, _events())), sample_fraction=1.0)
    assert spec.undeclared_actions == {"undeclared_thing": 1}
    assert spec.empty_groups == ["express_payment_confirmed"]
