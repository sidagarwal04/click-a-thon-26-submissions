"""Sequence: a Dataset Workspace-owned graph of typed transform steps.

A SequenceStep + its PreparedTable are only ever appended together, on a
*successful* Sequence Run. A failed run still yields a SequenceRun (with a
typed failure outcome) so nothing attempted is silently dropped, but no
SequenceStep or PreparedTable is produced from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceTableReference,
)

from .catalog import (
    CastTypeParameters,
    DedupeParameters,
    DropNullsParameters,
    FilterRowsParameters,
    RenameColumnParameters,
    SequenceOperation,
)
from .prepared_table import PreparedTable
from .raw_table import RawTableReference

_CATALOG_OPERATION_TYPES = (
    DropNullsParameters,
    CastTypeParameters,
    DedupeParameters,
    FilterRowsParameters,
    RenameColumnParameters,
)


class SequenceTransitionError(RuntimeError):
    """A Sequence was asked to record a step, run, or marker that does not
    belong to it, or that violates its lineage/catalog invariants."""


@dataclass(frozen=True, slots=True)
class SequenceRunSucceeded:
    produced_table_id: UUID
    kind: str = "succeeded"


@dataclass(frozen=True, slots=True)
class SequenceRunFailed:
    reason: SequenceExecutionFailureReason
    detail: str
    kind: str = "failed"


SequenceRunOutcome = SequenceRunSucceeded | SequenceRunFailed


@dataclass(frozen=True, slots=True)
class SequenceRun:
    """One attempted execution of a Sequence Step, whatever its outcome."""

    run_id: UUID
    sequence_id: UUID
    tenant_id: UUID
    step_id: UUID
    outcome: SequenceRunOutcome
    attempted_at: datetime


@dataclass(frozen=True, slots=True)
class SequenceStep:
    """One node in a Sequence's graph: a single typed operation applied to
    its input, recorded only once its Sequence Run has succeeded."""

    step_id: UUID
    sequence_id: UUID
    tenant_id: UUID
    operation: SequenceOperation
    # None means this step reads the Sequence's Raw Table directly.
    input_reference: SequenceTableReference | None
    produced_table_id: UUID
    created_at: datetime


@dataclass(slots=True)
class Sequence:
    """A reusable, Dataset Workspace-owned graph of Sequence Steps running
    from one Raw Table to one or more Final Tables."""

    sequence_id: UUID
    tenant_id: UUID
    dataset_workspace_id: UUID
    raw_table_reference: RawTableReference
    created_at: datetime
    updated_at: datetime
    steps: tuple[SequenceStep, ...] = field(default_factory=tuple)
    prepared_tables: tuple[PreparedTable, ...] = field(default_factory=tuple)
    runs: tuple[SequenceRun, ...] = field(default_factory=tuple)
    final_table_ids: frozenset[UUID] = field(default_factory=frozenset)

    @classmethod
    def create(
        cls,
        *,
        sequence_id: UUID,
        tenant_id: UUID,
        dataset_workspace_id: UUID,
        raw_table_reference: RawTableReference,
        now: datetime,
    ) -> Sequence:
        return cls(
            sequence_id=sequence_id,
            tenant_id=tenant_id,
            dataset_workspace_id=dataset_workspace_id,
            raw_table_reference=raw_table_reference,
            created_at=now,
            updated_at=now,
        )

    def _prepared_table_ids(self) -> frozenset[UUID]:
        return frozenset(table.prepared_table_id for table in self.prepared_tables)

    def record_run(self, run: SequenceRun) -> None:
        """Records an attempted Sequence Step execution, success or failure.

        Every attempt is recorded here, before append_step (which only
        happens on success) — so a failed run is never silently dropped.
        """
        if run.sequence_id != self.sequence_id or run.tenant_id != self.tenant_id:
            raise SequenceTransitionError(
                "Sequence Run does not belong to this Sequence"
            )
        self.runs = (*self.runs, run)
        self.updated_at = run.attempted_at

    def append_step(self, step: SequenceStep, table: PreparedTable) -> None:
        """Atomically appends a successful Sequence Step and the Prepared
        Table it produced. Only ever called after a successful Sequence Run.
        """
        if (
            step.sequence_id != self.sequence_id
            or table.sequence_id != self.sequence_id
        ):
            raise SequenceTransitionError(
                "Sequence Step or Prepared Table does not belong to this Sequence"
            )
        if step.tenant_id != self.tenant_id or table.tenant_id != self.tenant_id:
            raise SequenceTransitionError(
                "Sequence Step or Prepared Table does not belong to this Tenant"
            )
        if step.produced_table_id != table.prepared_table_id:
            raise SequenceTransitionError(
                "Sequence Step's produced table does not match the given Prepared Table"
            )
        if not isinstance(step.operation, _CATALOG_OPERATION_TYPES):
            raise SequenceTransitionError(
                "Sequence Step operation is not a member of the typed operation catalog"
            )
        if step.input_reference is not None:
            if step.input_reference.kind != "prepared":
                raise SequenceTransitionError(
                    "A Sequence Step's input reference must be either absent "
                    "(reading the Raw Table) or a prior Prepared Table"
                )
            if step.input_reference.reference_id not in self._prepared_table_ids():
                raise SequenceTransitionError(
                    "Sequence Step's input table is not part of this Sequence"
                )

        self.steps = (*self.steps, step)
        self.prepared_tables = (*self.prepared_tables, table)
        self.updated_at = table.created_at

    def mark_final(self, prepared_table_id: UUID) -> None:
        if prepared_table_id not in self._prepared_table_ids():
            raise SequenceTransitionError(
                f"{prepared_table_id} is not a Prepared Table in this Sequence"
            )
        self.final_table_ids = self.final_table_ids | {prepared_table_id}

    def unmark_final(self, prepared_table_id: UUID) -> None:
        if prepared_table_id not in self.final_table_ids:
            raise SequenceTransitionError(
                f"{prepared_table_id} is not marked as a Final Table"
            )
        self.final_table_ids = self.final_table_ids - {prepared_table_id}

    def lineage_for(self, prepared_table_id: UUID) -> tuple[PreparedTable, ...]:
        """The ordered chain of Prepared Tables from the Raw Table's first
        step through the given Prepared Table, inclusive."""
        by_id = {table.prepared_table_id: table for table in self.prepared_tables}
        if prepared_table_id not in by_id:
            raise SequenceTransitionError(
                f"{prepared_table_id} is not a Prepared Table in this Sequence"
            )
        chain: list[PreparedTable] = []
        current = by_id[prepared_table_id]
        while True:
            chain.append(current)
            parent_reference = current.parent_table_reference
            if parent_reference is None:
                break
            current = by_id[parent_reference.reference_id]
        return tuple(reversed(chain))
