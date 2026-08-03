"""One-time setup: create the context/ops tables and seed the context layer.

    python bootstrap_db.py            # create tables + seed base_context.md
    python bootstrap_db.py --reset    # wipe context/ops state first
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

import agents.context_agent as context_agent
from ch import CH

HERE = Path(__file__).parent
SCHEMA_SQL = HERE / "contextlayer" / "schema.sql"
BASE_CONTEXT = HERE.parent / "base_context.md"

OPS_TABLES = [
    "context_entry_log",
    "context_snapshot",
    "context_changelog",
    "contradiction",
    "schema_snapshot_log",
    "pipeline_runs",
    "pipeline_approvals",
    "insights_log",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="truncate context/ops tables first")
    args = ap.parse_args()
    con = Console()
    ch = CH()

    con.print(f"[bold]ClickHouse[/bold] {ch.database} @ {ch.run_select('SELECT version() v')[0]['v']}")

    if args.reset:
        for t in OPS_TABLES:
            if ch.table_exists(t):
                ch.execute_ddl(f"TRUNCATE TABLE {t}")
        con.print(f"[yellow]reset[/yellow] truncated {len(OPS_TABLES)} context/ops tables")

    ch.execute_script(SCHEMA_SQL.read_text())
    present = [t for t in OPS_TABLES if ch.table_exists(t)]
    con.print(f"[green]schema[/green] {len(present)}/{len(OPS_TABLES)} context/ops tables present")

    version = context_agent.bootstrap(BASE_CONTEXT, ch=ch, run_id="bootstrap")
    entries = ch.run_select("SELECT count() n FROM context_current")[0]["n"]
    con.print(f"[green]context[/green] seeded v{version} from base_context.md — {entries} active entries")

    by_kind = ch.run_select(
        "SELECT kind, count() n FROM context_current GROUP BY kind ORDER BY n DESC"
    )
    con.print("         " + ", ".join(f"{r['kind']}={r['n']}" for r in by_kind))
    con.print("\n[bold green]ready[/bold green] — run: python run_pipeline.py --spec <spec.md> --events <events.ndjson>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
