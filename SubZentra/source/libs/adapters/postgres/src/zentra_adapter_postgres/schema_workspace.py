from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from ._metadata import metadata

workspace_groups = Table(
    "workspace_groups",
    metadata,
    Column(
        "group_id",
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
    Column("name", Text, nullable=False),
    Column("normalized_name", Text, nullable=False),
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
    Column("archived_at", TIMESTAMP(timezone=True)),
    UniqueConstraint(
        "tenant_id",
        "normalized_name",
        name="uq_workspace_groups_tenant_name",
    ),
    UniqueConstraint(
        "group_id",
        "tenant_id",
        name="uq_workspace_groups_tenant_identity",
    ),
    CheckConstraint(
        "char_length(name) BETWEEN 1 AND 100",
        name="ck_workspace_groups_name_length",
    ),
)
Index(
    "ix_workspace_groups_tenant_activity",
    workspace_groups.c.tenant_id,
    workspace_groups.c.updated_at.desc(),
    workspace_groups.c.group_id.desc(),
)


projects = Table(
    "projects",
    metadata,
    Column(
        "project_id",
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
    Column("group_id", UUID(as_uuid=True), nullable=False),
    Column("name", Text, nullable=False),
    Column("normalized_name", Text, nullable=False),
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
        ("group_id", "tenant_id"),
        ("workspace_groups.group_id", "workspace_groups.tenant_id"),
        name="fk_projects_group_tenant",
        ondelete="CASCADE",
    ),
    UniqueConstraint(
        "tenant_id",
        "group_id",
        "normalized_name",
        name="uq_projects_group_name",
    ),
    UniqueConstraint(
        "project_id",
        "tenant_id",
        name="uq_projects_tenant_identity",
    ),
    CheckConstraint(
        "char_length(name) BETWEEN 1 AND 100",
        name="ck_projects_name_length",
    ),
)
Index(
    "ix_projects_group_activity",
    projects.c.tenant_id,
    projects.c.group_id,
    projects.c.latest_activity_at.desc(),
    projects.c.project_id.desc(),
)
