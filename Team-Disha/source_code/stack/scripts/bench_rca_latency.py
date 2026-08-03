"""Benchmark RCA path latencies (store + optional live investigate)."""

from __future__ import annotations

import time

from clickathon.explain import explain_anomaly_from_store
from clickathon.rca_store import (
    counterfactual_from_store,
    decompose_day_from_store,
    detect_day_from_store,
    expected_baseline_from_store,
    list_incidents_from_store,
)


def timed(label: str, fn):
    t0 = time.perf_counter()
    out = fn()
    ms = (time.perf_counter() - t0) * 1000
    print(f"{label}: {ms:.0f} ms")
    return out, ms


def main() -> None:
    timed("warmup", list_incidents_from_store)

    timed("list_all_anomalies", list_incidents_from_store)
    timed("detect_day 2026-07-01", lambda: detect_day_from_store("2026-07-01"))
    timed("decompose_day 2026-07-01", lambda: decompose_day_from_store("2026-07-01"))
    timed("expected_baseline 2026-07-01", lambda: expected_baseline_from_store("2026-07-01"))
    pack, _ = timed(
        "explain_anomaly F (no LLM)",
        lambda: explain_anomaly_from_store(incident_id="F", include_narrative=False),
    )
    timed("counterfactual F", lambda: counterfactual_from_store(incident_id="F"))

    t0 = time.perf_counter()
    bag = list_incidents_from_store()
    explain_anomaly_from_store(incident_id="F", include_narrative=False)
    counterfactual_from_store(incident_id="F")
    print(f"typical path list+explain+cf: {(time.perf_counter() - t0) * 1000:.0f} ms")
    print(f"catalog count: {bag.get('count')}")
    print(f"explanation chars: {len(pack.get('explanation') or '')}")

    try:
        from clickathon.investigate import investigate

        timed(
            "live investigate 2026-07-01 (may include LLM)",
            lambda: investigate("2026-07-01", narrate=False),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"live investigate skipped: {exc}")


if __name__ == "__main__":
    main()
