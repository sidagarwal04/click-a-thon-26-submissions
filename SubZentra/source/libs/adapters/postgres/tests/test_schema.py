from zentra_adapter_postgres.schema import agent_registry, metadata


def test_phase_zero_tables_are_present_and_registry_is_schema_only() -> None:
    assert {
        "tenants",
        "users",
        "identity_subjects",
        "tenant_identity_bindings",
        "tenant_memberships",
        "investigations",
        "agent_executions",
        "human_approvals",
        "semantic_metrics",
        "agent_registry",
        "audit_outbox",
        # Phase 2, added beside the Phase 1 narrative Finding rather than
        # replacing it.
        "draft_findings",
        "draft_finding_claims",
        "evidence_citations",
        "draft_finding_claim_citations",
        "erasure_operations",
        # Phase 3 connector: a registered Data Source and its sealed
        # credential, plus what a harvest learned and what a reviewer decided.
        "data_sources",
        "catalog_versions",
        "relations",
        "harvest_runs",
        "catalog_agent_access",
        "workspace_groups",
        "projects",
        "investigation_threads",
        "thread_messages",
        "thread_events",
        "execution_jobs",
        "visualization_briefs",
        "visualization_artifacts",
        "visualization_actions",
        # The Investigation Engine's working memory: what an investigation has
        # established, what it still does not know, and the queue it works off
        # (ADR-0026). Migration 0020.
        "investigation_boards",
        "board_facts",
        "board_hypotheses",
        "board_gaps",
        "board_conflicts",
        "work_items",
        # Per-Tenant narrowing of the governed catalog (ADR-0027). The table
        # exists; nothing writes it yet, so every Tenant reads the whole
        # catalog.
        "analytical_scopes",
        # Sequence: a Dataset Workspace-owned graph of typed transform steps.
        "sequences",
        "sequence_steps",
        "prepared_tables",
        "sequence_runs",
        "sequence_final_tables",
    } == set(metadata.tables)
    assert agent_registry.c.enabled.server_default.arg.text == "false"
