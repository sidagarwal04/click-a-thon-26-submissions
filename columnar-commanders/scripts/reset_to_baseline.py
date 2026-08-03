#!/usr/bin/env python3
"""Drop every table in the database except the eight original Atlys source tables.

Resets the ClickHouse database back to the state it was in before any agent ran:
the eight hand-loaded raw event tables, and nothing else. Intended for rehearsing
the unseen-spec run from a clean slate.

**Dry run by default.** Nothing is dropped unless you pass `--execute`.

    python scripts/reset_to_baseline.py                  # show what would be dropped
    python scripts/reset_to_baseline.py --execute        # actually drop it
    python scripts/reset_to_baseline.py --keep-infra     # spare the context/UI tables
    python scripts/reset_to_baseline.py --execute --keep-infra

Materialized views are dropped before plain tables: an MV whose target table has
already gone will still be dropped fine, but doing it in this order keeps the log
readable and avoids ClickHouse complaining about a missing TO target mid-run.

`.inner_id.*` tables are skipped entirely. They belong to materialized views
declared without an explicit TO target, and ClickHouse removes them itself when
the owning view is dropped. Dropping one directly orphans its view.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prism_ch.agents.context_store import (  # noqa: E402
    EMBEDDINGS_TABLE,
    ENTRIES_TABLE,
    ISSUES_TABLE,
    VERSIONS_TABLE,
    context_dialect,
)
from prism_ch.config import Settings  # noqa: E402
from prism_ch.db import connect  # noqa: E402
from prism_ch.ui.history import INSIGHTS_TABLE, SCHEMA_CHANGES_TABLE  # noqa: E402

#: The eight hand-loaded raw event tables. Everything else is agent-generated.
#: Sourced from prism_ch/base_context.md §3 and data/ddl.sql.
BASELINE_TABLES = frozenset(
    {
        # conversion funnel
        "destination_card_clicked",
        "application_started",
        "document_uploaded",
        "purchase_completed",
        # supporting engagement events
        "search_typed",
        "landing_page_scrolled",
        "auth_completed",
        "pay_now_clicked",
    }
)

#: Pipeline infrastructure — the context layer and the UI audit trail. These are
#: not agent-generated *artifacts*, they are where provenance lives, so
#: `--keep-infra` exists to preserve them. Dropping them loses the context
#: changelog, which is graded evidence.
INFRA_TABLES = frozenset(
    {
        VERSIONS_TABLE,
        ENTRIES_TABLE,
        ISSUES_TABLE,
        EMBEDDINGS_TABLE,
        SCHEMA_CHANGES_TABLE,
        INSIGHTS_TABLE,
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drop all tables except the eight original Atlys source tables.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually drop the tables. Without this, the script only prints the plan.",
    )
    parser.add_argument(
        "--keep-infra",
        action="store_true",
        help=(
            "Also keep the context layer (context_*) and UI audit tables (ui_*). "
            "Without this they are dropped along with everything else."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt. Only meaningful with --execute.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings.from_env()
    dialect = context_dialect(settings)
    client = connect(settings)

    keep = set(BASELINE_TABLES)
    if args.keep_infra:
        keep |= INFRA_TABLES

    rows = client.query(
        "SELECT name, engine FROM system.tables "
        "WHERE database = {db:String} ORDER BY engine, name",
        parameters={"db": settings.database},
    ).result_rows

    views, tables, skipped_inner = [], [], []
    for name, engine in rows:
        if name.startswith(".inner"):
            skipped_inner.append(name)
            continue
        if name in keep:
            continue
        (views if engine == "MaterializedView" else tables).append((name, engine))

    present_baseline = {name for name, _ in rows} & BASELINE_TABLES
    missing_baseline = BASELINE_TABLES - present_baseline

    print(f"database          {settings.database}")
    print(f"host              {settings.host}")
    print(f"target            {settings.clickhouse_target}")
    print(f"keeping           {len(present_baseline)}/8 baseline tables", end="")
    print(f" + {len(INFRA_TABLES)} infra tables" if args.keep_infra else "")
    if missing_baseline:
        print(f"  !! missing baseline: {', '.join(sorted(missing_baseline))}")
    print()

    doomed = views + tables
    if not doomed:
        print("Nothing to drop — the database is already at baseline.")
        return 0

    print(f"Would drop {len(doomed)} object(s):\n")
    for name, engine in doomed:
        marker = "  (infra)" if name in INFRA_TABLES else ""
        print(f"  {engine:<20} {name}{marker}")
    if skipped_inner:
        print(f"\nSkipping {len(skipped_inner)} .inner_id.* table(s) — "
              "dropped automatically with their views.")

    if not args.execute:
        print("\nDry run. Re-run with --execute to drop these.")
        return 0

    if not args.yes:
        print(f"\nThis is irreversible. Type the database name ({settings.database}) to confirm: ",
              end="")
        if input().strip() != settings.database:
            print("Aborted — no changes made.")
            return 1

    print()
    failed = 0
    # Views first: dropping a TO-target table out from under a live view leaves
    # the view in place, still pointed at something that no longer exists.
    for name, engine in doomed:
        sql = f"DROP TABLE IF EXISTS `{settings.database}`.`{name}`{dialect.on_cluster} SYNC"
        try:
            client.command(sql)
            print(f"  dropped  {engine:<20} {name}")
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            failed += 1
            print(f"  FAILED   {engine:<20} {name}: {str(exc)[:160]}")

    print(f"\n{len(doomed) - failed} dropped, {failed} failed.")
    if not args.keep_infra:
        print("Context and UI tables were dropped; they are recreated on the next "
              "context refresh or dashboard load.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
