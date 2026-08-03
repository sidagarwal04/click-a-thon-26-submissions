"""File-level sampling: the step the Instrumentation Agent runs before
profiling, so it never parses a full ndjson dump into memory."""

from __future__ import annotations

import json

from prism_ch.agents.sampling import sample_ndjson_text


def _ndjson(n: int) -> str:
    return "\n".join(json.dumps({"i": i}) for i in range(n))


def test_keeps_roughly_the_requested_fraction() -> None:
    events, total = sample_ndjson_text(_ndjson(1000), fraction=0.15, seed=1)
    assert total == 1000
    assert 100 <= len(events) <= 200  # 15% +/- rounding


def test_sampling_is_reproducible_with_a_seed() -> None:
    text = _ndjson(500)
    first, _ = sample_ndjson_text(text, fraction=0.15, seed=42)
    second, _ = sample_ndjson_text(text, fraction=0.15, seed=42)
    assert first == second


def test_different_seeds_usually_sample_differently() -> None:
    text = _ndjson(500)
    first, _ = sample_ndjson_text(text, fraction=0.15, seed=1)
    second, _ = sample_ndjson_text(text, fraction=0.15, seed=2)
    assert first != second


def test_small_file_keeps_at_least_one_record() -> None:
    events, total = sample_ndjson_text(_ndjson(3), fraction=0.15, seed=1)
    assert total == 3
    assert len(events) >= 1


def test_fraction_at_or_above_one_keeps_everything() -> None:
    events, total = sample_ndjson_text(_ndjson(50), fraction=1.0)
    assert len(events) == total == 50


def test_json_array_is_sampled_by_element_not_by_line() -> None:
    payload = json.dumps([{"i": i} for i in range(200)])
    events, total = sample_ndjson_text(payload, fraction=0.15, seed=1)
    assert total == 200
    assert 20 <= len(events) <= 40


def test_single_json_object_is_one_record_unsampled() -> None:
    events, total = sample_ndjson_text(json.dumps({"a": 1}), fraction=0.15)
    assert events == [{"a": 1}]
    assert total == 1


def test_unparseable_lines_are_skipped_not_fatal() -> None:
    text = "\n".join([json.dumps({"i": 1}), "not json", json.dumps({"i": 2})])
    events, total = sample_ndjson_text(text, fraction=1.0)
    assert total == 3  # counted as a record seen, even though it failed to parse
    assert events == [{"i": 1}, {"i": 2}]


def test_empty_text_yields_nothing() -> None:
    events, total = sample_ndjson_text("")
    assert events == []
    assert total == 0


# --- load_spec: profiling gets the sample, loading gets everything -------------


def test_load_spec_keeps_the_full_file_separately_for_loading(tmp_path) -> None:  # noqa: ANN001
    from prism_ch.agents.types import load_spec

    spec_dir = tmp_path / "my_spec"
    spec_dir.mkdir()
    (spec_dir / "spec.md").write_text("a feature")
    (spec_dir / "events.ndjson").write_text(_ndjson(1000))

    spec = load_spec(str(spec_dir), sample_fraction=0.15)

    assert spec.sampled
    assert len(spec.events) < 1000  # the sample, for profiling/design
    assert spec.load_events is not None
    assert len(spec.load_events) == 1000  # everything, for the real INSERT


def test_load_spec_without_sampling_has_no_separate_load_set(tmp_path) -> None:  # noqa: ANN001
    """sample_fraction=None (or >=1.0) is the old behaviour: events IS the
    full file, and there is nothing extra to carry alongside it."""
    from prism_ch.agents.types import load_spec

    spec_dir = tmp_path / "my_spec"
    spec_dir.mkdir()
    (spec_dir / "spec.md").write_text("a feature")
    (spec_dir / "events.ndjson").write_text(_ndjson(50))

    spec = load_spec(str(spec_dir), sample_fraction=None)

    assert len(spec.events) == 50
    assert spec.load_events is None


def test_load_spec_with_only_a_brief_has_no_load_set() -> None:
    from prism_ch.agents.types import load_spec

    spec = load_spec(brief="just a description, no events file")

    assert spec.events == []
    assert spec.load_events is None
