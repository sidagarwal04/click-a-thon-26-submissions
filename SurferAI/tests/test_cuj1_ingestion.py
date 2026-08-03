"""Tests for CUJ 1: Schema Ingestion, Evolution, Invariants, and Conversational HITL."""
from unittest.mock import MagicMock, patch

import pytest

from atlys_agentic import conversational_ingestion, paths, tools
from atlys_agentic.flows import ingestion_flow


def test_validate_invariants_passes_compliant_ddl():
    valid_ddl = (
        "CREATE TABLE test_table (\n"
        "    timestamp DateTime64(3),\n"
        "    user_id String,\n"
        "    device_type LowCardinality(String)\n"
        ") ENGINE = MergeTree\n"
        "PARTITION BY toYYYYMM(timestamp)\n"
        "ORDER BY (timestamp, user_id)\n"
        "TTL timestamp + INTERVAL 12 MONTH;"
    )
    violations = tools.Tool_Validate_Invariants(valid_ddl)
    assert violations == []


def test_validate_invariants_catches_all_four_violations():
    # 1. id-first ordering
    ddl_id_first = "CREATE TABLE t (id String, timestamp DateTime) ENGINE = MergeTree ORDER BY (id, timestamp) PARTITION BY toYYYYMM(timestamp) TTL timestamp + INTERVAL 12 MONTH;"
    assert any("id" in v.lower() for v in tools.Tool_Validate_Invariants(ddl_id_first))


    # 2. UUID-first ordering
    ddl_uuid_first = "CREATE TABLE t (user_uuid UUID, timestamp DateTime) ENGINE = MergeTree ORDER BY (user_uuid, timestamp) PARTITION BY toYYYYMM(timestamp) TTL timestamp + INTERVAL 12 MONTH;"
    assert any("uuid" in v.lower() for v in tools.Tool_Validate_Invariants(ddl_uuid_first))


    # 3. Missing PARTITION BY
    ddl_no_part = "CREATE TABLE t (timestamp DateTime, user_id String) ENGINE = MergeTree ORDER BY (timestamp, user_id) TTL timestamp + INTERVAL 12 MONTH;"
    assert any("PARTITION BY clause is missing" in v for v in tools.Tool_Validate_Invariants(ddl_no_part))

    # 4. Missing TTL
    ddl_no_ttl = "CREATE TABLE t (timestamp DateTime, user_id String) ENGINE = MergeTree ORDER BY (timestamp, user_id) PARTITION BY toYYYYMM(timestamp);"
    assert any("TTL clause is missing" in v for v in tools.Tool_Validate_Invariants(ddl_no_ttl))


def test_detect_chat_intent_catalog_discovery():
    intent, _ = conversational_ingestion.detect_chat_intent([{"role": "user", "content": "what specs are available?"}])
    assert intent == "LIST_SPECS"


def test_detect_chat_intent_proposal_and_token_extraction():
    # User asks for proposal
    intent, data = conversational_ingestion.detect_chat_intent(
        [{"role": "user", "content": "ingest 01_express_checkout"}],
        model="atlys-instrumentation",
    )
    assert intent == "INGESTION_PROPOSAL"
    assert data["spec_id"] == "01_express_checkout"

    # Assistant gives proposal with embedded token
    proposal_content = (
        "### Schema Proposal — `express_checkout`\n\n"
        "<!-- atlys:proposal spec_id=01_express_checkout table=express_checkout trace=trace-123 -->"
    )

    # Follow-up question preserves context
    intent2, data2 = conversational_ingestion.detect_chat_intent([
        {"role": "user", "content": "ingest 01_express_checkout"},
        {"role": "assistant", "content": proposal_content},
        {"role": "user", "content": "why not order by application_id first?"},
    ])
    assert intent2 == "INGESTION_FOLLOWUP"
    assert data2["spec_id"] == "01_express_checkout"
    assert data2["table_name"] == "express_checkout"

    # User says APPROVE
    intent3, data3 = conversational_ingestion.detect_chat_intent([
        {"role": "user", "content": "ingest 01_express_checkout"},
        {"role": "assistant", "content": proposal_content},
        {"role": "user", "content": "APPROVE"},
    ])
    assert intent3 == "HITL_APPROVE"
    assert data3["spec_id"] == "01_express_checkout"
    assert data3["table_name"] == "express_checkout"
    assert data3["trace_id"] == "trace-123"

    # User says reject
    intent4, data4 = conversational_ingestion.detect_chat_intent([
        {"role": "user", "content": "ingest 01_express_checkout"},
        {"role": "assistant", "content": proposal_content},
        {"role": "user", "content": "reject"},
    ])
    assert intent4 == "HITL_REJECT"
    assert data4["spec_id"] == "01_express_checkout"


def test_generate_proposal_and_deploy_in_dry_run_mode():
    prop_state = ingestion_flow.generate_proposal("01_express_checkout", dry_run=True)
    assert prop_state.table_name == "express_checkout"
    assert "<!-- atlys:proposal" in prop_state.proposal_md
    assert prop_state.violations == []

    # Deploy approved proposal
    deploy_state = ingestion_flow.deploy_approved_proposal(
        spec_id="01_express_checkout",
        table_name="express_checkout",
        trace_id=prop_state.trace_id,
        dry_run=True,
    )
    assert deploy_state.approved is True
    assert deploy_state.receipt_md is not None
    assert "Reasoning chain" in deploy_state.receipt_md
    assert "outputs/submission/01_express_checkout/" in deploy_state.receipt_md
