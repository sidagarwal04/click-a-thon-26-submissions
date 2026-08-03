from zentra_adapter_postgres.schema import (
    thread_events,
    visualization_actions,
    visualization_artifacts,
    visualization_briefs,
)


def _foreign_key_names(table: object) -> set[str]:
    return {value.name for value in table.foreign_key_constraints}


def test_chat_tables_use_tenant_scoped_foreign_keys_and_retry_lineage() -> None:
    assert "fk_thread_events_thread_tenant" in _foreign_key_names(thread_events)
    assert {
        "fk_visualization_artifacts_brief_tenant",
        "fk_visualization_artifacts_investigation_tenant",
        "fk_visualization_artifacts_retry_tenant",
    } <= _foreign_key_names(visualization_artifacts)
    assert {
        "fk_visualization_actions_artifact_tenant",
        "fk_visualization_actions_thread_tenant",
        "fk_visualization_actions_investigation_tenant",
    } <= _foreign_key_names(visualization_actions)
    assert "fk_visualization_briefs_investigation_tenant" in _foreign_key_names(
        visualization_briefs
    )


def test_visualization_content_is_nullable_for_transactional_erasure() -> None:
    assert visualization_briefs.c.content.nullable
    assert visualization_artifacts.c.c1_response.nullable
    assert {"erased_at", "erasure_category"} <= set(visualization_artifacts.c.keys())
