#!/usr/bin/env python3
"""Create InMobi source + dashboard on Managed ClickStack (ClickHouse Cloud API).

Requires in .env:
  CLICKHOUSE_CLOUD_KEY_ID
  CLICKHOUSE_CLOUD_KEY_SECRET
  CLICKHOUSE_CLOUD_ORG_ID
  CLICKSTACK_SERVICE_ID

Optional: reads docs/inmobi_dashboard_import.json for tiles/source.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT_PATH = ROOT / "docs" / "inmobi_dashboard_import.json"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

KEY_ID = os.environ.get("CLICKHOUSE_CLOUD_KEY_ID", "").strip()
KEY_SECRET = os.environ.get("CLICKHOUSE_CLOUD_KEY_SECRET", "").strip()
ORG_ID = os.environ.get("CLICKHOUSE_CLOUD_ORG_ID", "").strip()
SERVICE_ID = os.environ.get("CLICKSTACK_SERVICE_ID", "").strip()
TEAM_ID = os.environ.get("CLICKSTACK_TEAM_ID", "").strip()

missing = [
    name
    for name, val in [
        ("CLICKHOUSE_CLOUD_KEY_ID", KEY_ID),
        ("CLICKHOUSE_CLOUD_KEY_SECRET", KEY_SECRET),
        ("CLICKHOUSE_CLOUD_ORG_ID", ORG_ID),
        ("CLICKSTACK_SERVICE_ID", SERVICE_ID),
    ]
    if not val
]
if missing:
    print(
        "Missing in .env: " + ", ".join(missing) + "\n\n"
        "1. Open https://console.clickhouse.cloud → API Keys\n"
        "2. Create key with Org Admin or Service Admin on Manual Tracers\n"
        "3. Paste into .env:\n"
        "     CLICKHOUSE_CLOUD_KEY_ID=...\n"
        "     CLICKHOUSE_CLOUD_KEY_SECRET=...\n"
        "4. Re-run: python3 scripts/provision_clickstack_cloud.py\n"
        f"(org={ORG_ID or '?'} service={SERVICE_ID or '?'} team={TEAM_ID or '?'})",
        file=sys.stderr,
    )
    sys.exit(2)

BASE = (
    f"https://api.clickhouse.cloud/v1/organizations/{ORG_ID}"
    f"/services/{SERVICE_ID}/clickstack"
)


def api(method: str, path: str, body: dict | None = None):
    token = base64.b64encode(f"{KEY_ID}:{KEY_SECRET}".encode()).decode()
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"HTTP {e.code} {method} {path}: {err}", file=sys.stderr)
        raise


def unwrap(payload):
    if isinstance(payload, dict):
        if "data" in payload:
            return payload["data"]
        if "result" in payload:
            return payload["result"]
    return payload


def main() -> None:
    imp = json.loads(IMPORT_PATH.read_text())
    source_spec = imp["source"]
    dash_spec = imp["dashboard"]

    print(f"API base: {BASE}")
    print("Listing connections...")
    connection_id = None
    try:
        _, conns = api("GET", "/connections")
        cdata = unwrap(conns) or []
        if isinstance(cdata, list) and cdata:
            connection_id = cdata[0].get("id")
            print(f"  using connection {connection_id} ({cdata[0].get('name')})")
        else:
            print("  no connections listed:", json.dumps(conns)[:300])
    except Exception as e:
        print("  /connections not available:", e)

    if not connection_id and "connection" in imp:
        print("Creating connection from import JSON...")
        try:
            _, created = api("POST", "/connections", imp["connection"])
            connection_id = unwrap(created).get("id")
            print(f"  created {connection_id}")
        except Exception as e:
            print("  connection create failed:", e)

    print("Listing sources...")
    _, sources = api("GET", "/sources")
    src_list = unwrap(sources) or []
    if not isinstance(src_list, list):
        src_list = []
    source_id = None
    for s in src_list:
        frm = s.get("from") or {}
        if s.get("name") == source_spec["name"] or (
            frm.get("databaseName") == "inmobi"
            and frm.get("tableName") == "ad_events_enriched"
        ):
            source_id = s.get("id")
            print(f"  reuse source {source_id} ({s.get('name')})")
            break

    if not source_id:
        body = dict(source_spec)
        if connection_id:
            body["connection"] = connection_id
        print("Creating source...")
        _, created = api("POST", "/sources", body)
        source_id = unwrap(created).get("id")
        print(f"  created source {source_id}")

    # Stamp tiles with source/connection ids
    tiles = []
    for t in dash_spec["tiles"]:
        tile = {
            "name": t["name"],
            "x": t["x"],
            "y": t["y"],
            "w": t["w"],
            "h": t["h"],
            "config": dict(t["config"]),
        }
        cfg = tile["config"]
        if source_id:
            cfg["sourceId"] = source_id
        if connection_id and cfg.get("configType") == "sql":
            cfg["connectionId"] = connection_id
        tiles.append(tile)

    dashboard = {
        "name": dash_spec["name"],
        "tags": dash_spec.get("tags") or ["inmobi"],
        "tiles": tiles,
    }

    print("Validating dashboard...")
    try:
        _, val = api("POST", "/dashboards/validate", dashboard)
        print("  validate:", json.dumps(val)[:500])
        if isinstance(val, dict) and val.get("valid") is False:
            print("VALIDATION FAILED", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print("  validate skipped:", e)

    # Replace prior same-named dashboards
    _, dashes = api("GET", "/dashboards")
    for d in unwrap(dashes) or []:
        if isinstance(d, dict) and d.get("name") == dashboard["name"]:
            print(f"Deleting old dashboard {d.get('id')}")
            api("DELETE", f"/dashboards/{d['id']}")

    print("Creating dashboard...")
    _, created = api("POST", "/dashboards", dashboard)
    dash = unwrap(created)
    print(
        json.dumps(
            {
                "id": dash.get("id") if isinstance(dash, dict) else None,
                "name": dash.get("name") if isinstance(dash, dict) else dash,
                "tiles": len(dash.get("tiles", [])) if isinstance(dash, dict) else None,
            },
            indent=2,
        )
    )
    print("\nDone. Open ClickStack for service Manual Tracers.")
    print("Time range: 2026-06-01 → 2026-07-06")


if __name__ == "__main__":
    main()
