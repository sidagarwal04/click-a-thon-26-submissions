from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from zentra_domain_agent_execution import ModelMessage

from zentra_adapter_model_providers.cassette import (
    ReplayModelClient,
    UnrecordedRequestError,
)

MESSAGES = [ModelMessage(role="user", content="Why did EU refunds increase?")]


def write_cassette(directory: Path, *, cost: str) -> None:
    """One recording, keyed the way ReplayModelClient will look it up."""
    from zentra_adapter_model_providers.cassette import _key

    directory.mkdir(parents=True, exist_ok=True)
    key = _key(
        model="cube_analyst",
        system="system",
        messages=MESSAGES,
        response_schema=None,
    )
    (directory / f"{key}.json").write_text(
        json.dumps(
            {
                "requested_model": "cube_analyst",
                "text": '{"answer": "ok"}',
                "usage": {
                    "input_tokens": 1200,
                    "output_tokens": 300,
                    "cost_usd": cost,
                    "model": "claude-opus-5",
                },
                "fallbacks": ["cerebras/zai-glm-4.7: returned 402"],
            }
        )
    )


async def replay(directory: Path):
    return await ReplayModelClient(directory).complete(
        model="cube_analyst",
        system="system",
        messages=MESSAGES,
        max_tokens=4096,
    )


@pytest.mark.asyncio
async def test_replaying_costs_nothing_and_says_so(tmp_path: Path) -> None:
    """The pipeline writes this usage into agent_executions, which is what cost
    governance reads. Carrying the recorded cost through booked a premium run's
    spend again on every replay — and replay is meant to be the free path."""
    write_cassette(tmp_path, cost="0.0903")

    response = await replay(tmp_path)

    assert response.usage.cost_usd == Decimal("0")
    # Tokens and the served model still stand: they describe the recorded call,
    # and the independence check reads that model.
    assert response.usage.input_tokens == 1200
    assert response.usage.model == "claude-opus-5"
    assert response.fallbacks == ("cerebras/zai-glm-4.7: returned 402",)


@pytest.mark.asyncio
async def test_the_recording_still_remembers_what_it_cost(tmp_path: Path) -> None:
    write_cassette(tmp_path, cost="0.0903")
    recording = next(tmp_path.glob("*.json"))

    assert ReplayModelClient.recorded_cost(recording) == Decimal("0.0903")


@pytest.mark.asyncio
async def test_an_unrecorded_request_raises_rather_than_reaching_a_provider(
    tmp_path: Path,
) -> None:
    write_cassette(tmp_path, cost="0")

    with pytest.raises(UnrecordedRequestError):
        await ReplayModelClient(tmp_path).complete(
            model="cube_analyst",
            system="a prompt that changed since the recording",
            messages=MESSAGES,
            max_tokens=4096,
        )
