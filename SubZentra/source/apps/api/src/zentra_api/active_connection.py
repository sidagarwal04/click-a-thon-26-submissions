"""Which Data Connection an Investigation queries.

`Investigation.data_connection_id` has existed since ADR-0012, and nothing ever
set it: every caller passed `None`, which means the demo warehouse. That was
invisible while the only questions were the two demo scenarios, because those
questions were *about* the demo warehouse. Free-text questions (ADR-0023) made
it a bug with a clear symptom — a tenant with a connected ClickHouse holding
`application_started` asked for an application count and was answered from
`Commerce.orderCount`, because the connected tables were never compiled into the
schema the Agent could see.

Resolved here, once, so the chat surface, the launcher and the catalog endpoint
cannot disagree about which data a tenant's question is asked against.
"""

from __future__ import annotations

from uuid import UUID

from zentra_application_connector import (
    AuthenticatedActor as ConnectorActor,
)
from zentra_application_connector import ConnectorService
from zentra_application_connector import Role as ConnectorRole
from zentra_application_investigation import AuthenticatedActor


class AmbiguousDataConnectionError(ValueError):
    """Several Data Connections exist and the caller named none.

    Refused rather than guessed. Picking one silently would answer a question
    against data the asker did not choose, which is the failure this module
    exists to fix — not one to reintroduce under a different name.
    """


async def active_data_connection_id(
    connector: ConnectorService | None,
    actor: AuthenticatedActor,
    *,
    requested: UUID | None = None,
) -> UUID | None:
    """The Data Connection this tenant's questions are asked against.

    `None` means the demo warehouse, which is correct only when the tenant has
    connected nothing. A tenant with exactly one connection gets it without
    having to say so; more than one has to be chosen between.
    """
    if requested is not None:
        return requested
    if connector is None:
        return None

    sources = await connector.list_sources(
        ConnectorActor(
            user_id=actor.user_id,
            tenant_id=actor.tenant_id,
            role=ConnectorRole(actor.role.value),
        )
    )
    if not sources:
        return None
    if len(sources) > 1:
        raise AmbiguousDataConnectionError(
            "This tenant has more than one Data Connection. "
            "Name the one to query."
        )
    return sources[0].data_source_id
