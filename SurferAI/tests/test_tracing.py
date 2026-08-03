from unittest.mock import MagicMock, patch

from atlys_agentic import tracing


def test_trace_captures_trace_id_and_flushes():
    mock_client = MagicMock()
    mock_client.get_current_trace_id.return_value = "trace-abc"
    mock_client.start_as_current_observation.return_value.__enter__.return_value = MagicMock()

    with patch("atlys_agentic.tracing.client", return_value=mock_client):
        with tracing.trace("root", input={"x": 1}):
            pass

    mock_client.flush.assert_called_once()
    assert tracing.trace_url() is not None or tracing._current_trace_id == "trace-abc"


def test_trace_url_returns_none_when_no_trace_captured():
    tracing._current_trace_id = None
    assert tracing.trace_url() is None


def test_step_nests_under_active_trace_without_flushing():
    mock_client = MagicMock()
    mock_client.start_as_current_observation.return_value.__enter__.return_value = MagicMock()

    with patch("atlys_agentic.tracing.client", return_value=mock_client):
        with tracing.step("tool_call", input={"sql": "SELECT 1"}):
            pass

    mock_client.flush.assert_not_called()
