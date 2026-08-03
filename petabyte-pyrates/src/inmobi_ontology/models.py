"""Data models for glossary ontology."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Term:
    """A glossary term (metric or dimension reference)."""

    id: str
    type: str
    description: str
    synonyms: list[str] = field(default_factory=list)
    metric_key: str | None = None
    aggregation_rule: str | None = None
    clickhouse_column: str | None = None
    clickhouse_view: str | None = None
    context_only_for: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "synonyms": self.synonyms,
        }
        if self.metric_key:
            data["metric_key"] = self.metric_key
        if self.aggregation_rule:
            data["aggregation_rule"] = self.aggregation_rule
        if self.clickhouse_column:
            data["clickhouse_column"] = self.clickhouse_column
        if self.clickhouse_view:
            data["clickhouse_view"] = self.clickhouse_view
        if self.context_only_for:
            data["context_only_for"] = self.context_only_for
        return data


@dataclass
class Relationship:
    """A relationship between two ontology terms."""

    source: str
    target: str
    type: str
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "source": self.source,
            "target": self.target,
            "type": self.type,
        }
        if self.description:
            data["description"] = self.description
        return data


@dataclass
class Dimension:
    """A slice dimension for metric drill-down on the semantic layer."""

    id: str
    description: str
    clickhouse_view: str
    dimension_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "clickhouse_view": self.clickhouse_view,
            "dimension_key": self.dimension_key,
        }


@dataclass
class Decomposition:
    """Metric decomposition identity and components."""

    metric: str
    identity: str
    components: list[str]
    clickhouse_target: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "metric": self.metric,
            "identity": self.identity,
            "components": self.components,
        }
        if self.clickhouse_target:
            data["clickhouse_target"] = self.clickhouse_target
        return data


@dataclass
class Ontology:
    """Glossary ontology: terms, relationships, dimensions, decompositions, constraints."""

    version: str
    description: str
    terms: dict[str, Term]
    relationships: list[Relationship]
    dimensions: dict[str, Dimension]
    decompositions: dict[str, Decomposition]
    constraints: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "description": self.description,
            "terms": {k: v.to_dict() for k, v in self.terms.items()},
            "relationships": [r.to_dict() for r in self.relationships],
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "decompositions": {k: v.to_dict() for k, v in self.decompositions.items()},
            "constraints": self.constraints,
        }
