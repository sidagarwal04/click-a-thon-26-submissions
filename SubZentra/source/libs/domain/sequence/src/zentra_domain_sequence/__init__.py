"""ZentraOS Sequence domain: typed, versioned data-cleaning pipelines"""

from .catalog import (
    SEQUENCE_OPERATION_ADAPTER,
    CastTypeParameters,
    DedupeParameters,
    DropNullsParameters,
    FilterRowsParameters,
    RenameColumnParameters,
    SequenceOperation,
    SequenceOperationKind,
    SequenceOperationValidationError,
    UnknownSequenceOperationError,
    build_sequence_operation,
)
from .prepared_table import PreparedTable
from .raw_table import (
    ConnectorSourceTableReference,
    DatasetTableVersionReference,
    RawTableReference,
)
from .sequence import (
    Sequence,
    SequenceRun,
    SequenceRunFailed,
    SequenceRunOutcome,
    SequenceRunSucceeded,
    SequenceStep,
    SequenceTransitionError,
)

__all__ = [
    "SEQUENCE_OPERATION_ADAPTER",
    "CastTypeParameters",
    "ConnectorSourceTableReference",
    "DatasetTableVersionReference",
    "DedupeParameters",
    "DropNullsParameters",
    "FilterRowsParameters",
    "PreparedTable",
    "RawTableReference",
    "RenameColumnParameters",
    "Sequence",
    "SequenceOperation",
    "SequenceOperationKind",
    "SequenceOperationValidationError",
    "SequenceRun",
    "SequenceRunFailed",
    "SequenceRunOutcome",
    "SequenceRunSucceeded",
    "SequenceStep",
    "SequenceTransitionError",
    "UnknownSequenceOperationError",
    "build_sequence_operation",
]
