"""ScopedCubeSemanticLayers: the fix for the shared-catalog cross-tenant bug.

CubeSemanticLayer.catalog() caches for its own lifetime, so the property
that actually matters is: two different (tenant, Data Connection) pairs
never share an instance, and a stale instance is dropped as soon as its
Relations change or its TTL lapses — not just eventually.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from zentra_api.cube_scope import ScopedCubeSemanticLayers

TENANT_A = uuid4()
TENANT_B = uuid4()
CONNECTION_A = uuid4()
CONNECTION_B = uuid4()


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value


def _cache(
    *,
    fingerprints: dict[str, str] | None = None,
    clock: FakeClock | None = None,
):
    fingerprints = fingerprints or {}

    async def resolve(tenant_id, data_connection_id):
        return fingerprints[str(data_connection_id)]

    return ScopedCubeSemanticLayers(
        cube_url="http://unused",
        cube_api_secret=None,
        resolve_relation_fingerprint=resolve,
        now=clock or FakeClock(),
    )


@pytest.mark.asyncio
async def test_two_data_connections_never_share_an_instance() -> None:
    cache = _cache(fingerprints={str(CONNECTION_A): "fp-a", str(CONNECTION_B): "fp-b"})

    a = await cache.resolve(tenant_id=TENANT_A, data_connection_id=CONNECTION_A)
    b = await cache.resolve(tenant_id=TENANT_B, data_connection_id=CONNECTION_B)

    assert a is not b


@pytest.mark.asyncio
async def test_same_scope_within_ttl_reuses_the_cached_instance() -> None:
    cache = _cache(fingerprints={str(CONNECTION_A): "fp-a"})

    first = await cache.resolve(tenant_id=TENANT_A, data_connection_id=CONNECTION_A)
    second = await cache.resolve(tenant_id=TENANT_A, data_connection_id=CONNECTION_A)

    assert first is second


@pytest.mark.asyncio
async def test_a_confirmed_relation_invalidates_the_cache_even_within_ttl() -> None:
    """The gap a naive version-only cache key would have missed: confirming
    a Relation changes the fingerprint under the same TTL window, and that
    alone must be enough to stop serving the stale compiled schema."""
    fingerprints = {str(CONNECTION_A): "fp-before"}
    cache = _cache(fingerprints=fingerprints)

    before = await cache.resolve(tenant_id=TENANT_A, data_connection_id=CONNECTION_A)
    fingerprints[str(CONNECTION_A)] = "fp-after"
    after = await cache.resolve(tenant_id=TENANT_A, data_connection_id=CONNECTION_A)

    assert before is not after


@pytest.mark.asyncio
async def test_ttl_expiry_invalidates_even_with_an_unchanged_fingerprint() -> None:
    clock = FakeClock()
    cache = _cache(fingerprints={str(CONNECTION_A): "fp-a"}, clock=clock)

    before = await cache.resolve(tenant_id=TENANT_A, data_connection_id=CONNECTION_A)
    clock.value += 301.0  # past the 300s TTL
    after = await cache.resolve(tenant_id=TENANT_A, data_connection_id=CONNECTION_A)

    assert before is not after


@pytest.mark.asyncio
async def test_the_demo_warehouse_path_never_calls_the_fingerprint_resolver() -> None:
    """data_connection_id=None must not trigger a Connector lookup at all —
    it is the only path reachable before any Data Connection exists."""

    async def _unreachable(tenant_id, data_connection_id):
        raise AssertionError("must not be called for the demo warehouse path")

    cache = ScopedCubeSemanticLayers(
        cube_url="http://unused",
        cube_api_secret=None,
        resolve_relation_fingerprint=_unreachable,
    )

    await cache.resolve(tenant_id=TENANT_A, data_connection_id=None)
