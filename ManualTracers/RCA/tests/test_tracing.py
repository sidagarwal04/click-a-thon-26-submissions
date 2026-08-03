from unittest.mock import MagicMock, patch

from app.tracing import record_query


def test_record_query_is_a_noop_outside_any_active_span():
    # the bug: query_rows() called directly (e.g. get_metric() from a FastAPI handler,
    # before any @traced(...) function runs) has no active OTel span. Langfuse's own
    # update_current_span() doesn't raise in that case — it logs "Context error: No active
    # span..." directly, which our try/except never sees since nothing was thrown. Skipping
    # the call entirely when there's no active span silences that log at the source.
    mock_client = MagicMock()
    with patch("app.tracing.get_langfuse", return_value=mock_client):
        record_query("SELECT 1", {}, "qid", 1, 0.01)
    mock_client.update_current_span.assert_not_called()


def test_record_query_is_a_noop_when_langfuse_is_not_configured():
    with patch("app.tracing.get_langfuse", return_value=None):
        record_query("SELECT 1", {}, "qid", 1, 0.01)  # must not raise
