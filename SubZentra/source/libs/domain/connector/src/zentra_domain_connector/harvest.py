"""Harvest Runs: the bounded, observable execution of discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .constants import (
    DEFAULT_QUERY_BUDGET,
    DEFAULT_SAMPLE_ROWS,
    DEFAULT_TIME_BUDGET_SECONDS,
)
from .types import (
    TERMINAL_PHASES,
    HarvestPhase,
    HarvestTransitionError,
)


@dataclass(frozen=True, slots=True)
class HarvestScope:
    """Which part of a source a run should look at.

    Empty means everything. Scoping exists because sweeping a thousand-table
    warehouse to profile eight tables is a cost the Tenant pays on their own
    infrastructure.
    """

    databases: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()

    def includes_table(self, database: str, table: str) -> bool:
        if self.databases and database not in self.databases:
            return False
        return not (self.tables and table not in self.tables)


@dataclass(slots=True)
class HarvestBudget:
    """What a run may spend before it must stop.

    Consumption is tracked on the budget itself rather than on the run, so that
    a caller cannot advance a phase without the cost being counted.
    """

    max_queries: int = DEFAULT_QUERY_BUDGET
    max_seconds: float = DEFAULT_TIME_BUDGET_SECONDS
    sample_rows: int = DEFAULT_SAMPLE_ROWS
    queries_used: int = 0
    seconds_used: float = 0.0

    @property
    def exhausted(self) -> bool:
        return (
            self.queries_used >= self.max_queries
            or self.seconds_used >= self.max_seconds
        )

    def spend(self, *, queries: int = 1, seconds: float = 0.0) -> None:
        self.queries_used += queries
        self.seconds_used += seconds

    def remaining_queries(self) -> int:
        return max(0, self.max_queries - self.queries_used)


@dataclass(slots=True)
class HarvestRun:
    """One execution of discovery against a Data Source.

    Counts are exposed per phase rather than as a single percentage: a
    percentage of an unknown total is a fiction, and "412 fields described" is
    something a reader can actually act on.
    """

    harvest_run_id: UUID
    data_source_id: UUID
    tenant_id: UUID
    phase: HarvestPhase = HarvestPhase.PENDING
    scope: HarvestScope = field(default_factory=HarvestScope)
    budget: HarvestBudget = field(default_factory=HarvestBudget)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    tables_found: int = 0
    fields_described: int = 0
    fields_profiled: int = 0
    relations_proposed: int = 0
    unreadable_count: int = 0
    #: Fields inference skipped, and why, grouped by reason. Carried on the run
    #: so that a reviewer reading an empty proposal list can tell "nothing was
    #: found" from "most of your columns were never eligible".
    fields_unexamined: int = 0
    unexamined_reasons: dict[str, int] = field(default_factory=dict)
    catalog_version_id: UUID | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    cancellation_requested: bool = False

    @property
    def is_terminal(self) -> bool:
        return self.phase in TERMINAL_PHASES

    @property
    def is_running(self) -> bool:
        return not self.is_terminal and self.phase is not HarvestPhase.PENDING

    def advance(self, phase: HarvestPhase, *, at: datetime) -> None:
        if self.is_terminal:
            raise HarvestTransitionError(
                f"Harvest run already finished in phase {self.phase}"
            )
        if self.phase is HarvestPhase.PENDING:
            self.started_at = at
        self.phase = phase

    def request_cancellation(self) -> None:
        """Ask a run to stop at its next checkpoint.

        A request rather than an act, because the run may be mid-query against
        someone else's warehouse. The run itself decides where stopping is safe.
        """
        if self.is_terminal:
            raise HarvestTransitionError("Cannot cancel a finished harvest run")
        self.cancellation_requested = True

    def complete(self, *, catalog_version_id: UUID, at: datetime) -> None:
        if self.is_terminal:
            raise HarvestTransitionError("Harvest run already finished")
        self.phase = HarvestPhase.COMPLETED
        self.catalog_version_id = catalog_version_id
        self.finished_at = at

    def cancel(self, *, at: datetime) -> None:
        if self.is_terminal:
            raise HarvestTransitionError("Harvest run already finished")
        self.phase = HarvestPhase.CANCELLED
        self.finished_at = at

    def fail(self, *, code: str, message: str, at: datetime) -> None:
        """End a run that could not continue.

        Reachable from any non-terminal phase, including ``PENDING``: a run
        whose process died before it started must still reach a terminal state
        rather than sitting in limbo where a reader cannot tell it from one that
        is merely slow.
        """
        if self.is_terminal:
            raise HarvestTransitionError("Harvest run already finished")
        self.phase = HarvestPhase.FAILED
        self.failure_code = code
        self.failure_message = message
        self.finished_at = at
