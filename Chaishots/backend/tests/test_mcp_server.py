from __future__ import annotations

import asyncio

from mcp import Client
from mcp.types import CallToolResult

from app.mcp_server import create_mcp_server
from app.schemas.features import ProcessFeatureResult
from tests.test_cli import FakePipeline


async def call_process_feature(service: FakePipeline) -> CallToolResult:
    async with Client(create_mcp_server(service)) as client:
        return await client.call_tool(
            "process_feature",
            {"feature_folder": "01_express_checkout"},
        )


def test_mcp_process_feature_uses_in_memory_v2_client_and_shared_pipeline() -> None:
    service = FakePipeline()

    tool_result = asyncio.run(call_process_feature(service))

    assert tool_result.is_error is False
    assert ProcessFeatureResult.model_validate(tool_result.structured_content) == (
        service.result
    )
    assert service.calls == [("process_feature", "01_express_checkout")]
