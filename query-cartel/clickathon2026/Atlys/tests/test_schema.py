"""Unit tests — schema inference & DDL builder (Part 9: test_schema.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.schema import (  # noqa: E402
    build_ddl,
    flatten,
    infer_types,
    load_events,
    schema_rationale,
    _slug,
)


# ---------------------------------------------------------------------------
# flatten / load_events
# ---------------------------------------------------------------------------

def test_flatten_nested():
    assert flatten({"payment": {"amount": 5.0, "currency": "INR"}}) == {
        "payment_amount": 5.0, "payment_currency": "INR"
    }


def test_flatten_array_to_string():
    assert flatten({"tags": [1, 2, 3]}) == {"tags": "[1, 2, 3]"}


def test_load_events_skips_malformed(tmp_path):
    f = tmp_path / "e.ndjson"
    f.write_text('{"event": "a"}\nnot json\n{"event": "b"}\n')
    events = load_events(f)
    assert [e["event"] for e in events] == ["a", "b"]


def test_load_events_empty_raises(tmp_path):
    f = tmp_path / "e.ndjson"
    f.write_text("\n\n")
    with pytest.raises(ValueError, match="no valid events"):
        load_events(f)


# ---------------------------------------------------------------------------
# type inference
# ---------------------------------------------------------------------------

def test_infer_bool():
    events = [{"event": "x", "flag": True}, {"event": "x", "flag": False}]
    cols = infer_types(events).columns
    assert cols["flag"] == "UInt8"


def test_infer_int_by_magnitude():
    assert infer_types([{"event": "x", "n": 200}]).columns["n"] == "UInt8"
    assert infer_types([{"event": "x", "n": 300}]).columns["n"] == "UInt16"
    assert infer_types([{"event": "x", "n": 70000}]).columns["n"] == "UInt32"


def test_infer_negative_int_signed():
    assert infer_types([{"event": "x", "n": -5}]).columns["n"] == "Int8"


def test_infer_float():
    assert infer_types([{"event": "x", "v": 4.5}]).columns["v"] == "Float64"


def test_infer_string_default():
    assert infer_types([{"event": "x", "s": "hi"}]).columns["s"] == "String"


def test_infer_nullable_only_where_nulls():
    cols = infer_types([
        {"event": "x", "a": 1, "b": 2},
        {"event": "x", "a": None, "b": 3},
    ]).columns
    assert cols["a"] == "Nullable(UInt8)"
    assert cols["b"] == "UInt8"


def test_infer_mixed_types_string():
    cols = infer_types([
        {"event": "x", "v": 1},
        {"event": "x", "v": "two"},
    ]).columns
    assert cols["v"] == "String"


def test_infer_envelope_types():
    cols = infer_types([
        {"event": "e1", "timestamp": "2026-06-08T06:00:00.000", "id": "a" * 32,
         "user_id": "u1", "os": "iOS"}
    ]).columns
    assert cols["timestamp"] == "DateTime"
    assert cols["id"] == "String"
    assert cols["event"] == "LowCardinality(String)"
    assert cols["user_id"] == "String"
    assert cols["os"] == "LowCardinality(Nullable(String))"


def test_infer_event_order_first_seen():
    inferred = infer_types([
        {"event": "b", "user_id": "u1"},
        {"event": "a", "user_id": "u2"},
        {"event": "b", "user_id": "u3"},
    ])
    assert inferred.event_order == ["b", "a"]


def test_infer_no_user_id():
    inferred = infer_types([{"event": "x"}, {"event": "y"}])
    assert inferred.has_user_id is False


# ---------------------------------------------------------------------------
# DDL builder
# ---------------------------------------------------------------------------

def test_build_ddl_shape():
    cols = infer_types([
        {"event": "shown", "timestamp": "2026-06-08T06:00:00.000", "id": "x" * 32,
         "user_id": "u1", "shown_amount": 4743.0}
    ]).columns
    ddl = build_ddl("express_checkout", cols, ["shown"])
    assert "CREATE TABLE IF NOT EXISTS express_checkout_events" in ddl
    assert "ENGINE = MergeTree" in ddl
    assert "PARTITION BY toYYYYMM(timestamp)" in ddl
    assert "ORDER BY (event, timestamp, user_id)" in ddl
    assert "TTL timestamp + INTERVAL 180 DAY" in ddl
    assert "shown_amount Float64" in ddl  # no nulls in the sample → non-Nullable


def test_build_ddl_drops_nullable_user_id_from_sort_key():
    # sparse user_id (missing in some rows) infers Nullable(String); a
    # Nullable column can't be a MergeTree sort key on default settings, so
    # build_ddl must drop it from ORDER BY (regression: 03_status_sharing).
    cols = infer_types([
        {"event": "status_shared", "timestamp": "2026-06-08T06:00:00.000", "id": "x" * 32,
         "user_id": "u1"},
        {"event": "status_shared", "timestamp": "2026-06-08T06:01:00.000", "id": "y" * 32},
    ]).columns
    assert cols["user_id"] == "Nullable(String)"
    ddl = build_ddl("status_sharing", cols, ["status_shared"])
    assert "ORDER BY (event, timestamp)" in ddl
    assert "ORDER BY (event, timestamp, user_id)" not in ddl


def test_build_ddl_nullable_when_nulls():
    cols = infer_types([
        {"event": "shown", "timestamp": "2026-06-08T06:00:00.000", "id": "x" * 32,
         "user_id": "u1", "otp_success": 1},
        {"event": "shown", "timestamp": "2026-06-08T06:00:00.000", "id": "y" * 32,
         "user_id": "u2", "otp_success": None},
    ]).columns
    ddl = build_ddl("express_checkout", cols, ["shown"])
    assert "otp_success Nullable(UInt8)" in ddl


def test_build_ddl_no_user_id_swaps_order_by():
    cols = infer_types([
        {"event": "x", "timestamp": "2026-06-08T06:00:00.000", "id": "z" * 32}
    ]).columns
    ddl = build_ddl("widget", cols, ["x"])
    assert "ORDER BY (event, timestamp)" in ddl
    assert "user_id" not in ddl


def test_slug():
    assert _slug("01_Express Checkout") == "express_checkout"
    assert _slug("specs/02_group_family") == "group_family"


def test_rationale_mentions_decisions():
    cols = infer_types([
        {"event": "x", "timestamp": "2026-06-08T06:00:00.000", "id": "y" * 32,
         "user_id": "u"}
    ]).columns
    r = schema_rationale("express_checkout", cols, ["x"], 100, True)
    for key in ("order_by", "partition", "ttl", "types", "enums"):
        assert key in r and r[key]
