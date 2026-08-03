"""Load and query glossary_ontology.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from inmobi_ontology.models import (
    Decomposition,
    Dimension,
    Ontology,
    Relationship,
    Term,
)

_ONTOLOGY_FILENAME = "glossary_ontology.yaml"
_CONFIG_RELATIVE = Path("config") / _ONTOLOGY_FILENAME


def default_ontology_path() -> Path:
    """Resolve ontology YAML path from env or known locations."""
    env_path = os.environ.get("ONTOLOGY_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    cwd_candidate = Path.cwd() / _CONFIG_RELATIVE
    if cwd_candidate.is_file():
        return cwd_candidate.resolve()

    package_root = Path(__file__).resolve().parent
    for parent in [package_root, *package_root.parents]:
        candidate = parent / _CONFIG_RELATIVE
        if candidate.is_file():
            return candidate.resolve()

    raise FileNotFoundError(
        f"Could not find {_ONTOLOGY_FILENAME}. Set ONTOLOGY_PATH or run from repo root."
    )


def _normalize_term_id(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _build_term_index(terms: dict[str, Term]) -> dict[str, str]:
    index: dict[str, str] = {}
    for term_id, term in terms.items():
        index[_normalize_term_id(term_id)] = term_id
        for synonym in term.synonyms:
            index[_normalize_term_id(synonym)] = term_id
    return index


def _parse_terms(raw: dict[str, Any]) -> dict[str, Term]:
    terms: dict[str, Term] = {}
    for term_id, data in raw.items():
        terms[term_id] = Term(
            id=term_id,
            type=data.get("type", "unknown"),
            description=data.get("description", ""),
            synonyms=list(data.get("synonyms", [])),
            metric_key=data.get("metric_key"),
            aggregation_rule=data.get("aggregation_rule"),
            clickhouse_column=data.get("clickhouse_column"),
            clickhouse_view=data.get("clickhouse_view"),
            context_only_for=list(data.get("context_only_for", [])),
        )
    return terms


def _parse_relationships(raw: list[dict[str, Any]]) -> list[Relationship]:
    return [
        Relationship(
            source=item["source"],
            target=item["target"],
            type=item["type"],
            description=item.get("description"),
        )
        for item in raw
    ]


def _parse_dimensions(raw: dict[str, Any]) -> dict[str, Dimension]:
    dimensions: dict[str, Dimension] = {}
    for dim_id, data in raw.items():
        dimensions[dim_id] = Dimension(
            id=dim_id,
            description=data.get("description", ""),
            clickhouse_view=data.get("clickhouse_view", "gold.ad_events_semantic"),
            dimension_key=data.get("dimension_key", dim_id),
        )
    return dimensions


def _parse_decompositions(raw: dict[str, Any]) -> dict[str, Decomposition]:
    decompositions: dict[str, Decomposition] = {}
    for metric, data in raw.items():
        decompositions[metric] = Decomposition(
            metric=metric,
            identity=data.get("identity", ""),
            components=list(data.get("components", [])),
            clickhouse_target=data.get("clickhouse_target"),
        )
    return decompositions


def load_ontology(path: Path | None = None) -> Ontology:
    """Load and parse the glossary ontology YAML file."""
    ontology_path = path or default_ontology_path()
    if not ontology_path.is_file():
        raise FileNotFoundError(f"Ontology file not found: {ontology_path}")

    with ontology_path.open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)

    terms = _parse_terms(raw.get("terms", {}))
    return Ontology(
        version=str(raw.get("version", "1.0")),
        description=str(raw.get("description", "")).strip(),
        terms=terms,
        relationships=_parse_relationships(raw.get("relationships", [])),
        dimensions=_parse_dimensions(raw.get("dimensions", {})),
        decompositions=_parse_decompositions(raw.get("decompositions", {})),
        constraints=list(raw.get("constraints", [])),
    )


def lookup_term(ontology: Ontology, name: str) -> Term | None:
    """Find a term by id or synonym (case-insensitive)."""
    index = _build_term_index(ontology.terms)
    canonical = index.get(_normalize_term_id(name))
    if canonical is None:
        return None
    return ontology.terms[canonical]


def get_term(ontology: Ontology, name: str) -> dict[str, Any]:
    """Return a term dict or an error dict."""
    term = lookup_term(ontology, name)
    if term is None:
        return {"error": f"term not found: {name}"}
    return term.to_dict()


def get_relationships(
    ontology: Ontology,
    term: str,
    relationship_type: str | None = None,
) -> dict[str, Any]:
    """Return relationships involving a term."""
    canonical = lookup_term(ontology, term)
    if canonical is None:
        return {"error": f"term not found: {term}"}

    term_id = canonical.id
    matches = [
        rel.to_dict()
        for rel in ontology.relationships
        if (rel.source == term_id or rel.target == term_id)
        and (relationship_type is None or rel.type == relationship_type)
    ]
    return {"term": term_id, "relationships": matches}


def get_decomposition(ontology: Ontology, metric: str) -> dict[str, Any]:
    """Return decomposition tree for a metric."""
    canonical = lookup_term(ontology, metric)
    metric_id = canonical.id if canonical else _normalize_term_id(metric)
    decomp = ontology.decompositions.get(metric_id)
    if decomp is None:
        return {"error": f"no decomposition defined for metric: {metric}"}
    return decomp.to_dict()


def get_dimensions_for_metric(ontology: Ontology, metric: str) -> dict[str, Any]:
    """Return dimensions that can slice a metric."""
    canonical = lookup_term(ontology, metric)
    if canonical is None:
        return {"error": f"term not found: {metric}"}

    metric_id = canonical.id
    dim_ids = [
        rel.target
        for rel in ontology.relationships
        if rel.source == metric_id and rel.type == "sliced_by"
    ]
    dimensions = [ontology.dimensions[d].to_dict() for d in dim_ids if d in ontology.dimensions]
    return {"metric": metric_id, "dimensions": dimensions}
