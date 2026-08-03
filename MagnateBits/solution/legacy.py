"""T4 · Legacy projection remediation.

The eight production tables all ship `ORDER BY (id, timestamp, user_id)` -- the
anti-pattern `house_rules.md §2` forbids for new tables, and the Context Agent
already flags as a `stale_entry`. Rewriting those tables is a non-starter in
production. The right answer is a projection: a second physical sort order the
optimizer can pick, measured before/after.

    python legacy.py                         # remediate the largest id-leading table
    python legacy.py --table pay_now_clicked # pick one
    python legacy.py --dry-run               # propose + measure baseline only
"""

from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path
from typing import Any

from ch import CH
from contextlayer.checks import Reality

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "legacy_projection.md"

# Representative query shape for the standing Atlys funnel: filter by day + device,
# never by id. This is exactly the access pattern the id-leading sort key punishes.
# Window is derived from the table's own max(timestamp) -- `now() - 30 days` would
# miss a historical dump whose last event is weeks earlier than wall-clock "today".
# The device_type equality is load-bearing: the projection's ORDER BY leads with
# (toDate(timestamp), device_type, ...), so the optimizer can prune by device;
# the primary key (id, timestamp, user_id) cannot.
PROBE_SQL = """
SELECT
    toDate(timestamp) AS day,
    device_type,
    uniqIf(user_id, user_id IS NOT NULL AND toString(user_id) != '') AS users
FROM {table}
WHERE timestamp >= (SELECT max(timestamp) - INTERVAL 30 DAY FROM {table})
  AND device_type = (
        SELECT device_type FROM {table}
        WHERE device_type IS NOT NULL AND toString(device_type) != ''
        GROUP BY device_type ORDER BY count() DESC LIMIT 1
      )
GROUP BY day, device_type
ORDER BY day, device_type
LIMIT 200
"""

PROJECTION_NAME = "p_funnel"
PROJECTION_DDL = (
    "ADD PROJECTION {name} (\n"
    "  SELECT *\n"
    "  ORDER BY (toDate(timestamp), device_type, user_id)\n"
    ")"
)


def _qid(tag: str) -> str:
    return f"legacy_{tag}_{uuid.uuid4().hex[:12]}"


def id_leading_tables(ch: CH) -> list[dict[str, Any]]:
    """Tables whose primary sorting key starts with an identity column."""
    reality = Reality(ch)
    out: list[dict[str, Any]] = []
    for name, key in reality.sorting_keys.items():
        lead = (key or "").split(",")[0].strip().strip("`")
        if lead != "id" and not lead.endswith("_id"):
            continue
        # Skip our own feature/ops tables -- this tool remediates the legacy eight.
        if name.startswith(
            ("f_", "agg_", "mv_", "bake_", "context", "pipeline", "insight", "schema", "contradiction")
        ):
            continue
        rows = ch.run_select(
            f"SELECT total_rows AS n, total_bytes AS b FROM system.tables "
            f"WHERE database = currentDatabase() AND name = '{name}'"
        )
        n = int(rows[0]["n"]) if rows else 0
        b = int(rows[0]["b"]) if rows else 0
        out.append({"name": name, "sorting_key": key, "rows": n, "bytes": b})
    out.sort(key=lambda r: r["rows"], reverse=True)
    return out


def _has_projection(ch: CH, table: str, name: str) -> bool:
    rows = ch.run_select(
        f"SELECT name FROM system.projections "
        f"WHERE database = currentDatabase() AND table = '{table}' AND name = '{name}'"
    )
    return bool(rows)


def _explain(ch: CH, sql: str, *, use_projection: bool | None = None) -> str:
    settings: dict[str, Any] = {}
    if use_projection is True:
        settings = {"optimize_use_projections": 1, "force_optimize_projection": 1}
    elif use_projection is False:
        settings = {"optimize_use_projections": 0}
    try:
        rows = ch.run_select(
            f"EXPLAIN indexes=1 {sql.strip().rstrip(';')}", max_rows=200, settings=settings
        )
        return "\n".join(str(next(iter(r.values()))) for r in rows)
    except Exception as exc:  # noqa: BLE001
        return f"(EXPLAIN failed: {exc})"


def _measure(
    ch: CH, sql: str, tag: str, *, use_projection: bool | None = None
) -> dict[str, int]:
    settings: dict[str, Any] = {}
    if use_projection is True:
        settings = {"optimize_use_projections": 1, "force_optimize_projection": 1}
    elif use_projection is False:
        settings = {"optimize_use_projections": 0}
    qid = _qid(tag)
    ch.run_select(sql, max_rows=200, settings=settings)  # warm
    ch.run_select(sql, max_rows=200, query_id=qid, settings=settings)
    return ch.query_stats(qid, timeout_s=8.0) or {
        "read_rows": 0, "read_bytes": 0, "query_duration_ms": 0, "memory_usage": 0
    }


