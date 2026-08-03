"""The living, versioned context layer.

Three modules, one idea: **the ClickHouse tables are the source of truth for context,
and markdown is only a human render.**

    bootstrap.py  base_context.md -> ContextEntry rows (deterministic markdown parsing,
                  no LLM: a parser that hallucinates a metric definition is worse than
                  no parser at all).
    store.py      append-only CRUD + versioning + snapshots + diffs + changelog over
                  context_entry_log / context_snapshot / context_changelog /
                  contradiction / schema_snapshot_log.
    checks.py     contradiction detection. The LLM proposes, SQL adjudicates: every
                  Contradiction carries the query that proves it AND that query's
                  executed result.

Nothing in here knows the name of any feature spec. Every check is derived from the
context bodies and from `system.columns` at runtime.
"""

from __future__ import annotations

from contextlayer.bootstrap import parse_base_context
from contextlayer.checks import CheckOutput, run_all_checks
from contextlayer.store import ContextStore, apply_schema, system_select

__all__ = [
    "CheckOutput",
    "ContextStore",
    "apply_schema",
    "parse_base_context",
    "run_all_checks",
    "system_select",
]
