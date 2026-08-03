"""Bench plot_anomaly path: precomputed PNG read + optional HTTP /charts serve."""

from __future__ import annotations

import time

from clickathon.charts import (
    chart_url,
    charts_dir,
    load_chart_bytes,
    precompute_all_incident_charts,
)
from clickathon.mcp_server import plot_anomaly
from clickathon.rca_store import list_incidents_from_store


def main() -> None:
    bag = list_incidents_from_store()
    ids = [str(i["id"]) for i in (bag.get("incidents") or [])]
    if not ids:
        print("no incidents — run materialize first")
        return

    t0 = time.perf_counter()
    pre = precompute_all_incident_charts()
    print(f"precompute_all: {(time.perf_counter() - t0) * 1000:.0f} ms → {pre}")

    iid = ids[0]
    for kind in ("window", "factors", "counterfactual"):
        t0 = time.perf_counter()
        data = load_chart_bytes(iid, kind)
        ms = (time.perf_counter() - t0) * 1000
        print(f"load_chart_bytes {iid}/{kind}: {ms:.0f} ms ({len(data)} bytes)")

    t0 = time.perf_counter()
    out = plot_anomaly(iid, "window")
    ms = (time.perf_counter() - t0) * 1000
    n = len(out.content) if hasattr(out, "content") else 0
    print(f"plot_anomaly tool {iid}/window: {ms:.0f} ms parts={n}")
    print(f"charts_dir={charts_dir()}")
    print(f"url={chart_url(iid, 'window')}")
    ok = ms < 1000
    print(f"under_1s={'YES' if ok else 'NO'}")


if __name__ == "__main__":
    main()
