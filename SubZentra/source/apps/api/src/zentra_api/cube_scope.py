"""One CubeSemanticLayer per (tenant, Data Connection), never shared.

Fixes a real bug the naive version of dynamic per-tenant cubes would ship:
`CubeSemanticLayer.catalog()` caches its catalog for the instance's
lifetime. A single instance built once at boot and shared across every
tenant — which is what `dependencies.py` did before this module existed —
would silently serve tenant A's catalog to tenant B once cubes are
generated per tenant.

A short TTL plus a relation-fingerprint check (not the catalog version
alone) is what actually invalidates on a Relation confirm/reject/revoke,
since those mutate a Relation's state under the same CatalogVersion id —
see `connector_model.relation_fingerprint`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from uuid import UUID

from zentra_adapter_cube import CubeClient, CubeSemanticLayer

from .connector_model import ConnectorNotConfiguredError
from .cube_auth import mint_cube_token

#: Matches the JWT's own expiry (cube_auth.TOKEN_TTL) — a cached layer must
#: not outlive the token it was built with.
_CACHE_TTL_SECONDS = 300.0

RelationFingerprintResolver = Callable[[UUID, UUID], Awaitable[str]]


@dataclass(slots=True)
class _CacheEntry:
    semantic_layer: CubeSemanticLayer
    relation_fingerprint: str | None
    expires_at: float


class ScopedCubeSemanticLayers:
    def __init__(
        self,
        *,
        cube_url: str,
        cube_api_secret: str | None,
        resolve_relation_fingerprint: RelationFingerprintResolver,
        now: Callable[[], float] = monotonic,
    ) -> None:
        self._cube_url = cube_url
        self._cube_api_secret = cube_api_secret
        self._resolve_relation_fingerprint = resolve_relation_fingerprint
        self._now = now
        self._entries: dict[tuple[UUID, UUID | None], _CacheEntry] = {}

    async def resolve(
        self,
        *,
        tenant_id: UUID,
        data_connection_id: UUID | None,
    ) -> CubeSemanticLayer:
        fingerprint = (
            await self._resolve_relation_fingerprint(tenant_id, data_connection_id)
            if data_connection_id is not None
            else None
        )
        key = (tenant_id, data_connection_id)
        cached = self._entries.get(key)
        if (
            cached is not None
            and cached.expires_at > self._now()
            and cached.relation_fingerprint == fingerprint
        ):
            return cached.semantic_layer

        token = (
            mint_cube_token(
                str(tenant_id) if data_connection_id else None,
                str(data_connection_id) if data_connection_id else None,
                fingerprint,
                secret=self._cube_api_secret,
            )
            if self._cube_api_secret
            else None
        )
        semantic_layer = CubeSemanticLayer(CubeClient(self._cube_url, token))
        self._entries[key] = _CacheEntry(
            semantic_layer=semantic_layer,
            relation_fingerprint=fingerprint,
            expires_at=self._now() + _CACHE_TTL_SECONDS,
        )
        return semantic_layer


__all__ = [
    "ConnectorNotConfiguredError",
    "ScopedCubeSemanticLayers",
]
