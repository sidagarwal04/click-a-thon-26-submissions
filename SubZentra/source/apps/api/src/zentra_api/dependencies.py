from __future__ import annotations

import asyncio
import os
import socket
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from zentra_adapter_clickhouse import (
    AesGcmCredentialCipher,
    AuditRepository,
    ClickHouseLandingZone,
    ClickHouseSourceConnector,
)
from zentra_adapter_cube import CubeClient
from zentra_adapter_langgraph import IntakeAgent
from zentra_adapter_model_providers import (
    ModelTier,
    ProviderCircuitBreaker,
    ProviderClients,
    RoutedModelClient,
)
from zentra_adapter_postgres import (
    Database,
    PostgresAgentAccessRepository,
    PostgresCatalogRepository,
    PostgresDataSourceRepository,
    PostgresHarvestRunRepository,
    PostgresInvestigationUnitOfWorkFactory,
    PostgresOrganizationUnitOfWorkFactory,
    PostgresRelationRepository,
    PostgresThreadUnitOfWorkFactory,
)
from zentra_adapter_telemetry import (
    record_evidence_deletion,
    record_publication_decision,
)
from zentra_adapter_thesys import ThesysC1Client
from zentra_application_connector import ConnectorService
from zentra_application_investigation import (
    ExecutionJobWorker,
    IntakeService,
    InvestigationService,
    OrganizationService,
    ThreadService,
    VisualizationService,
)
from zentra_domain_agent_execution import SemanticLayerPort

from .audit_delivery import AuditDeliveryCoordinator
from .auth import ClerkJwtVerifier
from .connector_model import relation_fingerprint
from .cube_scope import ScopedCubeSemanticLayers
from .orchestrator_loop import OrchestratorLoop, build_agents_factory
from .pipeline import PostgresExecutionRecorder
from .registry import PostgresAgentRegistry
from .settings import Settings


class HealthProbe(Protocol):
    async def health(self) -> bool: ...


