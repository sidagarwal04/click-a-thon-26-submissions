from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from ._metadata import metadata

investigation_threads = Table(
    "investigation_threads",
    metadata,
    Column(
        "thread_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("project_id", UUID(as_uuid=True), nullable=False),
    Column("initiating_message_id", UUID(as_uuid=True), nullable=False),
    Column("title", Text, nullable=False),
    Column("status", String(16), nullable=False, server_default="draft"),
    Column("next_event_sequence", Integer, nullable=False, server_default="1"),
    Column("archived_from_status", String(16)),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "latest_activity_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("archived_at", TIMESTAMP(timezone=True)),
    ForeignKeyConstraint(
        ("project_id", "tenant_id"),
        ("projects.project_id", "projects.tenant_id"),
        name="fk_investigation_threads_project_tenant",
        ondelete="CASCADE",
    ),
    UniqueConstraint(
        "thread_id", "tenant_id", name="uq_investigation_threads_tenant_identity"
    ),
    CheckConstraint(
        "status IN ('draft', 'active', 'archived')",
        name="ck_investigation_threads_status",
    ),
    CheckConstraint(
        "archived_from_status IS NULL OR archived_from_status IN ('draft', 'active')",
        name="ck_investigation_threads_archived_from",
    ),
    CheckConstraint(
        "char_length(title) BETWEEN 1 AND 80",
        name="ck_investigation_threads_title_length",
    ),
    CheckConstraint(
        "next_event_sequence >= 1",
        name="ck_investigation_threads_event_sequence",
    ),
)
Index(
    "ix_investigation_threads_project_activity",
    investigation_threads.c.tenant_id,
    investigation_threads.c.project_id,
    investigation_threads.c.latest_activity_at.desc(),
    investigation_threads.c.thread_id.desc(),
)


thread_messages = Table(
    "thread_messages",
    metadata,
    Column(
        "message_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("thread_id", UUID(as_uuid=True), nullable=False),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("author_id", UUID(as_uuid=True)),
    Column("kind", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    ForeignKeyConstraint(
        ("thread_id", "tenant_id"),
        ("investigation_threads.thread_id", "investigation_threads.tenant_id"),
        name="fk_thread_messages_thread_tenant",
        ondelete="CASCADE",
    ),
    UniqueConstraint(
        "message_id",
        "thread_id",
        "tenant_id",
        name="uq_thread_messages_thread_tenant_identity",
    ),
    CheckConstraint(
        "kind IN ('user_question', 'user_clarification', "
        "'router_clarification', 'safe_system')",
        name="ck_thread_messages_kind",
    ),
    CheckConstraint(
        "char_length(content) BETWEEN 1 AND 4000",
        name="ck_thread_messages_content_length",
    ),
)
Index(
    "ix_thread_messages_thread_created",
    thread_messages.c.tenant_id,
    thread_messages.c.thread_id,
    thread_messages.c.created_at,
    thread_messages.c.message_id,
)

investigation_threads.append_constraint(
    ForeignKeyConstraint(
        ("initiating_message_id", "thread_id", "tenant_id"),
        (
            "thread_messages.message_id",
            "thread_messages.thread_id",
            "thread_messages.tenant_id",
        ),
        name="fk_investigation_threads_initiating_message",
        deferrable=True,
        initially="DEFERRED",
        use_alter=True,
    )
)
