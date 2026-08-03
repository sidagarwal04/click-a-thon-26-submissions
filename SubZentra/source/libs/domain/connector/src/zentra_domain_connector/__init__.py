"""Connector domain.

Data Sources, Catalog Versions, Field Profiles, and the Relations between
fields that form a Join Graph. Framework independent: this package knows
nothing about ClickHouse, HTTP, or persistence.
"""

from .access import AccessOverrides, CatalogAccessOverride
from .catalog import (
    CatalogDiff,
    CatalogVersion,
    DataSource,
    FieldChange,
    FieldIdentity,
    FieldProfile,
    SourceField,
    SourceTable,
    UnreadableTable,
    diff_catalogs,
)
from .confidence import (
    ConfidenceAssessment,
    OverlapMeasurement,
    assess,
    cardinality_ceiling,
    sample_size_ceiling,
)
from .constants import (
    MAX_UPLOAD_BYTES,
    MIN_OVERLAP_FRACTION,
    MIN_PROPOSAL_CONFIDENCE,
)
from .harvest import HarvestBudget, HarvestRun, HarvestScope
from .inference import (
    COMPOSITE_KEY_LIMITATION,
    CandidatePair,
    ScoredCandidate,
    UnexaminedField,
    coverage_summary,
    generate_candidates,
    score_candidate,
)
from .naming import name_affinity, normalise_field_name, tokenise
from .reconciliation import ReconciliationOutcome, reconcile
from .relation import (
    JoinGraph,
    Relation,
    RelationEvidence,
    infer_cardinality,
)
from .types import (
    JOINABLE_FAMILIES,
    TERMINAL_PHASES,
    BindingCeiling,
    BudgetExhaustedError,
    Cardinality,
    ConnectionCheck,
    ConnectionFailure,
    ConnectorError,
    HarvestPhase,
    HarvestTransitionError,
    RejectionReason,
    RelationOrigin,
    RelationState,
    RelationTransitionError,
    SourceHealth,
    SourceKind,
    StaleReason,
    TypeFamily,
    UploadFormat,
)
from .typing_rules import classify, normalise_type, types_are_compatible, unwrap_type

__all__ = [
    "COMPOSITE_KEY_LIMITATION",
    "JOINABLE_FAMILIES",
    "MAX_UPLOAD_BYTES",
    "MIN_OVERLAP_FRACTION",
    "MIN_PROPOSAL_CONFIDENCE",
    "TERMINAL_PHASES",
    "AccessOverrides",
    "BindingCeiling",
    "BudgetExhaustedError",
    "CandidatePair",
    "Cardinality",
    "CatalogAccessOverride",
    "CatalogDiff",
    "CatalogVersion",
    "ConfidenceAssessment",
    "ConnectionCheck",
    "ConnectionFailure",
    "ConnectorError",
    "DataSource",
    "FieldChange",
    "FieldIdentity",
    "FieldProfile",
    "HarvestBudget",
    "HarvestPhase",
    "HarvestRun",
    "HarvestScope",
    "HarvestTransitionError",
    "JoinGraph",
    "OverlapMeasurement",
    "ReconciliationOutcome",
    "RejectionReason",
    "Relation",
    "RelationEvidence",
    "RelationOrigin",
    "RelationState",
    "RelationTransitionError",
    "ScoredCandidate",
    "SourceField",
    "SourceHealth",
    "SourceKind",
    "SourceTable",
    "StaleReason",
    "TypeFamily",
    "UnexaminedField",
    "UnreadableTable",
    "UploadFormat",
    "assess",
    "cardinality_ceiling",
    "classify",
    "coverage_summary",
    "diff_catalogs",
    "generate_candidates",
    "infer_cardinality",
    "name_affinity",
    "normalise_field_name",
    "normalise_type",
    "reconcile",
    "sample_size_ceiling",
    "score_candidate",
    "tokenise",
    "types_are_compatible",
    "unwrap_type",
]
