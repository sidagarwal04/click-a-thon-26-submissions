"""Test that usage tracking works correctly with the updated Langfuse wrapper."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from librechat_client.client import AgentResult
from tracing import traced_run


def test_usage_tracking():
    """Simulate an agent result with usage data to verify it logs correctly."""

    # Create a mock AgentResult as if it came from LibreChat
    mock_result = AgentResult(
        output_text="This is the agent's response with some generated content.",
        tool_calls=[
            {
                "name": "execute_query",
                "arguments": {"query": "SELECT count() FROM table"},
                "call_id": "call_123",
                "output": "42"
            }
        ],
        raw={},
        usage={
            "input": 1500,
            "output": 500,
            "total": 2000,
        }
    )

    # Log the result using the tracing wrapper
    with traced_run(agent="test", spec="usage_tracking_test") as run:
        # Test logging with usage data
        run.log(
            step="test_agent_generation",
            input={"query": "Generate a test response"},
            output=mock_result.output_text,
            usage=mock_result.usage,
            reasoning="Testing token usage tracking"
        )

        # Test logging tool calls
        for i, tc in enumerate(mock_result.tool_calls):
            run.log(
                step=f"test_tool[{i}]_{tc.get('name')}",
                input=tc.get("arguments"),
                output=tc.get("output")
            )

        print(f"✓ Trace created with usage tracking")
        print(f"  Trace URL: {run.url}")
        print(f"  Usage: {mock_result.usage}")
        print(f"\nExpected in Langfuse:")
        print(f"  - Generation observation (not span) for 'test_agent_generation'")
        print(f"  - Input tokens: {mock_result.usage['input']}")
        print(f"  - Output tokens: {mock_result.usage['output']}")
        print(f"  - Total tokens: {mock_result.usage['total']}")
        print(f"  - Tool call spans for each tool")


if __name__ == "__main__":
    test_usage_tracking()
    import time
    time.sleep(1)  # Give flush time
    print("\n✅ Test completed - check the trace URL above in Langfuse to verify:")
    print("   1. Token counts are visible")
    print("   2. Input/output are logged")
    print("   3. The observation type is 'generation' (not 'span')")
