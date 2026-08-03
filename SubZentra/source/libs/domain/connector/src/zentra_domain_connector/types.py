"""Value types shared across the Connector domain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceKind(StrEnum):
    """How a Data Source came to exist.

    Two kinds of one concept rather than two concepts. An uploaded file is a
    Data Source backed by a ZentraOS-owned table, which is what gives harvest,
    profiling and inference exactly one implementation — and what makes
    relations *across* sources fall out rather than needing separate machinery.
    """

    CONNECTED = "connected"
    UPLOADED = "uploaded"


class SourceHealth(StrEnum):
    UNVERIFIED = "unverified"
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"


class ConnectionFailure(StrEnum):
    """Why a connection attempt failed, in terms the caller can act on.

    Three kinds rather than one, because "it did not work" does not tell an
    admin which field to fix. Deliberately coarse: anything finer would start
    echoing the source's own error text back to the caller, which is how
    connection internals leak.
    """

    UNREACHABLE = "unreachable"
    AUTHENTICATION_FAILED = "authentication_failed"
    DATABASE_NOT_FOUND = "database_not_found"


class TypeFamily(StrEnum):
    """Join-relevant grouping of source column types.

    Not a faithful type system — a classification for deciding whether two
    fields could plausibly be the same key.
    """

    INTEGER = "integer"
    STRING = "string"
    UUID = "uuid"
    DECIMAL = "decimal"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TEMPORAL = "temporal"
    OTHER = "other"


#: Families whose values can serve as a join key.
#:
#: Floats are excluded because equality on them is unreliable, and temporals
#: because two rows sharing a timestamp is coincidence rather than reference.
#: Booleans are excluded because they cannot identify anything — the cardinality
#: ceiling would flatten them anyway, but refusing them outright keeps obviously
#: useless pairs out of the reviewer's queue entirely.
JOINABLE_FAMILIES: frozenset[TypeFamily] = frozenset(
    {
        TypeFamily.INTEGER,
        TypeFamily.STRING,
        TypeFamily.UUID,
        TypeFamily.DECIMAL,
    }
)


class RelationState(StrEnum):
    """The lifecycle of a Relation.

    ``confirmed`` is the only state the Join Graph contains. Everything else
    exists so the reviewer's decisions are remembered: ``rejected`` so the same
    wrong guess is not re-proposed forever, ``stale`` so a schema change
    withdraws a join rather than silently changing what it means.
    """

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    STALE = "stale"


class RelationOrigin(StrEnum):
    INFERRED = "inferred"
    DECLARED = "declared"


class RejectionReason(StrEnum):
    NOT_A_REAL_RELATION = "not_a_real_relation"
    COINCIDENTAL_OVERLAP = "coincidental_overlap"
    WRONG_DIRECTION = "wrong_direction"
    DUPLICATE_OF_ANOTHER = "duplicate_of_another"


class StaleReason(StrEnum):
    FIELD_DROPPED = "field_dropped"
    FIELD_TYPE_CHANGED = "field_type_changed"
    TABLE_DROPPED = "table_dropped"


class BindingCeiling(StrEnum):
    """Which bound held a proposal's confidence down.

    Recorded rather than derived on read so a reviewer can see *why* a proposal
    is not more confident. ``NONE`` means the raw signal score was itself the
    limit — the evidence supported more confidence than the signals produced.
    """

    NONE = "none"
    SAMPLE_SIZE = "sample_size"
    CARDINALITY = "cardinality"


class Cardinality(StrEnum):
    ONE_TO_ONE = "one_to_one"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"
    UNKNOWN = "unknown"


class HarvestPhase(StrEnum):
    """Where a Harvest Run has reached.

    Ordered as they occur, so a reader can tell progress from the phase alone.
    """

    PENDING = "pending"
    CONNECTING = "connecting"
    LISTING_TABLES = "listing_tables"
    DESCRIBING_FIELDS = "describing_fields"
    PROFILING = "profiling"
    INFERRING_RELATIONS = "inferring_relations"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_PHASES: frozenset[HarvestPhase] = frozenset(
    {HarvestPhase.COMPLETED, HarvestPhase.FAILED, HarvestPhase.CANCELLED}
)


class UploadFormat(StrEnum):
    CSV = "csv"
    PARQUET = "parquet"


@dataclass(frozen=True, slots=True)
class ConnectionCheck:
    """The outcome of trying to reach a source.

    Carries no message from the source itself. A source's own error text
    routinely contains hostnames, usernames and internal topology, and this
    value is destined for an API response.
    """

    reachable: bool
    failure: ConnectionFailure | None = None

    def __post_init__(self) -> None:
        if self.reachable and self.failure is not None:
            raise ValueError("A reachable check cannot carry a failure")
        if not self.reachable and self.failure is None:
            raise ValueError("An unreachable check must say why")


class ConnectorError(Exception):
    """Base for every domain-level connector failure."""


class RelationTransitionError(ConnectorError):
    """A Relation was asked to move somewhere its lifecycle does not allow."""


class HarvestTransitionError(ConnectorError):
    """A Harvest Run was asked to move somewhere its lifecycle does not allow."""


class BudgetExhaustedError(ConnectorError):
    """A Harvest Run reached its query or time budget."""
