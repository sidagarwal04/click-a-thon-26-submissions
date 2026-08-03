from sqlalchemy import CheckConstraint, UniqueConstraint

from zentra_adapter_postgres.schema import (
    investigation_threads,
    investigations,
    thread_messages,
)


def test_thread_tables_have_tenant_hierarchy_and_immutable_message_shape() -> None:
    thread_foreign_keys = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in investigation_threads.foreign_key_constraints
    }
    message_foreign_keys = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in thread_messages.foreign_key_constraints
    }

    assert ("projects.project_id", "projects.tenant_id") in thread_foreign_keys
    assert (
        "investigation_threads.thread_id",
        "investigation_threads.tenant_id",
    ) in message_foreign_keys
    assert "updated_at" not in thread_messages.c


def test_thread_message_and_title_bounds_are_database_invariants() -> None:
    checks = {
        constraint.name
        for table in (investigation_threads, thread_messages)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_investigation_threads_title_length" in checks
    assert "ck_thread_messages_content_length" in checks
    assert "ck_thread_messages_kind" in checks


def test_investigations_link_to_one_message_and_sequence_in_a_thread() -> None:
    uniques = {
        constraint.name
        for constraint in investigations.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    foreign_keys = {
        constraint.name for constraint in investigations.foreign_key_constraints
    }

    assert "uq_investigations_thread_sequence" in uniques
    assert "fk_investigations_thread_tenant" in foreign_keys
    assert "fk_investigations_initiating_message" in foreign_keys