def _wait_mutations(ch: CH, table: str, timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        muts = ch.run_select(
            f"SELECT count() AS n FROM system.mutations "
            f"WHERE database = currentDatabase() AND table = '{table}' AND is_done = 0"
        )
        if not muts or int(muts[0]["n"]) == 0:
            return
        time.sleep(1.0)


def remediate(ch: CH, table: str, *, dry_run: bool = False) -> dict[str, Any]:
    sql = PROBE_SQL.format(table=table)

    # Baseline must be against the primary key alone. If a previous run left the
    # projection in place, drop it first so "before" is honest.
    if _has_projection(ch, table, PROJECTION_NAME) and not dry_run:
        ch.execute_ddl(f"ALTER TABLE {table} DROP PROJECTION IF EXISTS {PROJECTION_NAME}")
        _wait_mutations(ch, table)

    before_explain = _explain(ch, sql, use_projection=False)
    before = _measure(ch, sql, "before", use_projection=False)

    added = False
    materialized = False
    if not dry_run:
        ddl = f"ALTER TABLE {table} " + PROJECTION_DDL.format(name=PROJECTION_NAME)
        ch.execute_ddl(ddl)
        added = True
        ch.execute_ddl(f"ALTER TABLE {table} MATERIALIZE PROJECTION {PROJECTION_NAME}")
        materialized = True
        _wait_mutations(ch, table)

    after_explain = _explain(ch, sql, use_projection=True) if not dry_run else ""
    after = (
        _measure(ch, sql, "after", use_projection=True)
        if not dry_run
        else {"read_rows": 0, "read_bytes": 0, "query_duration_ms": 0, "memory_usage": 0}
    )

    before_b = int(before.get("read_bytes", 0))
    after_b = int(after.get("read_bytes", 0))
    ratio = (before_b / after_b) if after_b > 0 else 0.0

    return {
        "table": table,
        "dry_run": dry_run,
        "projection": PROJECTION_NAME,
        "added": added,
        "materialized": materialized,
        "before": before,
        "after": after,
        "ratio": ratio,
        "before_explain": before_explain,
        "after_explain": after_explain,
        "probe_sql": sql.strip(),
        "projection_ddl": f"ALTER TABLE {table} " + PROJECTION_DDL.format(name=PROJECTION_NAME),
    }


def render_markdown(result: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    b, a = result["before"], result["after"]
    lines = [
        "# Legacy projection remediation",
        "",
        "The Context Agent flags every id-leading `ORDER BY` as a `stale_entry`.",
        "This tool prices the defect and applies the production-safe fix: a projection,",
        "not a table rewrite.",
        "",
        "## Id-leading tables detected",
        "",
        "| table | sorting_key | rows | bytes |",
        "| --- | --- | ---: | ---: |",
    ]
    for c in candidates:
        lines.append(
            f"| `{c['name']}` | `{c['sorting_key']}` | {c['rows']:,} | {c['bytes']:,} |"
        )
    lines += [
        "",
        f"## Remediated: `{result['table']}`",
        "",
        "```sql",
        result["projection_ddl"],
        f"ALTER TABLE {result['table']} MATERIALIZE PROJECTION {result['projection']};",
        "```",
        "",
        "### Probe query",
        "",
        "```sql",
        result["probe_sql"],
        "```",
        "",
        "### Measured cost",
        "",
        f"| | read_rows | read_bytes | duration_ms |",
        f"| --- | ---: | ---: | ---: |",
        f"| before (primary key) | {b.get('read_rows', 0):,} | {b.get('read_bytes', 0):,} | {b.get('query_duration_ms', 0):,} |",
        f"| after (projection) | {a.get('read_rows', 0):,} | {a.get('read_bytes', 0):,} | {a.get('query_duration_ms', 0):,} |",
        "",
        f"**Ratio:** {result['ratio']:.2f}× fewer bytes read after materialising `{result['projection']}`."
        if result["ratio"] > 0
        else "**Ratio:** n/a (dry-run or zero after-bytes).",
        "",
        "### EXPLAIN before",
        "",
        "```",
        result["before_explain"][:4000],
        "```",
        "",
        "### EXPLAIN after",
        "",
        "```",
        result["after_explain"][:4000],
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", help="legacy table to remediate (default: largest id-leading)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    ch = CH()
    candidates = id_leading_tables(ch)
    if not candidates:
        print("no id-leading MergeTree tables found")
        return 1

    table = args.table or candidates[0]["name"]
    if table not in {c["name"] for c in candidates}:
        print(f"{table} is not an id-leading table; candidates: {[c['name'] for c in candidates]}")
        return 1

    print(f"remediating {table} (dry_run={args.dry_run}) ...")
    result = remediate(ch, table, dry_run=args.dry_run)
    md = render_markdown(result, candidates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")

    print(f"before: {result['before'].get('read_bytes', 0):,} B")
    print(f"after : {result['after'].get('read_bytes', 0):,} B")
    print(f"ratio : {result['ratio']:.2f}×")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
