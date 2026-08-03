"""Measure relation inference against TPC-H's documented foreign keys.

The Connector's premise is that inference is deterministic, so its accuracy can
be *measured* rather than asserted. This is what makes good on that: TPC-H
publishes its foreign keys, so there is a known-correct answer to score against.

Deliberately narrow, in the spirit of `live_run.py::compare`. It reports which
documented joins were recovered, which were missed, and which proposals were
spurious. It does not score how *confident* the system was — a proposal that is
right for the wrong reason is still a recovered join, and conflating the two
would hide a real regression behind a moved threshold.

Run:  docker compose up -d --wait clickhouse
      uv run python tools/evals/connector_accuracy.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from zentra_adapter_clickhouse import ClickHouseSourceConnector
from zentra_application_connector import SourceCredentials, SourceFieldDescriptor
from zentra_domain_connector import (
    CatalogVersion,
    SourceField,
    SourceTable,
    classify,
    generate_candidates,
    normalise_type,
    score_candidate,
)

#: TPC-H's documented foreign keys, as unordered field pairs. Ground truth.
#:
#: Note that the three dimension keys — the two nation references and the region
#: reference — *are* recovered, despite pointing at tables with 25 and 5 distinct
#: values. The cardinality ceiling caps how much confidence such a relation may
#: claim; it does not suppress the proposal. That is the intended behaviour and
#: worth stating, because "capped" and "rejected" are easy to conflate: a
#: reviewer still sees the join, and still sees that the system is not sure.
GROUND_TRUTH: tuple[frozenset[str], ...] = (
    frozenset({"customer.c_nationkey", "nation.n_nationkey"}),
    frozenset({"supplier.s_nationkey", "nation.n_nationkey"}),
    frozenset({"nation.n_regionkey", "region.r_regionkey"}),
    frozenset({"orders.o_custkey", "customer.c_custkey"}),
    frozenset({"lineitem.l_orderkey", "orders.o_orderkey"}),
    frozenset({"lineitem.l_partkey", "part.p_partkey"}),
    frozenset({"lineitem.l_suppkey", "supplier.s_suppkey"}),
    frozenset({"partsupp.ps_partkey", "part.p_partkey"}),
    frozenset({"partsupp.ps_suppkey", "supplier.s_suppkey"}),
)

#: Recovering fewer than this many of the nine fails the run. Set to the measured
#: baseline — all nine — rather than to a comfortable margin, because a floor
#: below the current behaviour would let a regression land unnoticed.
MIN_RECOVERED = 9

#: Above this many spurious proposals, a reviewer's queue is mostly noise and
#: the confirmation step stops being a judgement rather than a rubber stamp.
#:
#: The baseline is four, and three of those four are *transitive co-references*
#: — `lineitem.l_partkey` and `partsupp.ps_partkey` genuinely share values
#: because both reference `part.p_partkey`. They are not foreign keys to each
#: other, and a human is exactly the right thing to decide that. The fourth,
#: two account-balance columns in the same numeric range, is the honest kind of
#: false positive. The ceiling has headroom for one more before the queue would
#: need rethinking.
MAX_SPURIOUS = 6

SAMPLE_ROWS = 20_000


def credentials() -> SourceCredentials:
    return SourceCredentials(
        host=os.getenv("TPCH_HOST", "localhost"),
        port=int(os.getenv("TPCH_PORT", "8123")),
        database=os.getenv("TPCH_DATABASE", "tpch"),
        username=os.getenv("TPCH_USERNAME", "tpch_reader"),
        password=os.getenv("TPCH_PASSWORD", "tpch_reader"),
        secure=os.getenv("TPCH_SECURE", "false").lower() == "true",
    )


def _to_field(descriptor: SourceFieldDescriptor, table_id) -> SourceField:
    return SourceField(
        field_id=uuid4(),
        table_id=table_id,
        name=descriptor.name,
        declared_type=descriptor.declared_type,
        family=classify(descriptor.declared_type),
        normalised_type=normalise_type(descriptor.declared_type),
        nullable=descriptor.nullable,
        position=descriptor.position,
    )


async def build_catalog(
    connector: ClickHouseSourceConnector, creds: SourceCredentials
) -> CatalogVersion:
    """Harvest schema only. Profiles are not needed to score joins."""
    descriptors = await connector.list_tables(creds, databases=(creds.database,))
    tables: list[SourceTable] = []
    for descriptor in descriptors:
        table_id = uuid4()
        fields = await connector.describe_fields(
            creds, database=descriptor.database, table=descriptor.name
        )
        tables.append(
            SourceTable(
                table_id=table_id,
                name=descriptor.name,
                database=descriptor.database,
                engine=descriptor.engine,
                estimated_rows=descriptor.estimated_rows,
                fields=tuple(_to_field(f, table_id) for f in fields),
            )
        )
    return CatalogVersion(
        catalog_version_id=uuid4(),
        data_source_id=uuid4(),
        tenant_id=uuid4(),
        harvest_run_id=uuid4(),
        created_at=datetime.now(UTC),
        tables=tuple(tables),
    )


async def infer(
    connector: ClickHouseSourceConnector,
    creds: SourceCredentials,
    catalog: CatalogVersion,
) -> tuple[set[frozenset[str]], int]:
    """Every pair inference proposes, as `table.field` name pairs."""
    source_id = catalog.data_source_id
    candidates, unexamined = generate_candidates(((source_id, catalog),))
    proposed: set[frozenset[str]] = set()

    for candidate in candidates:
        overlap = await connector.measure_overlap(
            creds,
            creds,
            left=(
                candidate.left_table.database,
                candidate.left_table.name,
                candidate.left_field.name,
            ),
            right=(
                candidate.right_table.database,
                candidate.right_table.name,
                candidate.right_field.name,
            ),
            sample_rows=SAMPLE_ROWS,
        )
        if score_candidate(candidate, overlap) is None:
            continue
        proposed.add(
            frozenset(
                {
                    f"{candidate.left_table.name}.{candidate.left_field.name}",
                    f"{candidate.right_table.name}.{candidate.right_field.name}",
                }
            )
        )
    return proposed, len(unexamined)


def report(proposed: set[frozenset[str]], unexamined: int) -> int:
    expected = set(GROUND_TRUTH)
    recovered = expected & proposed
    missed = expected - proposed
    spurious = proposed - expected

    precision = len(recovered) / len(proposed) if proposed else 0.0
    recall = len(recovered) / len(expected)

    print(f"\nTPC-H relation inference — {len(expected)} documented foreign keys\n")
    print(f"  recovered  {len(recovered)}/{len(expected)}")
    print(f"  spurious   {len(spurious)}")
    print(f"  precision  {precision:.2f}")
    print(f"  recall     {recall:.2f}")
    print(f"  unexamined {unexamined} fields skipped as ineligible")

    for pair in sorted(missed, key=sorted):
        print(f"  MISSED     {' <-> '.join(sorted(pair))}")
    for pair in sorted(spurious, key=sorted):
        print(f"  SPURIOUS   {' <-> '.join(sorted(pair))}")

    failed = False
    if len(recovered) < MIN_RECOVERED:
        print(f"\n  FAIL  recovered {len(recovered)}, floor is {MIN_RECOVERED}")
        failed = True
    if len(spurious) > MAX_SPURIOUS:
        print(f"\n  FAIL  {len(spurious)} spurious, ceiling is {MAX_SPURIOUS}")
        failed = True
    if not failed:
        print(
            f"\n  OK  {len(recovered)} of {len(expected)} recovered "
            "with no schema knowledge"
        )
    return 1 if failed else 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    connector = ClickHouseSourceConnector()
    creds = credentials()

    check = await connector.test_connection(creds)
    if not check.reachable:
        print(
            f"Cannot reach the TPC-H source ({check.failure}). "
            "Run: docker compose up -d --wait clickhouse",
            file=sys.stderr,
        )
        return 2

    catalog = await build_catalog(connector, creds)
    proposed, unexamined = await infer(connector, creds, catalog)
    return report(proposed, unexamined)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
