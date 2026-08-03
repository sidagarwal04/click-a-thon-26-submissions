"""Cross-table analysis joining a new feature to the existing warehouse funnel.

A feature analysed in isolation can only answer "how does this behave"; the
question a product manager actually asks is "did this move conversion, and for
whom". That needs the new event table joined to the pre-existing outcome tables.

Which tables those are is never hardcoded. The join is resolved from the
accumulated context layer: relationships name the shared key, and entities mark
which tables are funnel stages. When the context cannot supply a join, no
baseline query is produced rather than a guessed one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pydantic import JsonValue

from app.schemas.agents import AnalysisQuery, InstrumentationPlan
from app.schemas.features import ContextDocument

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Ordered weakest-to-strongest: a later match wins when several tables qualify,
# so the terminal conversion event is preferred as the outcome table.
_OUTCOME_HINTS = ("complete", "purchase", "convert", "success", "paid")


class BaselineResolutionError(RuntimeError):
    """Raised when a baseline join cannot be resolved from context."""


def _safe(identifier: str) -> str:
    if _IDENTIFIER.fullmatch(identifier) is None:
        raise BaselineResolutionError(f"Unsafe baseline identifier: {identifier!r}")
    return f"`{identifier}`"


def _outcome_rank(table: str) -> int:
    lowered = table.casefold()
    for rank, hint in enumerate(_OUTCOME_HINTS, start=1):
        if hint in lowered:
            return rank
    return 0


def resolve_outcome_table(
    context: ContextDocument | None,
    *,
    entity_column: str,
    available_tables: Sequence[str],
    table_columns: Mapping[str, Sequence[str]],
) -> str | None:
    """Pick the existing table that best represents a converted outcome.

    Candidates must be pre-existing tables that carry the feature's own entity
    column, so the join key is known to exist on both sides. Among those, the
    context layer's own funnel entities are preferred, and the strongest
    outcome-shaped name wins.
    """

    candidates = [
        table
        for table in available_tables
        if entity_column in set(table_columns.get(table, ()))
    ]
    if not candidates:
        return None

    funnel_tables: set[str] = set()
    if context is not None:
        for entity in context.entities:
            table = entity.get("table_name")
            kind = str(entity.get("kind", "")).casefold()
            if isinstance(table, str) and kind == "funnel":
                funnel_tables.add(table)

    ranked = sorted(
        candidates,
        key=lambda table: (
            table in funnel_tables,
            _outcome_rank(table),
            # Stable tie-break so the same warehouse always resolves the same way.
            -len(table),
        ),
        reverse=True,
    )
    best = ranked[0]
    if best not in funnel_tables and _outcome_rank(best) == 0:
        return None
    return best


def build_baseline_analyses(
    instrumentation: InstrumentationPlan,
    *,
    context: ContextDocument | None,
    available_tables: Sequence[str],
    table_columns: Mapping[str, Sequence[str]],
) -> list[AnalysisQuery]:
    """Compare entities exposed to the feature against those that were not.

    Returns an empty list when the warehouse offers no joinable outcome table,
    so a feature with no baseline simply produces no baseline query.
    """

    entity_column = instrumentation.primary_entity
    outcome_table = resolve_outcome_table(
        context,
        entity_column=entity_column,
        available_tables=available_tables,
        table_columns=table_columns,
    )
    if outcome_table is None:
        return []

    feature_table = _safe(instrumentation.table_name)
    outcome = _safe(outcome_table)
    entity = _safe(entity_column)
    steps = instrumentation.funnel_steps
    event_column = (
        "event"
        if any(column.name == "event" for column in instrumentation.columns)
        else "event_name"
    )
    event_field = _safe(event_column)

    analyses = [
        AnalysisQuery(
            query_id="baseline_conversion_lift",
            analysis_type="baseline_comparison",
            purpose=(
                f"Compare downstream {outcome_table} conversion for entities "
                "exposed to the feature against entities that were not, to "
                "estimate the feature's lift."
            ),
            sql=(
                "SELECT exposed, uniqExact(entity_id) AS entities, "
                "uniqExactIf(entity_id, converted) AS converted_entities, "
                "converted_entities / nullIf(uniqExact(entity_id), 0) AS "
                f"conversion_rate FROM (SELECT o.{entity} AS entity_id, 1 AS converted, "
                f"o.{entity} IN (SELECT {entity} FROM {feature_table}) AS exposed FROM "
                f"{outcome} AS o) GROUP BY exposed ORDER BY exposed"
            ),
        ),
        AnalysisQuery(
            query_id="feature_step_to_conversion",
            analysis_type="baseline_comparison",
            purpose=(
                "Measure how many entities reaching each feature step go on to "
                f"convert in {outcome_table}, isolating where value is lost."
            ),
            sql=(
                f"SELECT {event_field} AS step, uniqExact({entity}) AS entities, "
                f"uniqExactIf({entity}, converted) AS converted_entities, "
                f"converted_entities / nullIf(uniqExact({entity}), 0) AS "
                f"conversion_rate FROM (SELECT {event_field}, {entity}, {entity} IN (SELECT "
                f"{entity} FROM {outcome}) AS converted FROM {feature_table}) GROUP BY step "
                "ORDER BY entities DESC"
            ),
        ),
    ]

    # windowFunnel enforces true time-ordered progression per entity, which a
    # per-event-name count cannot: the base context recommends it explicitly.
    if len(steps) >= 2:
        timestamp = _safe(instrumentation.timestamp_field)
        conditions = ", ".join(
            f"{event_field} = " + "'" + step.replace("'", "''") + "'" for step in steps
        )
        analyses.append(
            AnalysisQuery(
                query_id="ordered_funnel_depth",
                analysis_type="funnel",
                purpose=(
                    "Count entities by how far they progress through the feature "
                    "steps in strict time order, not merely which events they emitted."
                ),
                sql=(
                    f"SELECT depth, count() AS entities FROM (SELECT {entity}, "
                    f"windowFunnel(86400)({timestamp}, {conditions}) AS depth "
                    f"FROM {feature_table} GROUP BY {entity}) GROUP BY depth "
                    "ORDER BY depth"
                ),
            )
        )
    return analyses


def baseline_context_note(
    context: ContextDocument | None,
) -> list[dict[str, JsonValue]]:
    """Surface the join map used, so a trace shows why these tables were chosen."""

    if context is None:
        return []
    return [
        {
            "source_table": relationship.get("source_table"),
            "target_table": relationship.get("target_table"),
            "join_column": relationship.get("target_column"),
        }
        for relationship in context.relationships
    ]


__all__ = [
    "BaselineResolutionError",
    "baseline_context_note",
    "build_baseline_analyses",
    "resolve_outcome_table",
]
