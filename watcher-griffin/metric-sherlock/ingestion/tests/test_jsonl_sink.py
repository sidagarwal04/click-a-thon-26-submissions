import json
import math

from ingestion.sinks.jsonl_sink import JsonlSink


def test_nan_and_inf_are_sanitized_to_null(tmp_path):
    sink = JsonlSink(str(tmp_path))
    sink.write("apps", [{"record": {"app_id": "app_1", "publisher_tier": float("nan")}, "score": float("inf")}])

    path = tmp_path / "apps.valid.jsonl"
    line = path.read_text(encoding="utf-8").strip()

    # json.loads with strict parsing rejects the literal NaN/Infinity tokens --
    # this only passes if the sink actually sanitized them to null beforehand.
    parsed = json.loads(line, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    assert parsed["record"]["publisher_tier"] is None
    assert parsed["score"] is None