class _UtcClock:
    """The Connector's `Clock` port.

    A class rather than the `now=lambda` the Investigation service takes,
    because that port asks for an object with a `now()` method.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(slots=True)
class AppDependencies:
    database: Database
    audit: AuditRepository
    cube: CubeClient
    #: Per (tenant, Data Connection) governed catalogs. Held here as well as
    #: inside the pipeline because the catalog is now read on the request path
    #: too — a client that must offer a question needs to know what this tenant
    #: can actually be asked about.
    semantic_layers: ScopedCubeSemanticLayers
    models: ProviderClients
    jwt_verifier: ClerkJwtVerifier
    investigations: InvestigationService
    audit_delivery: AuditDeliveryCoordinator
    organization: OrganizationService
    threads: ThreadService
    execution_worker: ExecutionJobWorker
    execution_worker_enabled: bool
    registry: PostgresAgentRegistry
    visualizations: VisualizationService | None = None
    #: Absent when `CONNECTOR_CREDENTIAL_KEY` is unset. `None` rather than a
    #: service with no key: the Connector routes then fail with a message
    #: naming the missing configuration, instead of accepting a password they
    #: cannot seal. Last because a defaulted field must follow the required ones.
    #: The internal Cube model endpoint and connector_model.py's functions
    #: fail the same way — a clear, typed error rather than an
    #: AttributeError — whenever this is unset.
    worker_task: asyncio.Task[None] | None = None
    connector: ConnectorService | None = None
    #: Exposed so routes that need a raw, tenant-scoped Cube query (bypassing
    #: `CubeSemanticLayer.query()`'s governed-metrics gate) can reach one —
    #: `connector_rows_routes.py` is the only current caller.
    cube_semantic_layers: ScopedCubeSemanticLayers | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> AppDependencies:
        database = Database(settings.database_url)
        audit = AuditRepository.connect(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_username,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
            secure=settings.clickhouse_secure,
        )
        # Unauthenticated: /readyz needs no token, and a health probe must
        # not depend on a JWT's expiry.
        cube = CubeClient(settings.cube_url, None)
        unit_of_work_factory = PostgresInvestigationUnitOfWorkFactory(database)
        registry = PostgresAgentRegistry(database)
        recorder = PostgresExecutionRecorder(unit_of_work_factory)

        # A provider with no key is simply absent from the chain, so the whole
        # system still runs on ANTHROPIC_API_KEY alone.
        models = ProviderClients.from_keys(settings.provider_api_keys())
        # Shared across tiers: the limits being tripped belong to our API keys,
        # not to any one tenant.
        breaker = ProviderCircuitBreaker()

        connector: ConnectorService | None = None

        async def resolve_relation_fingerprint(
            tenant_id: UUID, data_connection_id: UUID
        ) -> str:
            return await relation_fingerprint(
                connector,
                tenant_id=tenant_id,
                data_connection_id=data_connection_id,
            )

        semantic_layers = ScopedCubeSemanticLayers(
            cube_url=settings.cube_url,
            cube_api_secret=settings.cube_api_secret,
            resolve_relation_fingerprint=resolve_relation_fingerprint,
        )

        # ADR-0026: the Investigation Engine's Board and Work Item queue
        # are the platform controller. There is no graph to build any more —
        # the loop holds the Agents directly.
        #
        # The registry is what makes the planner fail closed: it refuses the
        # run outright when a required role has no enabled, eval-passing agent,
        # rather than fanning out to a capability nobody promoted.
        agents_factories = {
            tier: build_agents_factory(
                tier=tier, models=models, breaker=breaker, registry=registry
            )
            for tier in ModelTier
        }

        audit_delivery = AuditDeliveryCoordinator(
            unit_of_work_factory=unit_of_work_factory,
            audit=audit,
        )
        investigations = InvestigationService(
            unit_of_work_factory=unit_of_work_factory,
            pipeline=OrchestratorLoop(
                agents_factories,
                semantic_layers,
                unit_of_work_factory=unit_of_work_factory,
                recorder=recorder,
                # Checked between Work Items, which is the only safe place to
                # stop: a cancellation observed mid-call would abandon an Agent
                # Execution the ledger has already announced.
                cancellation_checkpoint=recorder.cancellation_checkpoint,
            ),
            audit_writer=audit_delivery,
            audit_reader=audit_delivery,
            now=lambda: datetime.now(UTC),
            new_id=uuid4,
            publication_observer=record_publication_decision,
            erasure_observer=record_evidence_deletion,
        )
        organization = OrganizationService(
            unit_of_work_factory=PostgresOrganizationUnitOfWorkFactory(database),
            now=lambda: datetime.now(UTC),
            new_id=uuid4,
        )
        # Free tier: Intake is a light classification call, not the deep
        # analysis a tenant's paid tier buys.
        intake_model = RoutedModelClient(
            tier=ModelTier.FREE,
            clients=models.as_dict(),
            breaker=breaker,
        )

        def _build_intake_agent(semantic_layer: SemanticLayerPort) -> IntakeAgent:
            return IntakeAgent(model=intake_model, semantic_layer=semantic_layer)

        async def _resolve_intake_semantic_layer(
            tenant_id: UUID, data_connection_id: UUID | None
        ) -> SemanticLayerPort:
            return await semantic_layers.resolve(
                tenant_id=tenant_id, data_connection_id=data_connection_id
            )

        threads = ThreadService(
            unit_of_work_factory=PostgresThreadUnitOfWorkFactory(database),
            intake=IntakeService(
                agent_factory=_build_intake_agent,
                resolve_semantic_layer=_resolve_intake_semantic_layer,
                new_id=uuid4,
            ),
            now=lambda: datetime.now(UTC),
            new_id=uuid4,
        )
        visualizations = VisualizationService(
            unit_of_work_factory=unit_of_work_factory,
            renderer=(
                ThesysC1Client(
                    api_key=settings.thesys_api_key,
                    model=settings.thesys_model,
                    input_price_per_million=Decimal(
                        str(settings.thesys_input_price_per_million)
                    ),
                    output_price_per_million=Decimal(
                        str(settings.thesys_output_price_per_million)
                    ),
                )
                if settings.thesys_api_key
                else None
            ),
            now=lambda: datetime.now(UTC),
            new_id=uuid4,
            continuation=threads,
        )
        connector = (
            ConnectorService(
                sources=PostgresDataSourceRepository(database),
                catalogs=PostgresCatalogRepository(database),
                relations=PostgresRelationRepository(database),
                runs=PostgresHarvestRunRepository(database),
                access=PostgresAgentAccessRepository(database),
                connector=ClickHouseSourceConnector(),
                # The key comes from Settings rather than `from_env` so it is
                # read the same way as every other secret, and one .env file
                # remains the single place configuration lives.
                cipher=AesGcmCredentialCipher(
                    bytes.fromhex(settings.connector_credential_key)
                ),
                landing_zone=ClickHouseLandingZone(
                    host=settings.clickhouse_host,
                    port=settings.clickhouse_port,
                    username=settings.clickhouse_username,
                    password=settings.clickhouse_password,
                    secure=settings.clickhouse_secure,
                ),
                clock=_UtcClock(),
            )
            if settings.connector_credential_key
            else None
        )
        worker_id = settings.execution_worker_id or (
            f"{socket.gethostname()}:{os.getpid()}"
        )
        execution_worker = ExecutionJobWorker(
            unit_of_work_factory=unit_of_work_factory,
            executor=investigations,
            visualization_executor=visualizations,
            worker_id=worker_id,
            now=lambda: datetime.now(UTC),
        )
        return cls(
            database=database,
            audit=audit,
            cube=cube,
            semantic_layers=semantic_layers,
            models=models,
            jwt_verifier=ClerkJwtVerifier(
                settings.clerk_issuer,
                settings.clerk_audience,
            ),
            investigations=investigations,
            audit_delivery=audit_delivery,
            organization=organization,
            threads=threads,
            execution_worker=execution_worker,
            execution_worker_enabled=settings.execution_worker_enabled,
            registry=registry,
            visualizations=visualizations,
            connector=connector,
            cube_semantic_layers=semantic_layers,
        )

    async def start(self) -> None:
        self.audit_delivery.start()
        if self.execution_worker_enabled and self.worker_task is None:
            self.worker_task = asyncio.create_task(
                self.execution_worker.run_forever(),
                name="investigation-execution-worker",
            )

    async def stop(self) -> None:
        self.execution_worker.stop()
        if self.worker_task is not None:
            self.worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.worker_task
            self.worker_task = None
        await self.audit_delivery.stop()

    async def close(self) -> None:
        await self.database.close()
        await self.audit.close()
        await self.models.close()


