"""E2E: precomputed charts + HTTP URL fallback + plot_anomaly under 1s."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from clickathon.charts import CHART_KINDS, chart_filename, charts_dir, charts_public_base
from clickathon.mcp_server import plot_anomaly
from clickathon.rca_store import list_incidents_from_store
from mcp.types import ImageContent


def main() -> int:
    bag = list_incidents_from_store()
    ids = [str(i["id"]) for i in (bag.get("incidents") or [])]
    if not ids:
        print("FAIL: no incidents")
        return 1

    out_dir = charts_dir()
    missing = [
        chart_filename(iid, kind)
        for iid in ids
        for kind in CHART_KINDS
        if not (out_dir / chart_filename(iid, kind)).is_file()
    ]
    if missing:
        print(f"FAIL: missing PNGs: {missing[:6]}")
        return 1
    print(f"OK pngs={len(ids) * len(CHART_KINDS)} dir={out_dir}")

    base = charts_public_base()
    with httpx.Client(timeout=5.0) as client:
        for iid in ids:
            for kind in CHART_KINDS:
                url = f"{base}/{chart_filename(iid, kind)}"
                t0 = time.perf_counter()
                r = client.get(url)
                ms = (time.perf_counter() - t0) * 1000
                if r.status_code != 200 or r.headers.get("content-type", "").startswith("image") is False and b"PNG" not in r.content[:8]:
                    # Accept image/png or raw PNG magic
                    if r.status_code != 200 or not r.content.startswith(b"\x89PNG"):
                        print(f"FAIL http {url} status={r.status_code} ms={ms:.0f}")
                        return 1
                if ms >= 1000:
                    print(f"WARN http slow {url} {ms:.0f}ms")
                else:
                    print(f"OK http {Path(url).name} {ms:.0f}ms {len(r.content)}B")

    # Cold-ish tool call after imports already done
    times: list[float] = []
    result = None
    for _ in range(3):
        t0 = time.perf_counter()
        result = plot_anomaly(ids[0], "window")
        times.append((time.perf_counter() - t0) * 1000)
    print(f"OK plot_anomaly times_ms={[round(t) for t in times]}")
    if min(times) >= 1000:
        print("FAIL: plot_anomaly >= 1s")
        return 1
    assert result is not None
    parts = list(result.content)
    if not parts or not isinstance(parts[0], ImageContent):
        print(f"FAIL: expected ImageContent, got {type(parts[0]) if parts else None}")
        return 1
    meta = json.loads(parts[1].text)
    assert "markdown" in meta and meta["url"].startswith("http")
    print(f"OK image+markdown fallback: {meta['markdown']}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
