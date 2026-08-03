"""SQL construction helpers shared by the connector adapters.

Extracted so that identifier escaping has exactly one implementation. It
previously existed in ``source_connector`` while ``landing_zone`` inlined raw
backticks — the same shape written twice, one of which escaped correctly and one
of which did not. Identifier quoting is the injection boundary in both modules,
so it is not a place for two opinions.
"""

from __future__ import annotations


def quote_identifier(name: str) -> str:
    """Quote an identifier for interpolation into a query.

    Table and column names cannot be passed as query parameters — they are
    identifiers, not values — so they must be interpolated. Backtick-quoting
    with internal backticks doubled is ClickHouse's own escaping rule.
    """
    return "`" + name.replace("`", "``") + "`"


def qualify(database: str, table: str) -> str:
    """A quoted `database`.`table` reference."""
    return f"{quote_identifier(database)}.{quote_identifier(table)}"
