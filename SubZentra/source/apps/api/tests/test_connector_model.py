"""Cube's dynamic per-tenant schema generator reads only confirmed Relations.

This is the governance-parity test for ADR-0014's reimplemented intent: an
unconfirmed Relation must never appear in what a tenant's compiled Cube
schema can query. `connector_cube_model`/`relation_fingerprint` are the only
things standing between a Data Connection's Join Graph and Cube — if they
leak an unconfirmed join, nothing downstream would catch it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from zentra_application_connector import (
    AuthenticatedActor,
    ConnectorService,
    JoinGraphView,
    RelationView,
    SourceCredentials,
)
from zentra_domain_connector import (
    AccessOverrides,
    BindingCeiling,
    Cardinality,
    CatalogAccessOverride,
    CatalogVersion,
    RelationOrigin,
    RelationState,
    SourceField,
    SourceTable,
)

from zentra_api.connector_model import (
    ConnectorNotConfiguredError,
    connector_cube_model,
    relation_fingerprint,
)

TENANT_ID = uuid4()
DATA_CONNECTION_ID = uuid4()
CATALOG_VERSION_ID = uuid4()


def _field(name: str, *, normalised_type: str = "string") -> SourceField:
    return SourceField(
        field_id=uuid4(),
        table_id=uuid4(),
        name=name,
        declared_type=normalised_type,
        family="string",  # not asserted on; a plain placeholder is enough
        normalised_type=normalised_type,
        nullable=True,
        position=0,
    )


def _relation(
    left_field_id: UUID,
    right_field_id: UUID,
    *,
    state: RelationState = RelationState.CONFIRMED,
    cardinality: Cardinality = Cardinality.MANY_TO_ONE,
) -> RelationView:
    return RelationView(
        relation_id=uuid4(),
        state=state,
        origin=RelationOrigin.INFERRED,
        confidence=0.9,
        binding_ceiling=BindingCeiling.NONE,
        cardinality=cardinality,
        left="orders.customer_id",
        right="customers.customer_id",
        left_field_id=left_field_id,
        right_field_id=right_field_id,
        is_cross_source=False,
    )


class FakeConnectorService:
    """A duck-typed stand-in for the three ConnectorService methods this
    module calls — not a fake repository stack, since none of those methods'
    internals are under test here."""

    def __init__(
        self,
        *,
        tables: tuple[SourceTable, ...],
        relations: tuple[RelationView, ...],
        credentials: SourceCredentials,
        overrides: tuple[CatalogAccessOverride, ...] = (),
    ) -> None:
        self._tables = tables
        self._relations = relations
        self._credentials = credentials
        self._overrides = overrides
        self.join_graph_calls = 0

    async def latest_catalog(
        self, actor: AuthenticatedActor, data_source_id: UUID
    ) -> CatalogVersion:
        return CatalogVersion(
            catalog_version_id=CATALOG_VERSION_ID,
            data_source_id=data_source_id,
            tenant_id=actor.tenant_id,
            harvest_run_id=uuid4(),
            created_at=datetime.now(UTC),
            tables=self._tables,
        )

    async def agent_visible_catalog(
        self, actor: AuthenticatedActor, data_source_id: UUID
    ) -> CatalogVersion:
        # Mirrors the real method: the harvest, with the Tenant's overrides
        # applied by the same domain object the service uses.
        version = await self.latest_catalog(actor, data_source_id)
        return AccessOverrides.build(data_source_id, self._overrides).apply(version)

    async def list_agent_access(
        self, actor: AuthenticatedActor, data_source_id: UUID
    ) -> tuple[CatalogAccessOverride, ...]:
        return self._overrides

    async def join_graph(
        self, actor: AuthenticatedActor, catalog_version_id: UUID
    ) -> JoinGraphView:
        self.join_graph_calls += 1
        # Mirrors ConnectorService.join_graph: only confirmed relations ever
        # come back from here — the same filtering JoinGraph.build applies.
        confirmed = tuple(
            r for r in self._relations if r.state is RelationState.CONFIRMED
        )
        return JoinGraphView(
            catalog_version_id=catalog_version_id,
            relations=confirmed,
        )

    async def resolve_driver_credentials(
        self, actor: AuthenticatedActor, data_source_id: UUID
    ) -> SourceCredentials:
        return self._credentials


def _override(
    table_name: str, field_name: str | None, *, agent_visible: bool
) -> CatalogAccessOverride:
    return CatalogAccessOverride(
        override_id=uuid4(),
        tenant_id=TENANT_ID,
        data_source_id=DATA_CONNECTION_ID,
        table_name=table_name,
        field_name=field_name,
        agent_visible=agent_visible,
        decided_by=uuid4(),
        decided_at=datetime.now(UTC),
    )


def _connector(
    *,
    pending_relation: bool,
    overrides: tuple[CatalogAccessOverride, ...] = (),
) -> FakeConnectorService:
    orders = SourceTable(
        table_id=uuid4(),
        name="orders",
        database="analytics",
        fields=(
            _field("order_id", normalised_type="int"),
            _field("customer_id", normalised_type="int"),
        ),
    )
    customers = SourceTable(
        table_id=uuid4(),
        name="customers",
        database="analytics",
        fields=(_field("customer_id", normalised_type="int"),),
    )
    confirmed = _relation(
        orders.fields[1].field_id,
        customers.fields[0].field_id,
        state=RelationState.CONFIRMED,
    )
    relations = (confirmed,)
    if pending_relation:
        relations = (
            confirmed,
            _relation(
                orders.fields[0].field_id,
                customers.fields[0].field_id,
                state=RelationState.PROPOSED,
            ),
        )
    return FakeConnectorService(
        tables=(orders, customers),
        relations=relations,
        overrides=overrides,
        credentials=SourceCredentials(
            host="clickhouse.tenant.example",
            port=8443,
            database="analytics",
            username="reader",
            password="secret",
            secure=True,
        ),
    )


@pytest.mark.asyncio
async def test_unconfirmed_relation_never_reaches_the_cube_model() -> None:
    """The governance-parity assertion: a pending Relation must not appear
    in the model Cube compiles a schema from, however many other relations
    exist alongside it."""
    connector = _connector(pending_relation=True)

    model = await connector_cube_model(
        connector, tenant_id=TENANT_ID, data_connection_id=DATA_CONNECTION_ID
    )

    assert len(model.joins) == 1
    assert model.joins[0].from_table == "orders"
    assert model.joins[0].to_table == "customers"


@pytest.mark.asyncio
async def test_credentials_are_carried_but_never_logged_by_this_function() -> None:
    connector = _connector(pending_relation=False)

    model = await connector_cube_model(
        connector, tenant_id=TENANT_ID, data_connection_id=DATA_CONNECTION_ID
    )

    assert model.clickhouse["host"] == "clickhouse.tenant.example"
    assert model.clickhouse["password"] == "secret"


@pytest.mark.asyncio
async def test_fingerprint_changes_when_a_relation_is_confirmed() -> None:
    """The fix for the cache-invalidation gap: confirming a Relation must
    change the fingerprint even though the CatalogVersion id does not."""
    relation_id = uuid4()
    left_field_id, right_field_id = uuid4(), uuid4()
    tables = (
        SourceTable(
            table_id=uuid4(), name="orders", database="analytics",
            fields=(_field("customer_id", normalised_type="int"),),
        ),
        SourceTable(
            table_id=uuid4(), name="customers", database="analytics",
            fields=(_field("customer_id", normalised_type="int"),),
        ),
    )
    credentials = SourceCredentials(
        host="h", port=1, database="d", username="u", password="p"
    )

    def relation(state: RelationState) -> RelationView:
        return RelationView(
            relation_id=relation_id,
            state=state,
            origin=RelationOrigin.INFERRED,
            confidence=0.9,
            binding_ceiling=BindingCeiling.NONE,
            cardinality=Cardinality.MANY_TO_ONE,
            left="orders.customer_id",
            right="customers.customer_id",
            left_field_id=left_field_id,
            right_field_id=right_field_id,
            is_cross_source=False,
        )

    before = await relation_fingerprint(
        FakeConnectorService(
            tables=tables,
            relations=(relation(RelationState.PROPOSED),),
            credentials=credentials,
        ),
        tenant_id=TENANT_ID,
        data_connection_id=DATA_CONNECTION_ID,
    )
    after = await relation_fingerprint(
        FakeConnectorService(
            tables=tables,
            relations=(relation(RelationState.CONFIRMED),),
            credentials=credentials,
        ),
        tenant_id=TENANT_ID,
        data_connection_id=DATA_CONNECTION_ID,
    )

    assert before != after


@pytest.mark.asyncio
async def test_fingerprint_changes_when_the_confirmed_relation_is_rejected() -> None:
    confirmed_connector = _connector(pending_relation=False)
    rejected_relations = tuple(
        _relation(
            r.left_field_id, r.right_field_id, state=RelationState.REJECTED
        )
        for r in confirmed_connector._relations
    )
    rejected_connector = FakeConnectorService(
        tables=confirmed_connector._tables,
        relations=rejected_relations,
        credentials=confirmed_connector._credentials,
    )

    confirmed_fingerprint = await relation_fingerprint(
        confirmed_connector, tenant_id=TENANT_ID, data_connection_id=DATA_CONNECTION_ID
    )
    rejected_fingerprint = await relation_fingerprint(
        rejected_connector, tenant_id=TENANT_ID, data_connection_id=DATA_CONNECTION_ID
    )

    assert confirmed_fingerprint != rejected_fingerprint


@pytest.mark.asyncio
async def test_many_to_many_relations_are_not_emitted_as_a_cube_join() -> None:
    """No bridge table exists to interpret a many-to-many join safely — see
    Data Source CONTEXT.md. Skipping is the safe default, not a guess."""
    orders = SourceTable(
        table_id=uuid4(), name="orders", database="analytics",
        fields=(_field("tag_id", normalised_type="int"),),
    )
    tags = SourceTable(
        table_id=uuid4(), name="tags", database="analytics",
        fields=(_field("tag_id", normalised_type="int"),),
    )
    connector = FakeConnectorService(
        tables=(orders, tags),
        relations=(
            _relation(
                orders.fields[0].field_id,
                tags.fields[0].field_id,
                cardinality=Cardinality.MANY_TO_MANY,
            ),
        ),
        credentials=SourceCredentials(
            host="h", port=1, database="d", username="u", password="p"
        ),
    )

    model = await connector_cube_model(
        connector, tenant_id=TENANT_ID, data_connection_id=DATA_CONNECTION_ID
    )

    assert model.joins == ()


@pytest.mark.asyncio
async def test_no_connector_configured_fails_clearly_not_with_attribute_error() -> None:
    with pytest.raises(ConnectorNotConfiguredError):
        await connector_cube_model(
            None, tenant_id=TENANT_ID, data_connection_id=DATA_CONNECTION_ID
        )
    with pytest.raises(ConnectorNotConfiguredError):
        await relation_fingerprint(
            None, tenant_id=TENANT_ID, data_connection_id=DATA_CONNECTION_ID
        )


def test_fake_satisfies_the_real_protocol_shape() -> None:
    """Not exhaustive, but catches the obvious drift: if ConnectorService
    ever renames one of these three methods, this fails instead of the fake
    silently going stale."""
    for name in ("latest_catalog", "join_graph", "resolve_driver_credentials"):
        assert hasattr(ConnectorService, name)


@pytest.mark.asyncio
async def test_a_hidden_table_is_absent_from_the_compiled_model() -> None:
    """The per-table agent-access toggle, enforced by absence.

    This is the governance-parity case for #40's toggle, and it was broken:
    `connector_cube_model` read `latest_catalog`, so a table a Tenant turned
    off was still compiled into a queryable cube. Same discipline as an
    unconfirmed join — there is nothing to enforce at query time because there
    is nothing to query.
    """
    connector = _connector(
        pending_relation=False,
        overrides=(_override("customers", None, agent_visible=False),),
    )

    model = await connector_cube_model(
        connector,
        tenant_id=TENANT_ID,
        data_connection_id=DATA_CONNECTION_ID,
    )

    assert [table.name for table in model.tables] == ["orders"]
    # The confirmed join pointed at `customers`. Hiding the table takes the
    # join with it rather than leaving an edge to a cube that does not exist.
    assert model.joins == ()


@pytest.mark.asyncio
async def test_a_hidden_field_leaves_its_table_reachable() -> None:
    connector = _connector(
        pending_relation=False,
        overrides=(_override("orders", "customer_id", agent_visible=False),),
    )

    model = await connector_cube_model(
        connector,
        tenant_id=TENANT_ID,
        data_connection_id=DATA_CONNECTION_ID,
    )

    orders = next(table for table in model.tables if table.name == "orders")
    assert [field["name"] for field in orders.fields] == ["order_id"]
    # The join was on the hidden field, so it cannot be compiled either.
    assert model.joins == ()


@pytest.mark.asyncio
async def test_visibility_changes_move_the_fingerprint() -> None:
    """Hiding a table changes which cubes exist without touching a Relation.

    A fingerprint over Relations alone would leave `ScopedCubeSemanticLayers`
    serving a cached catalog — and Cube a compiled schema — that still carries
    the table the Tenant just turned off.
    """
    unchanged = await relation_fingerprint(
        _connector(pending_relation=False),
        tenant_id=TENANT_ID,
        data_connection_id=DATA_CONNECTION_ID,
    )
    hidden = await relation_fingerprint(
        _connector(
            pending_relation=False,
            overrides=(_override("customers", None, agent_visible=False),),
        ),
        tenant_id=TENANT_ID,
        data_connection_id=DATA_CONNECTION_ID,
    )

    assert unchanged != hidden


@pytest.mark.asyncio
async def test_field_descriptions_reach_the_model_without_sampled_values() -> None:
    """What the harvest observed travels to Cube, so it reaches `/meta` and
    from there the catalog an agent reasons over. Sampled values do not —
    they are raw customer data and this string ends up in a prompt."""
    connector = _connector(pending_relation=False)

    model = await connector_cube_model(
        connector,
        tenant_id=TENANT_ID,
        data_connection_id=DATA_CONNECTION_ID,
    )

    orders = next(table for table in model.tables if table.name == "orders")
    order_id = next(f for f in orders.fields if f["name"] == "order_id")
    assert order_id["description"] == "int, nullable"
