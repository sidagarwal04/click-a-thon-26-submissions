"""Test that ClickHouse query execution time is properly logged to Langfuse."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from librechat_client.client import AgentResult
from tracing import traced_run


def test_query_timing():
    """Simulate an agent result with ClickHouse tool calls that include execution time."""

    # Simulate a tool call to run_query with execution timing
    mock_result = AgentResult(
        output_text="I ran a query to count the rows in the events table. The result is 42 rows.",
        tool_calls=[
            {
                "name": "run_query",
                "arguments": {"query": "SELECT count() FROM events", "database": "atlys"},
                "call_id": "call_abc123",
                "output": {
                    "columns": ["count()"],
                    "rows": [{"count()": 42}],
                    "row_count": 1,
                    "truncated": False,
                    "execution_time_ms": 127.45  # This is the key field we're testing
                }
            },
            {
                "name": "list_tables",
                "arguments": {"database": "atlys"},
                "call_id": "call_def456",
                "output": {
                    "tables": [
                        {"table": "events", "engine": "MergeTree", "row_count": 1000},
                        {"table": "users", "engine": "MergeTree", "row_count": 500}
                    ],
                    "execution_time_ms": 23.12
                }
            }
        ],
        raw={},
        usage={
            "input": 2500,
            "output": 150,
            "total": 2650,
        }
    )

    # Log the result using the tracing wrapper (simulating what pipeline.py does)
    with traced_run(agent="test", spec="query_timing_test") as run:
        with run.span("analyze_data") as span:
            # Log the generation
            run.log(
                step="analyze_data_generation",
                input={"task": "Count rows in events table"},
                output=mock_result.output_text,
                usage=mock_result.usage,
                n_tool_calls=len(mock_result.tool_calls)
            )

            # Log each tool call with execution timing
            for i, tc in enumerate(mock_result.tool_calls):
                tool_metadata = {}
                tool_output = tc.get("output")

                # Extract execution_time_ms if present
                if isinstance(tool_output, dict) and "execution_time_ms" in tool_output:
                    tool_metadata["execution_time_ms"] = tool_output["execution_time_ms"]

                run.log(
                    step=f"analyze_data_tool[{i}]_{tc.get('name')}",
                    input=tc.get("arguments"),
                    output=tool_output,
                    **tool_metadata
                )

        print(f"✓ Trace created with query execution timing")
        print(f"  Trace URL: {run.url}")
        print(f"\nTool calls logged:")
        for i, tc in enumerate(mock_result.tool_calls):
            exec_time = tc["output"].get("execution_time_ms", "N/A")
            print(f"  [{i}] {tc['name']}: {exec_time}ms")

        print(f"\n✅ Expected in Langfuse:")
        print(f"  - Tool call #0 (run_query) should have execution_time_ms: 127.45")
        print(f"  - Tool call #1 (list_tables) should have execution_time_ms: 23.12")
        print(f"  - Both timings should be visible in the trace metadata")


if __name__ == "__main__":
    test_query_timing()
    import time
    time.sleep(1)  # Give flush time
    print("\n✅ Test completed - verify in Langfuse that execution times are logged!")
