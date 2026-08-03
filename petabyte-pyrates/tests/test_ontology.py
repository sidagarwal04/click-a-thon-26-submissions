"""Tests for inmobi_ontology package."""

from pathlib import Path

from inmobi_ontology.loader import (
    default_ontology_path,
    get_decomposition,
    get_dimensions_for_metric,
    get_relationships,
    load_ontology,
    lookup_term,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = REPO_ROOT / "config" / "glossary_ontology.yaml"


def test_default_ontology_path_exists():
    path = default_ontology_path()
    assert path.is_file()


def test_load_ontology():
    ontology = load_ontology(ONTOLOGY_PATH)
    assert ontology.version == "1.3"
    assert "fill_rate" in ontology.terms
    assert "revenue" in ontology.terms
    assert len(ontology.relationships) > 0
    assert len(ontology.dimensions) > 0
    assert "revenue" in ontology.decompositions


def test_lookup_term_by_synonym():
    ontology = load_ontology(ONTOLOGY_PATH)
    term = lookup_term(ontology, "eCPM")
    assert term is not None
    assert term.id == "ecpm"


def test_lookup_term_not_found():
    ontology = load_ontology(ONTOLOGY_PATH)
    assert lookup_term(ontology, "nonexistent_metric") is None


def test_get_decomposition_revenue():
    ontology = load_ontology(ONTOLOGY_PATH)
    result = get_decomposition(ontology, "revenue")
    assert "error" not in result
    assert "requests" in result["components"]
    assert "fill_rate" in result["components"]
    assert "ecpm" in result["components"]


def test_get_dimensions_for_fill_rate():
    ontology = load_ontology(ONTOLOGY_PATH)
    result = get_dimensions_for_metric(ontology, "fill_rate")
    assert "error" not in result
    dim_ids = {d["id"] for d in result["dimensions"]}
    assert "region" in dim_ids
    assert "ad_format" in dim_ids
    for dim in result["dimensions"]:
        assert dim["clickhouse_view"] == "gold.metrics_hourly"
        if dim["id"] == "category":
            assert dim["dimension_key"] == "app_category"
        else:
            assert dim["dimension_key"] == dim["id"]


def test_get_relationships_filtered():
    ontology = load_ontology(ONTOLOGY_PATH)
    result = get_relationships(ontology, "revenue", "decomposed_by")
    assert "error" not in result
    assert len(result["relationships"]) >= 3
    for rel in result["relationships"]:
        assert rel["type"] == "decomposed_by"


def test_metric_term_has_query_pointers():
    ontology = load_ontology(ONTOLOGY_PATH)
    fill_rate = ontology.terms["fill_rate"]
    assert fill_rate.metric_key == "fill_rate"
    assert fill_rate.clickhouse_view == "gold.metrics_hourly"
    assert fill_rate.aggregation_rule == "sum_over_sum"
    assert "formula" not in fill_rate.to_dict()

    requests = ontology.terms["requests"]
    assert requests.metric_key == "requests"
    assert requests.clickhouse_view == "gold.metrics_hourly"
    assert requests.aggregation_rule is None


def test_ontology_to_dict_is_pure_ontology():
    ontology = load_ontology(ONTOLOGY_PATH)
    data = ontology.to_dict()
    assert data["version"] == "1.3"
    assert "terms" in data
    assert "decompositions" in data
    assert "constraints" in data
    assert "anomaly_detection" not in data
    assert "rca_playbook" not in data
    assert "investigation_playbook" not in data
