from unittest.mock import MagicMock, patch

from atlys_agentic.flows.ingestion_flow import IngestionFlow, run


def test_approved_path_executes_ddl_and_runs_context_audit():
    with patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Infer_Schema", return_value="CREATE TABLE express_checkout (...)"), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Generate_MV", return_value=""), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Execute_DDL", return_value={"status": "ok", "table": "express_checkout", "version": 1, "error": None}) as mock_exec, \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Context_Diff", return_value={"additions": ["express_checkout.shown_amount"], "conflicts": [], "gaps": []}) as mock_diff, \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Context_Upsert", return_value=1) as mock_upsert, \
         patch("atlys_agentic.flows.ingestion_flow.tracing.new_trace", return_value="trace-1"), \
         patch("atlys_agentic.flows.ingestion_flow.tracing.span"):
        result = run(
            spec_id="01_express_checkout",
            table_name="express_checkout",
            input_fn=lambda _prompt: "APPROVE",
        )
    mock_exec.assert_called_once()
    mock_diff.assert_called_once()
    mock_upsert.assert_called_once()
    assert result["approved"] is True
    assert result["ddl_result"]["status"] == "ok"
    assert result["trace_id"] == "trace-1"


def test_rejected_path_never_touches_clickhouse():
    with patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Infer_Schema", return_value="CREATE TABLE express_checkout (...)"), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Generate_MV", return_value=""), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Execute_DDL") as mock_exec, \
         patch("atlys_agentic.flows.ingestion_flow.tracing.new_trace", return_value="trace-2"), \
         patch("atlys_agentic.flows.ingestion_flow.tracing.span"):
        result = run(
            spec_id="01_express_checkout",
            table_name="express_checkout",
            input_fn=lambda _prompt: "nope",
        )
    mock_exec.assert_not_called()
    assert result["approved"] is False


def test_only_literal_approve_string_passes_the_gate():
    with patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Infer_Schema", return_value="CREATE TABLE express_checkout (...)"), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Generate_MV", return_value=""), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Execute_DDL") as mock_exec, \
         patch("atlys_agentic.flows.ingestion_flow.tracing.new_trace", return_value="trace-3"), \
         patch("atlys_agentic.flows.ingestion_flow.tracing.span"):
        result = run(
            spec_id="01_express_checkout",
            table_name="express_checkout",
            input_fn=lambda _prompt: "approve",  # lowercase must NOT pass
        )
    mock_exec.assert_not_called()
    assert result["approved"] is False


def test_approved_path_executes_materialized_view_when_generated():
    mv_ddl = "CREATE MATERIALIZED VIEW IF NOT EXISTS express_checkout_daily_mv (...)"
    with patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Infer_Schema", return_value="CREATE TABLE express_checkout (...)"), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Generate_MV", return_value=mv_ddl), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Execute_DDL", return_value={"status": "ok", "table": "express_checkout", "version": 1, "error": None}) as mock_exec, \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Context_Diff", return_value={"additions": [], "conflicts": [], "gaps": []}), \
         patch("atlys_agentic.flows.ingestion_flow.tools.Tool_Context_Upsert"), \
         patch("atlys_agentic.flows.ingestion_flow.tracing.new_trace", return_value="trace-4"), \
         patch("atlys_agentic.flows.ingestion_flow.tracing.span"):
        result = run(
            spec_id="01_express_checkout",
            table_name="express_checkout",
            input_fn=lambda _prompt: "APPROVE",
        )
    assert mock_exec.call_count == 2
    assert result["approved"] is True
