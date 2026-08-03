import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.clickhouse_client import _as_utc, get_client


def test_naive_datetime_is_labeled_utc_not_converted():
    # the bug: clickhouse_connect assumes a naive datetime is in the machine's LOCAL
    # timezone and converts it before binding. Every datetime this app produces is already
    # a UTC wall-clock value with no tzinfo — labeling it UTC must be a no-op on the wall
    # clock, not a conversion (regression for the ~5.5h-off compressed-replay silent miss).
    naive = datetime(2026, 8, 1, 21, 49, 42)
    result = _as_utc(naive)

    assert result == datetime(2026, 8, 1, 21, 49, 42, tzinfo=timezone.utc)
    assert result.hour == 21 and result.minute == 49


def test_already_aware_datetime_is_left_untouched():
    aware = datetime(2026, 8, 1, 21, 49, 42, tzinfo=timezone.utc)
    assert _as_utc(aware) is aware


def test_non_datetime_values_pass_through_unchanged():
    assert _as_utc("fill_rate") == "fill_rate"
    assert _as_utc(42) == 42
    assert _as_utc(None) is None


@pytest.mark.anyio
async def test_get_client_is_reused_and_built_only_once_under_concurrent_first_calls():
    # the old bug: one global sync client hit clickhouse_connect's own concurrency guard
    # ('Attempt to execute concurrent queries within the same session') the moment two
    # FastAPI threadpool threads queried at once. The async client's aiohttp connector pools
    # concurrent requests safely on one instance, so there's no per-thread client anymore —
    # just a single lazily-built client, guarded by a lock so concurrent first-callers (e.g.
    # global-series + segment-series firing together) don't each build their own.
    from app import clickhouse_client

    clickhouse_client._client = None  # isolate from any prior test's client

    build_count = 0

    async def fake_build(**kw):
        nonlocal build_count
        build_count += 1
        await asyncio.sleep(
            0.01
        )  # widen the race window so concurrent callers actually overlap
        return object()

    with patch(
        "app.clickhouse_client.clickhouse_connect.get_async_client",
        side_effect=fake_build,
    ):
        first, second, third = await asyncio.gather(
            get_client(), get_client(), get_client()
        )

    assert first is second is third
    assert build_count == 1
