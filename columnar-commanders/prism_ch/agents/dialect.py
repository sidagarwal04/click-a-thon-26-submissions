"""Target-aware DDL rendering.

The same SchemaProposal has to become valid DDL in two very different places:

- **cloud** - ClickHouse Cloud. SharedMergeTree underneath, replication handled
  for you, no user-configurable `remote_servers`. Plain `MergeTree`, and no
  `ON CLUSTER` clause: there is no `click_agents` cluster there.
- **cluster** - our local compose stack. A real named cluster, so DDL wants
  `ON CLUSTER click_agents` and `ReplicatedMergeTree` with `{shard}`/`{replica}`
  macros the *server* expands.

Getting this wrong is silent until it is not: DDL written for one target either
fails or quietly does the wrong thing on the other. Rehearse on the target you
will actually use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .types import ColumnSpec, MaterializedViewSpec, TableSpec, quote_literal

Target = Literal["cloud", "cluster"]


@dataclass
class Dialect:
    target: Target
    database: str
    cluster: str = "click_agents"
    # Generated tables share a database with the 8 hand-loaded source tables.
    # A prefix keeps "what the agent built" obvious at a glance in the Cloud
    # console and in `SHOW TABLES`, and makes cleanup a single LIKE pattern.
    table_prefix: str = "prism_"

    def physical_name(self, name: str) -> str:
        """The on-disk table name. Idempotent, so re-prefixing is harmless."""
        if not self.table_prefix or name.startswith(self.table_prefix):
            return name
        return f"{self.table_prefix}{name}"

    @property
    def on_cluster(self) -> str:
        return "" if self.target == "cloud" else f" ON CLUSTER {self.cluster}"

    def engine(self, table: TableSpec) -> str:
        family = table.engine or "MergeTree"
        if self.target == "cloud":
            # Cloud maps the whole MergeTree family onto Shared*MergeTree; an
            # explicit replication path would be meaningless here.
            return family
        # Braces stay literal - the server expands them from <macros>.
        path = f"/clickhouse/tables/{{shard}}/{self.database}/{self.physical_name(table.name)}"
        replicated = family if family.startswith("Replicated") else f"Replicated{family}"
        return f"{replicated}('{path}', '{{replica}}')"

    def qualified(self, name: str) -> str:
        return f"`{self.database}`.`{self.physical_name(name)}`"

    def create_database(self) -> str:
        return f"CREATE DATABASE IF NOT EXISTS `{self.database}`{self.on_cluster}"

    @staticmethod
    def _order_term(term: str) -> str:
        """Quote bare identifiers; leave expressions like toDate(ts) alone."""
        return term if "(" in term else f"`{term}`"

    def create_table(self, table: TableSpec) -> str:
        cols = ",\n    ".join(c.sql() for c in table.columns)
        order_by = ", ".join(self._order_term(c) for c in table.order_by) or "tuple()"

        sql = [
            f"CREATE TABLE IF NOT EXISTS {self.qualified(table.name)}{self.on_cluster}",
            "(",
            f"    {cols}",
            ")",
            f"ENGINE = {self.engine(table)}",
        ]
        if table.partition_by:
            sql.append(f"PARTITION BY {table.partition_by}")
        sql.append(f"ORDER BY ({order_by})")
        if table.ttl:
            sql.append(f"TTL {table.ttl}")
        sql.append("SETTINGS index_granularity = 8192")
        # Last clause, after SETTINGS - this is the one the LLM is explicitly
        # asked for ("one line on what this table records") and it was being
        # silently dropped: TableSpec.comment reached this method and nothing
        # rendered it.
        if table.comment:
            sql.append(f"COMMENT {quote_literal(table.comment)}")
        return "\n".join(sql)

    def create_materialized_view(self, view: MaterializedViewSpec) -> str:
        return (
            f"CREATE MATERIALIZED VIEW IF NOT EXISTS {self.qualified(view.name)}"
            f"{self.on_cluster}\n"
            f"TO {self.qualified(view.target_table)}\n"
            f"AS {view.select}"
        )

    def drop_database(self, name: str) -> str:
        return f"DROP DATABASE IF EXISTS `{name}`{self.on_cluster}"

    def add_column(self, table_name: str, column: ColumnSpec) -> str:
        """Widening an existing table, and the missing-column repair loop.

        There is deliberately no `drop_table` here. An existing table is only
        ever widened - dropping one would destroy data the pipeline cannot
        recreate, so the primitive that would allow it does not exist.

        `IF NOT EXISTS` makes this idempotent - safe to re-run the same repair
        without checking first whether a previous attempt already added it.
        """
        return (
            f"ALTER TABLE {self.qualified(table_name)}{self.on_cluster} "
            f"ADD COLUMN IF NOT EXISTS {column.sql()}"
        )


def for_settings(
    target: str, database: str, cluster: str, table_prefix: str = "prism_"
) -> Dialect:
    normalized = target.strip().lower()
    if normalized not in ("cloud", "cluster"):
        raise ValueError(f"CLICKHOUSE_TARGET must be 'cloud' or 'cluster', got {target!r}")
    return Dialect(  # type: ignore[arg-type]
        target=normalized, database=database, cluster=cluster, table_prefix=table_prefix
    )
