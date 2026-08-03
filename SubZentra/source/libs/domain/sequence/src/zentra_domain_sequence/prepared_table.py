"""Prepared Table: the immutable, versioned output of one Sequence Step.

"Final" is deliberately not a flag on PreparedTable itself — it is state the
owning Sequence maintains over its own Prepared Tables (see sequence.py),
which keeps this value record a pure, append-only fact about what a step
produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from zentra_domain_agent_execution import SequenceTableReference


@dataclass(frozen=True, slots=True)
class PreparedTable:
    """One immutable, versioned output of a Sequence Step.

    `parent_table_reference` is `None` only for the Prepared Table produced by
    the first Sequence Step, whose input is the Sequence's Raw Table rather
    than a prior Prepared Table.
    """

    prepared_table_id: UUID
    tenant_id: UUID
    sequence_id: UUID
    step_id: UUID
    parent_table_reference: SequenceTableReference | None
    row_count: int
    columns: tuple[str, ...]
    created_at: datetime
