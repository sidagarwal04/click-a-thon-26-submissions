"""Tests for Orchestrator Agent tools, raw path resolution, catalog discovery, and intent dispatch."""
from pathlib import Path

import pytest

from atlys_agentic import agents, conversational_ingestion, paths, tools_orchestrator


def test_resolve_path_or_spec_exact_id():
    res = tools_orchestrator.Tool_Resolve_Path_Or_Spec("01_express_checkout")
    assert res["found"] is True
    assert res["spec_id"] == "01_express_checkout"
    assert res["table_name"] == "express_checkout"
    assert res["has_events_ndjson"] is True


def test_resolve_path_or_spec_relative_path_with_spaces_and_slashes():
    res = tools_orchestrator.Tool_Resolve_Path_Or_Spec("problem statment/specs/01_express_checkout/")
    assert res["found"] is True
    assert res["spec_id"] == "01_express_checkout"
    assert res["table_name"] == "express_checkout"
    assert Path(res["spec_dir"]).exists()


def test_resolve_path_or_spec_direct_ndjson_file():
    res = tools_orchestrator.Tool_Resolve_Path_Or_Spec("problem statment/specs/01_express_checkout/events.ndjson")
    assert res["found"] is True
    assert res["spec_id"] == "01_express_checkout"
    assert res["table_name"] == "express_checkout"


def test_resolve_path_or_spec_fuzzy_name():
    res = tools_orchestrator.Tool_Resolve_Path_Or_Spec("express_checkout")
    assert res["found"] is True
    assert res["spec_id"] == "01_express_checkout"

    res_num = tools_orchestrator.Tool_Resolve_Path_Or_Spec("01")
    assert res_num["found"] is True
    assert res_num["spec_id"] == "01_express_checkout"


def test_resolve_path_or_spec_invalid_path():
    res = tools_orchestrator.Tool_Resolve_Path_Or_Spec("non_existent_folder/random_path_123")
    assert res["found"] is False
    assert res["spec_id"] == ""


def test_discover_workspace_paths():
    catalog = tools_orchestrator.Tool_Discover_Workspace_Paths()
    assert len(catalog) >= 5
    spec_ids = [c["spec_id"] for c in catalog]
    assert "01_express_checkout" in spec_ids
    assert "02_group_family" in spec_ids
    assert all("relative_path" in c for c in catalog)
    assert all("status" in c for c in catalog)


def test_batch_scan_specs():
    specs = tools_orchestrator.Tool_Batch_Scan_Specs("problem statment/specs")
    assert len(specs) >= 5
    ids = [s["spec_id"] for s in specs]
    assert "01_express_checkout" in ids
    assert "03_status_sharing" in ids


def test_detect_chat_intent_orchestrator_path_resolution():
    # 1. Raw path with spaces passed in chat
    intent, data = conversational_ingestion.detect_chat_intent(
        [{"role": "user", "content": "ingest problem statment/specs/01_express_checkout"}],
        model="atlys-instrumentation",
    )
    assert intent == "INGESTION_PROPOSAL"
    assert data["spec_id"] == "01_express_checkout"
    assert data["table_name"] == "express_checkout"

    # 2. Path discovery query
    intent_paths, _ = conversational_ingestion.detect_chat_intent(
        [{"role": "user", "content": "give me available paths"}],
        model="atlys-instrumentation",
    )
    assert intent_paths == "LIST_PATHS"

    # 3. Batch folder ingestion query
    intent_batch, data_batch = conversational_ingestion.detect_chat_intent(
        [{"role": "user", "content": "ingest folder problem statment/specs"}],
        model="atlys-instrumentation",
    )
    assert intent_batch == "BATCH_INGEST_PROPOSAL"
    assert "problem statment/specs" in data_batch["folder_path"]


def test_format_available_paths_card():
    card = conversational_ingestion.format_available_paths_card()
    assert "Workspace Ingestion Catalog & Available Paths" in card
    assert "`01_express_checkout`" in card
    assert "events.ndjson" in card


def test_format_batch_proposal_card():
    card = conversational_ingestion.format_batch_proposal_card("problem statment/specs")
    assert "Batch Ingestion Plan" in card
    assert "01_express_checkout" in card


def test_build_orchestrator_agent():
    agent = agents.build_orchestrator_agent()
    assert agent is not None
    assert "Orchestrator" in agent.role
    assert len(agent.tools) == 3
