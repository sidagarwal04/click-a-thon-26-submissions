"""Glossary ontology loader for the InMobi root-cause analyst."""

from inmobi_ontology.loader import (
    default_ontology_path,
    get_decomposition,
    get_dimensions_for_metric,
    get_relationships,
    get_term,
    load_ontology,
    lookup_term,
)
from inmobi_ontology.models import Ontology, Term

__all__ = [
    "Ontology",
    "Term",
    "default_ontology_path",
    "get_decomposition",
    "get_dimensions_for_metric",
    "get_relationships",
    "get_term",
    "load_ontology",
    "lookup_term",
]
