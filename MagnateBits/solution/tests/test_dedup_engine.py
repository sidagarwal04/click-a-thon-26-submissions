"""Trap F — dedup/backfill engine selection (ported from `loop`, generalized).

Proves: when the events carry a re-ingestion/backfill signal column (detected by SHAPE,
not by an Atlys-specific literal), the instrumentation agent selects ReplacingMergeTree so
re-ingested rows collapse; otherwise plain MergeTree, with the check recorded either way.
Generic -> fires on an unseen spec that carries such a column.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import profile as profile_mod
import ddl as ddl_mod
from agents.instrumentation import _dedup_engine, build_fallback_proposal


# ── unit: shape detection, no ClickHouse ──────────────────────────────────────
def test_detects_duplicate_id():
    eng, why = _dedup_engine({"event", "timestamp", "user_id", "duplicate_id"},
                             ["event", "timestamp", "user_id"])
    assert eng == "ReplacingMergeTree(timestamp)"
    assert "duplicate_id" in why


def test_detects_backfill_variants():
    for col in ("is_back_filled", "backfilled", "back_fill", "row_reingested", "dedup_key"):
        eng, _ = _dedup_engine({"event", "timestamp", col}, ["event", "timestamp"])
        assert eng.startswith("ReplacingMergeTree"), f"{col} not detected"


def test_no_signal_stays_mergetree():
    eng, why = _dedup_engine({"event", "timestamp", "user_id", "device_type"},
                             ["event", "timestamp", "user_id"])
    assert eng == "MergeTree"
    assert "no dedup" in why.lower() and "check ran" in why.lower()


def test_signal_without_timestamp_is_keyless_replacing():
    eng, _ = _dedup_engine({"event", "duplicate_id"}, ["event"])
    assert eng == "ReplacingMergeTree"


def test_not_hardcoded_to_atlys():
    # a generic name the 5 known specs never use must still be caught by shape
    eng, _ = _dedup_engine({"event", "timestamp", "dedup_marker"}, ["event", "timestamp"])
    assert eng.startswith("ReplacingMergeTree")


def test_substring_variants_and_no_false_positives():
    # substring variants of the signal words must fire ...
    for col in ("is_duplicate", "user_deduplicated_flag", "row_reingested", "back_filled"):
        eng, _ = _dedup_engine({"event", "timestamp", col}, ["event", "timestamp"])
        assert eng.startswith("ReplacingMergeTree"), f"{col} missed"
    # ... but lookalikes that merely share letters must NOT (duration/backup/dupe-free)
    for col in ("duration_ms", "backup_count", "dupe_free_note", "device_type"):
        eng, _ = _dedup_engine({"event", "timestamp", col}, ["event", "timestamp"])
        assert eng == "MergeTree", f"{col} false-positive"


# ── integration: full fallback proposal must lint clean + dry-run on a dup spec ──
def _spec_with(rows: list[dict]) -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "spec.md").write_text(
        "# Feature spec - X\n## User actions\n- `a_shown` - a\n- `a_done` - b\n"
        "## Questions the PM will ask\n- rate by device_type?\n"
    )
    (d / "events.ndjson").write_text("\n".join(json.dumps(r) for r in rows))
    return d


def test_dup_spec_produces_replacing_and_lints_clean():
    rows = [
        {
            "event": ["a_shown", "a_done"][i % 2],
            "id": f"{i:032x}",
            "timestamp": "2026-06-08T06:%02d:00.000" % (i % 60),
            "user_id": f"u{i % 40}",
            "device_type": ["ios", "android"][i % 2],
            "duplicate_id": "" if i % 5 else f"dup{i}",
        }
        for i in range(200)
    ]
    prop = build_fallback_proposal(profile_mod.profile_spec(*_spec_paths(_spec_with(rows))))
    assert prop.engine.startswith("ReplacingMergeTree")
    assert prop.rationale.get("engine")
    assert ddl_mod.lint(prop) == [], "dedup proposal should lint clean"


def _spec_paths(d: Path) -> tuple[Path, Path]:
    return d / "spec.md", d / "events.ndjson"


def test_version_column_type_guarded():
    """P3: ReplacingMergeTree version must be a temporal/numeric column, never a String."""
    from agents.instrumentation import _dedup_engine
    # String-typed timestamp -> keyless Replacing (not an invalid ReplacingMergeTree(timestamp))
    eng, _ = _dedup_engine(
        {"event", "timestamp", "duplicate_id"}, ["event", "timestamp"],
        col_types={"timestamp": "LowCardinality(String)", "duplicate_id": "String",
                   "event": "LowCardinality(String)"})
    assert eng == "ReplacingMergeTree"
    # temporal timestamp -> versioned Replacing
    eng2, _ = _dedup_engine(
        {"event", "timestamp", "duplicate_id"}, ["event", "timestamp"],
        col_types={"timestamp": "DateTime64(3)", "duplicate_id": "String"})
    assert eng2 == "ReplacingMergeTree(timestamp)"
