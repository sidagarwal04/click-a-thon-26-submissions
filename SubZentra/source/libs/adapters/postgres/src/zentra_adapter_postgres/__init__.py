"""ZentraOS Postgres control-plane adapter"""

from .agent_access import PostgresAgentAccessRepository
from .connector import PostgresDataSourceRepository
from .connector_catalog import (
    PostgresCatalogRepository,
    PostgresHarvestRunRepository,
    PostgresRelationRepository,
)
from .database import Database
from .execution_job import PostgresExecutionJobRepository
from .identity import (
    IdentityContext,
    IdentityNotBoundError,
    resolve_identity_context,
)
from .investigation import (
    ConcurrentInvestigationUpdateError,
    OutboxRecord,
    PostgresInvestigationUnitOfWork,
    PostgresInvestigationUnitOfWorkFactory,
)
from .schema import metadata
from .sequence import (
    PostgresSequenceRepository,
    PostgresSequenceUnitOfWork,
    PostgresSequenceUnitOfWorkFactory,
)
from .thread import (
    PostgresThreadRepository,
    PostgresThreadUnitOfWork,
    PostgresThreadUnitOfWorkFactory,
)
from .visualization import PostgresVisualizationRepository
from .work_feed import PostgresWorkFeedRepository
from .workspace import (
    PostgresOrganizationRepository,
    PostgresOrganizationUnitOfWork,
    PostgresOrganizationUnitOfWorkFactory,
)

__all__ = [
    "Database",
    "IdentityContext",
    "IdentityNotBoundError",
    "ConcurrentInvestigationUpdateError",
    "OutboxRecord",
    "PostgresAgentAccessRepository",
    "PostgresCatalogRepository",
    "PostgresDataSourceRepository",
    "PostgresHarvestRunRepository",
    "PostgresExecutionJobRepository",
    "PostgresInvestigationUnitOfWork",
    "PostgresInvestigationUnitOfWorkFactory",
    "PostgresOrganizationRepository",
    "PostgresOrganizationUnitOfWork",
    "PostgresOrganizationUnitOfWorkFactory",
    "PostgresRelationRepository",
    "PostgresSequenceRepository",
    "PostgresSequenceUnitOfWork",
    "PostgresSequenceUnitOfWorkFactory",
    "PostgresThreadRepository",
    "PostgresThreadUnitOfWork",
    "PostgresThreadUnitOfWorkFactory",
    "PostgresWorkFeedRepository",
    "PostgresVisualizationRepository",
    "metadata",
    "resolve_identity_context",
]
