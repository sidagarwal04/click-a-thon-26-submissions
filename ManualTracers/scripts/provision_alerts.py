#!/usr/bin/env python3
"""Render the whole HyperDX detection layer — tiles and alerts — from the registry.

Why this exists: **tile SQL is clock-dependent.** `metric_sql._clock_exprs()` bakes the
bucket, hour-of-day and weekend expressions into the query text at render time, reading
`inmobi.replay_clock`. So every `scripts/compress_replay.py` run invalidates every tile
already saved in ClickStack — they keep scoring on the previous clock and silently stop
matching what the agent computes. Re-provisioning has to be one repeatable command, not a
hand-paste, because it happens again the moment the sealed dataset lands.

Nothing about the detection layer is written down twice: the metric list, the drill order,
the guard rails and the thresholds all come out of `metric_def` / `metric_dim_map`, and the
SQL comes out of the one builder in `RCA/app/metric_sql.py` via `scripts/metric_query.py`.

Three kinds of tile, per docs/RCA_AGENT_DESIGN.md:

  global    one per alertable metric   did the metric itself move?
  marginal  one per metric with dims   did any depth-1 slice move, even if the global
                                       series did not? (measured: the iOS 18.1 incident
                                       scores 0 on the global tile and 8-9 here)
  freshness one, total                 is data still arriving? every deviation alert goes
                                       *silent* when ingest dies, and silence reads as health

Writes the spec to docs/rca_detection_dashboard.json. Applying it needs ClickStack
credentials: with CLICKHOUSE_CLOUD_KEY_ID/_SECRET set, `--apply` pushes over the Cloud API;
without them the JSON is the handoff to the ClickStack MCP.

    ./scripts/provision_alerts.py            # render the spec
    ./scripts/provision_alerts.py --apply    # render and push (needs Cloud API keys)

Depends on nothing outside the standard library, same as metric_query.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "docs" / "rca_detection_dashboard.json"
DASHBOARD_NAME = "RCA Detection"

# The receiver the RCA agent listens on. Created once by hand; referenced by id so this
# script never mints a duplicate webhook on re-run.
WEBHOOK_ID = "6a6debfdca45b0d18a58579f"

# Data is stale once more than this many evaluation intervals have passed with no new rows.
# The freshness query reports in intervals rather than seconds precisely so this number does
# not have to be re-derived when the clock (and with it the alert interval) changes.
FRESHNESS_STALE_INTERVALS = 1

sys.path.insert(0, str(ROOT / "scripts"))
import metric_query  # noqa: E402  (path-loaded, same trick metric_query uses for metric_sql)


def render(mode: str, metric_id: str | None = None) -> str:
    """Shell out to metric_query rather than importing its main().

    It is a CLI whose contract is "prints one query to stdout", and going through that
    contract is what guarantees the SQL provisioned here is byte-identical to the SQL a
    human gets from `./scripts/metric_query.py alert fill_rate` when debugging a tile."""
    cmd = [sys.executable, str(ROOT / "scripts" / "metric_query.py"), mode]
    if metric_id:
        cmd.append(metric_id)
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"metric_query {mode} {metric_id or ''} failed:\n{out.stderr}")
    return out.stdout.strip()


def alertable(env: dict) -> list[dict]:
    """Which metrics get a tile — read from metric_def.alertable, not inferred.

    Alertability is a *measured* property, not a structural one, and that distinction cost a
    round of noise to learn. Deriving it from structure ("has dimensions or has
    dependencies") reads plausibly and is wrong: it puts `ctr` and `render_rate` back on
    tiles, and their separation is ~1x or worse — ctr's noisiest clean day outscores its
    worst real incident, so the tile fires on noise by construction. The calibration lives
    in docs/RCA_AGENT_DESIGN.md 2.2 and is recorded per row in the registry.

    n_dims still comes from metric_dim_map, since it decides whether the metric also gets a
    marginal tile. countDistinctIf, not countDistinct: an unmatched LEFT JOIN row fills a
    String column with '' rather than NULL, so a metric with no drill path would otherwise
    count one dimension and be given a marginal tile over nothing.
    """
    rows = metric_query.query(
        env,
        "SELECT m.metric_id AS metric_id, "
        "  countDistinctIf(d.dim_id, d.dim_id != '') AS n_dims, "
        "  length(m.dependencies) AS n_deps "
        "FROM inmobi.metric_def m FINAL "
        "LEFT JOIN (SELECT metric_id, dim_id FROM inmobi.metric_dim_map FINAL) d "
        "  ON d.metric_id = m.metric_id AND NOT has(m.invalid_dims, d.dim_id) "
        "WHERE m.alertable = 1 "
        "GROUP BY metric_id, n_deps "
        "ORDER BY n_deps DESC, metric_id FORMAT JSONEachRow",
    )
    return [
        {"metric_id": r["metric_id"], "n_dims": int(r["n_dims"])}
        for r in rows
    ]


def build_spec(env: dict) -> dict:
    clock = metric_query.get_clock(env)
    bucket_s = int(clock["bucket_seconds"])
    compressed = bucket_s < 3600

    # ClickStack's interval enum bottoms out at 1m — there is no seconds option, so a
    # compressed replay cannot be alerted on at its own pace. 1m is the floor; at
    # bucket_seconds=2 that is one evaluation per 30 data-hours. metric_sql.lookback_buckets
    # widens the agent's window to match, so nothing the alert scored falls outside what the
    # agent reproduces.
    interval = "1m" if compressed else "1h"

    tiles, alerts = [], []

    def add(name, sql, display, threshold, threshold_type, message):
        key = f"tile-{len(tiles)}"
        tiles.append(
            {
                "key": key,
                "name": name,
                "x": 0,
                "y": len(tiles) * 4,
                "w": 12,
                "h": 4,
                "config": {"configType": "sql", "displayType": display, "sqlTemplate": sql},
            }
        )
        alerts.append(
            {
                "tileKey": key,
                "name": name,
                "source": "tile",
                "threshold": threshold,
                "thresholdType": threshold_type,
                "interval": interval,
                "message": message,
                "channel": {"type": "webhook", "webhookId": WEBHOOK_ID},
            }
        )

    # Ordered so the freshness tile is first: if it is firing, every tile below it is
    # reporting on data that stopped arriving, and nothing under it should be believed.
    add(
        "data freshness",
        render("freshness"),
        "number",
        FRESHNESS_STALE_INTERVALS,
        "above",
        # Deliberately not a metric_def id: main.py will log unknown_metric and skip the
        # investigation. This is an ops signal, not an incident to diagnose.
        "metric_id=freshness scope=ops",
    )

    for m in alertable(env):
        mid = m["metric_id"]
        # above_exclusive, never above: `above` fires unconditionally at zero, which is a
        # real bug that shipped once in a hand-built alert.
        add(
            f"{mid} · global anomalies",
            render("alert", mid),
            "number",
            0,
            "above_exclusive",
            f"metric_id={mid} scope=global",
        )
        if m["n_dims"]:
            # {{group}} and {{value}} ARE available in an alert message, contrary to the
            # webhook body template, which really is limited to {{title}}/{{body}}/{{link}}.
            # A grouped tile fires once per breaching group and substitutes that group here,
            # so the firing slice reaches the agent without one tile per dimension.
            #
            # The tile's group columns are (dim_name, dim_value) in that order, and
            # main.py's DIMENSION_ID_RE captures `(\w+)` — the first word — which is the
            # dimension id and exactly what scan_dims wants as a first-scan hint. If the
            # rendering ever puts the value first, the capture fails registry whitelisting in
            # _dim_col and the scan falls back to the full sweep: degraded, never wrong.
            add(
                f"{mid} · marginal sentinel",
                render("marginal", mid),
                "line",
                0,
                "above_exclusive",
                f"metric_id={mid} scope=marginal dimension_id={{{{group}}}} z={{{{value}}}}",
            )

    return {
        "dashboard": {"name": DASHBOARD_NAME, "tags": ["inmobi", "rca", "detection"]},
        "clock": {"bucket_seconds": bucket_s, "anchor": int(clock["anchor"])},
        "interval": interval,
        "tiles": tiles,
        "alerts": alerts,
    }


def apply_via_cloud_api(env: dict, spec: dict) -> None:
    key_id = env.get("CLICKHOUSE_CLOUD_KEY_ID", "")
    key_secret = env.get("CLICKHOUSE_CLOUD_KEY_SECRET", "")
    if not (key_id and key_secret):
        raise SystemExit(
            "--apply needs CLICKHOUSE_CLOUD_KEY_ID and CLICKHOUSE_CLOUD_KEY_SECRET in .env "
            "(Cloud console -> API Keys, Org or Service Admin).\n"
            f"The spec is written to {SPEC_PATH.relative_to(ROOT)} either way — push it "
            "through the ClickStack MCP instead."
        )

    base = (
        f"https://api.clickhouse.cloud/v1/organizations/{env['CLICKHOUSE_CLOUD_ORG_ID']}"
        f"/services/{env['CLICKSTACK_SERVICE_ID']}/clickstack"
    )

    def api(method, path, body=None):
        """Through curl rather than urllib, deliberately.

        curl verifies against the macOS keychain; Python verifies against certifi. Behind a
        TLS-intercepting proxy the keychain has the interception CA and certifi does not, so
        urllib fails CERTIFICATE_VERIFY_FAILED on a host curl reaches fine. Shelling out is
        the fix that does not involve turning verification off."""
        cmd = [
            "curl", "-sS", "--fail-with-body", "-X", method,
            "-u", f"{key_id}:{key_secret}",
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json",
            base + path,
        ]
        if body is not None:
            cmd += ["--data-binary", "@-"]
        r = subprocess.run(
            cmd,
            input=json.dumps(body) if body is not None else None,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise SystemExit(f"{method} {path} failed: {r.stdout or r.stderr}")
        payload = json.loads(r.stdout) if r.stdout.strip() else {}
        return payload.get("result", payload.get("data", payload))

    # A raw-SQL tile runs against a connection, not a source, and the id is not stable across
    # environments — look it up rather than pinning it. There is no /connections endpoint on
    # the Cloud API and the /sources list omits the field, but fetching one source by id
    # returns it.
    sources = api("GET", "/sources") or []
    connection_id = next(
        (
            c
            for s in sources
            if (c := (api("GET", f"/sources/{s['id']}") or {}).get("connection"))
        ),
        None,
    )
    if not connection_id:
        raise SystemExit("could not resolve a ClickStack connection id from /sources")

    # Replace rather than update: a re-provision after a clock change must not leave tiles
    # rendered on the previous clock behind, and reconciling them by name is more fragile
    # than rebuilding. Alerts go first — deleting a dashboard otherwise orphans its alerts,
    # which then keep evaluating against a tile that no longer exists.
    stale = {
        d["id"]
        for d in (api("GET", "/dashboards") or [])
        if isinstance(d, dict) and d.get("name") == DASHBOARD_NAME
    }
    for a in api("GET", "/alerts") or []:
        if isinstance(a, dict) and a.get("dashboardId") in stale:
            api("DELETE", f"/alerts/{a['id']}")
    for dashboard_id in stale:
        api("DELETE", f"/dashboards/{dashboard_id}")

    dash = api(
        "POST",
        "/dashboards",
        {
            "name": spec["dashboard"]["name"],
            "tags": spec["dashboard"]["tags"],
            "tiles": [
                {k: v for k, v in t.items() if k != "key"}
                | {"config": t["config"] | {"connectionId": connection_id}}
                for t in spec["tiles"]
            ],
        },
    )
    tile_ids = [t["id"] for t in dash["tiles"]]
    for alert, tile_id in zip(spec["alerts"], tile_ids):
        api(
            "POST",
            "/alerts",
            {k: v for k, v in alert.items() if k != "tileKey"}
            | {"dashboardId": dash["id"], "tileId": tile_id},
        )
    print(f"applied: dashboard {dash['id']}, {len(spec['alerts'])} alerts")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="push to ClickStack Cloud API")
    args = ap.parse_args()

    env = metric_query.load_env()
    spec = build_spec(env)
    SPEC_PATH.write_text(json.dumps(spec, indent=2) + "\n")

    print(
        f"clock: bucket_seconds={spec['clock']['bucket_seconds']} -> alert interval "
        f"{spec['interval']}"
    )
    for t, a in zip(spec["tiles"], spec["alerts"]):
        print(
            f"  {t['config']['displayType']:6s} {t['name']:34s} "
            f"{a['thresholdType']} {a['threshold']}   [{a['message']}]"
        )
    print(f"\nspec -> {SPEC_PATH.relative_to(ROOT)}")

    if args.apply:
        apply_via_cloud_api(env, spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
