import json
from pathlib import Path

import pytest

from app.schemas.features import ObservedFieldType
from app.tools.event_profiler import (
    EventLineTooLongError,
    EventProfilerConfigurationError,
    InvalidEventError,
    TooManyEventNamesError,
    TooManyFieldsError,
    profile_events,
)


def _write_events(path: Path, events: list[object]) -> Path:
    path.write_text(
        "".join(f"{json.dumps(event)}\n" for event in events), encoding="utf-8"
    )
    return path


def test_profiles_event_names_fields_types_presence_and_examples(
    tmp_path: Path,
) -> None:
    events_path = _write_events(
        tmp_path / "events.ndjson",
        [
            {
                "event_name": "shown",
                "event": "ignored",
                "user_id": 1,
                "amount": 2,
                "channel": "ios",
                "metadata": {"attempt": 1},
            },
            {
                "event": "selected",
                "user_id": 2,
                "amount": 2.5,
                "channel": None,
                "metadata": {"attempt": 2},
            },
            {"type": "shown", "user_id": 2, "amount": None},
            {"name": "paid", "user_id": 3, "amount": 4},
            {"user_id": 3},
        ],
    )

    profile = profile_events(events_path)

    assert profile.event_count == 5
    assert profile.event_names == {"shown": 2, "selected": 1, "paid": 1}
    assert profile.unnamed_event_count == 1

    user_id = profile.fields["user_id"]
    assert user_id.observed_type is ObservedFieldType.INTEGER
    assert user_id.presence_count == 5
    assert user_id.presence == 1.0
    assert user_id.approx_cardinality == 3
    assert user_id.cardinality_is_estimate is False
    assert user_id.examples == [1, 2, 3]

    amount = profile.fields["amount"]
    assert amount.observed_type is ObservedFieldType.FLOAT
    assert amount.observed_types == [
        ObservedFieldType.NULL,
        ObservedFieldType.INTEGER,
        ObservedFieldType.FLOAT,
    ]
    assert amount.presence == pytest.approx(0.8)

    channel = profile.fields["channel"]
    assert channel.observed_type is ObservedFieldType.STRING
    assert channel.observed_types == [
        ObservedFieldType.NULL,
        ObservedFieldType.STRING,
    ]

    metadata = profile.fields["metadata"]
    assert metadata.observed_type is ObservedFieldType.OBJECT
    assert metadata.examples == []


def test_examples_are_distinct_json_scalars_and_capped_at_five(
    tmp_path: Path,
) -> None:
    events_path = _write_events(
        tmp_path / "events.ndjson",
        [{"value": value} for value in [1, 1, 2, 3, 4, 5, 6]],
    )

    profile = profile_events(events_path)

    assert profile.fields["value"].examples == [1, 2, 3, 4, 5]


def test_cardinality_estimate_uses_bounded_sample(tmp_path: Path) -> None:
    events_path = _write_events(
        tmp_path / "events.ndjson", [{"id": value} for value in range(200)]
    )

    profile = profile_events(events_path, cardinality_sample_size=16)

    field = profile.fields["id"]
    assert field.cardinality_is_estimate is True
    assert field.approx_cardinality > 16


def test_blank_lines_are_ignored(tmp_path: Path) -> None:
    events_path = tmp_path / "events.ndjson"
    events_path.write_bytes(b'\n  \r\n{"event": "shown"}\n')

    assert profile_events(events_path).event_count == 1


def test_line_byte_limit_is_checked_before_json_decode(tmp_path: Path) -> None:
    events_path = tmp_path / "events.ndjson"
    events_path.write_bytes(b'{"value":"12345"}\n')

    with pytest.raises(EventLineTooLongError, match="line 1"):
        profile_events(events_path, max_line_bytes=8)


@pytest.mark.parametrize(
    "content", [b"not-json\n", b"[]\n", b'{"x": NaN}\n', b"\xff\n"]
)
def test_invalid_event_lines_have_domain_errors(tmp_path: Path, content: bytes) -> None:
    events_path = tmp_path / "events.ndjson"
    events_path.write_bytes(content)

    with pytest.raises(InvalidEventError, match="line 1"):
        profile_events(events_path)


def test_distinct_field_count_is_bounded(tmp_path: Path) -> None:
    events_path = _write_events(tmp_path / "events.ndjson", [{"a": 1, "b": 2}])

    with pytest.raises(TooManyFieldsError, match="1 distinct-field"):
        profile_events(events_path, max_fields=1)


def test_distinct_event_name_count_is_bounded(tmp_path: Path) -> None:
    events_path = _write_events(
        tmp_path / "events.ndjson", [{"event": "a"}, {"event": "b"}]
    )

    with pytest.raises(TooManyEventNamesError, match="1 distinct"):
        profile_events(events_path, max_event_names=1)


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("max_line_bytes", 0),
        ("cardinality_sample_size", 1),
        ("max_examples", 6),
    ],
)
def test_invalid_limits_have_configuration_error(
    tmp_path: Path, keyword: str, value: int
) -> None:
    events_path = _write_events(tmp_path / "events.ndjson", [])

    with pytest.raises(EventProfilerConfigurationError):
        if keyword == "max_line_bytes":
            profile_events(events_path, max_line_bytes=value)
        elif keyword == "cardinality_sample_size":
            profile_events(events_path, cardinality_sample_size=value)
        else:
            profile_events(events_path, max_examples=value)
