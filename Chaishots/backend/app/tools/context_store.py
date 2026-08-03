from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence

from pydantic import JsonValue

from app.schemas.agents import (
    ContextAgentOutput,
    EntityDefinition,
    MetricDefinition,
    RelationshipDefinition,
)
from app.schemas.features import ContextDocument


class ContextValidationError(RuntimeError):
    """Raised when agent-proposed context names tables or columns that do not exist."""


def _relationship_key(relationship: Mapping[str, JsonValue]) -> tuple[str, ...]:
    return tuple(
        str(relationship.get(field, ""))
        for field in (
            "source_table",
            "source_column",
            "target_table",
            "target_column",
        )
    )


def _named_key(item: Mapping[str, JsonValue]) -> str:
    return str(item.get("name", ""))


def _merge_by_key(
    previous: Sequence[dict[str, JsonValue]],
    added: Sequence[dict[str, JsonValue]],
    key: Callable[[Mapping[str, JsonValue]], Hashable],
) -> list[dict[str, JsonValue]]:
    """Fold additions over previous items, letting the newer definition win."""

    merged: dict[Hashable, dict[str, JsonValue]] = {}
    for item in (*previous, *added):
        merged[key(item)] = item
    return list(merged.values())


def _dedup_strings(*groups: Sequence[str]) -> list[str]:
    seen: dict[str, None] = {}
    for group in groups:
        for value in group:
            seen.setdefault(value, None)
    return list(seen)


def merge_context(
    previous: ContextDocument | None,
    output: ContextAgentOutput,
    *,
    version: int,
    run_id: str,
) -> ContextDocument:
    """Fold newly discovered knowledge into the previous snapshot.

    The agent only reports what is new; the complete document is always
    assembled here so a snapshot never depends on the model repeating itself.
    """

    entities = _merge_by_key(
        previous.entities if previous else [],
        [entity.model_dump(mode="json") for entity in output.entities_added],
        _named_key,
    )
    relationships = _merge_by_key(
        previous.relationships if previous else [],
        [
            relationship.model_dump(mode="json")
            for relationship in output.relationships_added
        ],
        _relationship_key,
    )
    metrics = _merge_by_key(
        previous.metrics if previous else [],
        [metric.model_dump(mode="json") for metric in output.metrics_added],
        _named_key,
    )
    conventions = _dedup_strings(
        previous.naming_conventions if previous else [],
        output.conventions_added,
    )
    previous_conflicts = [
        str(conflict) for conflict in (previous.conflicts if previous else [])
    ]
    conflicts = _dedup_strings(previous_conflicts, output.conflicts)
    return ContextDocument(
        version=version,
        run_id=run_id,
        entities=entities,
        relationships=relationships,
        metrics=metrics,
        # Known issues are seeded from the base layer and carried forward: the
        # write agent records new knowledge, it does not curate this log.
        known_issues=list(previous.known_issues) if previous else [],
        naming_conventions=conventions,
        conflicts=list(conflicts),
    )


def _require_column(
    table_schemas: Mapping[str, Sequence[str]],
    table: str,
    column: str,
    *,
    label: str,
) -> None:
    columns = table_schemas.get(table)
    if columns is None:
        raise ContextValidationError(
            f"{label} references unknown table: {table!r}"
        )
    if column not in columns:
        raise ContextValidationError(
            f"{label} references unknown column {column!r} on table {table!r}"
        )


def validate_context_output(
    output: ContextAgentOutput,
    *,
    table_schemas: Mapping[str, Sequence[str]],
) -> None:
    """Reject context that names tables or columns absent from the warehouse."""

    for relationship in output.relationships_added:
        _require_column(
            table_schemas,
            relationship.source_table,
            relationship.source_column,
            label="Relationship source",
        )
        _require_column(
            table_schemas,
            relationship.target_table,
            relationship.target_column,
            label="Relationship target",
        )
    for entity in output.entities_added:
        _require_column(
            table_schemas,
            entity.table_name,
            entity.primary_key,
            label=f"Entity {entity.name!r} primary key",
        )
        for dimension in entity.dimensions:
            _require_column(
                table_schemas,
                entity.table_name,
                dimension,
                label=f"Entity {entity.name!r} dimension",
            )
        access_fields = [
            *entity.business_entities,
            *entity.common_filters,
            *entity.common_groupings,
        ]
        if entity.time_field is not None:
            access_fields.append(entity.time_field)
        if entity.event_field is not None:
            access_fields.append(entity.event_field)
        for field in access_fields:
            _require_column(
                table_schemas,
                entity.table_name,
                field,
                label=f"Entity {entity.name!r} access pattern",
            )


def valid_context_subset(
    output: ContextAgentOutput,
    *,
    table_schemas: Mapping[str, Sequence[str]],
) -> ContextAgentOutput:
    """Drop only the items that fail validation, keeping the rest.

    Used as a last resort after the write agent has exhausted its retries: the
    run's schema, data, and insights are already durable, so a partly-invalid
    context proposal should not discard the knowledge that is sound.
    """

    entities: list[EntityDefinition] = []
    for entity in output.entities_added:
        try:
            _require_column(
                table_schemas,
                entity.table_name,
                entity.primary_key,
                label=f"Entity {entity.name!r} primary key",
            )
        except ContextValidationError:
            continue
        available = table_schemas.get(entity.table_name, ())
        entities.append(
            entity.model_copy(
                update={
                    "dimensions": [
                        dimension
                        for dimension in entity.dimensions
                        if dimension in available
                    ],
                    "business_entities": [
                        field for field in entity.business_entities if field in available
                    ],
                    "time_field": (
                        entity.time_field if entity.time_field in available else None
                    ),
                    "event_field": (
                        entity.event_field if entity.event_field in available else None
                    ),
                    "common_filters": [
                        field for field in entity.common_filters if field in available
                    ],
                    "common_groupings": [
                        field for field in entity.common_groupings if field in available
                    ],
                }
            )
        )

    relationships: list[RelationshipDefinition] = []
    for relationship in output.relationships_added:
        try:
            _require_column(
                table_schemas,
                relationship.source_table,
                relationship.source_column,
                label="Relationship source",
            )
            _require_column(
                table_schemas,
                relationship.target_table,
                relationship.target_column,
                label="Relationship target",
            )
        except ContextValidationError:
            continue
        relationships.append(relationship)

    metrics: list[MetricDefinition] = list(output.metrics_added)
    return ContextAgentOutput(
        entities_added=entities,
        relationships_added=relationships,
        metrics_added=metrics,
        conventions_added=list(output.conventions_added),
        conflicts=list(output.conflicts),
    )
