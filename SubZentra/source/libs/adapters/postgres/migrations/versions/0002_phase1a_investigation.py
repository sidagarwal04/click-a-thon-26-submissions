"""Add the Phase 1A investigation lifecycle and audit outbox."""

from alembic import op
from sqlalchemy import TIMESTAMP, Column, Integer, String, inspect, text

from zentra_adapter_postgres.schema import audit_outbox

revision = "0002_phase1a"
down_revision = "0001_phase0"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {
        column["name"]
        for column in inspect(op.get_bind()).get_columns(table_name=table)
    }


def _indexes(table: str) -> set[str]:
    return {
        index["name"] for index in inspect(op.get_bind()).get_indexes(table_name=table)
    }


def upgrade() -> None:
    bind = op.get_bind()
    investigation_columns = _columns("investigations")

    if (
        "resolved_at" in investigation_columns
        and "finished_at" not in investigation_columns
    ):
        op.alter_column("investigations", "resolved_at", new_column_name="finished_at")
        investigation_columns.remove("resolved_at")
        investigation_columns.add("finished_at")
    if "scenario_key" not in investigation_columns:
        op.add_column("investigations", Column("scenario_key", String(64)))
    if "version" not in investigation_columns:
        op.add_column(
            "investigations",
            Column("version", Integer, nullable=False, server_default="1"),
        )
    if "evaluation_attempts" not in investigation_columns:
        op.add_column(
            "investigations",
            Column(
                "evaluation_attempts",
                Integer,
                nullable=False,
                server_default="0",
            ),
        )
    if "updated_at" not in investigation_columns:
        op.add_column(
            "investigations",
            Column(
                "updated_at",
                TIMESTAMP(timezone=True),
                nullable=False,
                server_default=text("now()"),
            ),
        )
    if "finished_at" not in investigation_columns:
        op.add_column(
            "investigations",
            Column("finished_at", TIMESTAMP(timezone=True)),
        )

    op.execute(
        "ALTER TABLE investigations DROP CONSTRAINT IF EXISTS "
        "ck_investigations_status"
    )
    op.execute(
        """
        UPDATE investigations
        SET status = CASE status
          WHEN 'in_progress' THEN 'running'
          WHEN 'pending_review' THEN 'awaiting_approval'
          WHEN 'resolved' THEN 'completed'
          WHEN 'cost_limited' THEN 'failed'
          ELSE status
        END
        """
    )
    op.create_check_constraint(
        "ck_investigations_status",
        "investigations",
        "status IN ('pending', 'running', 'evaluating', 'awaiting_approval', "
        "'completed', 'rejected', 'failed', 'cancelled')",
    )
    op.execute(
        "ALTER TABLE investigations DROP CONSTRAINT IF EXISTS ck_investigations_version"
    )
    op.create_check_constraint(
        "ck_investigations_version",
        "investigations",
        "version >= 1",
    )
    op.execute(
        "ALTER TABLE investigations DROP CONSTRAINT IF EXISTS "
        "ck_investigations_evaluation_attempts"
    )
    op.create_check_constraint(
        "ck_investigations_evaluation_attempts",
        "investigations",
        "evaluation_attempts >= 0 AND evaluation_attempts <= 3",
    )

    approval_columns = _columns("human_approvals")
    if "decision_reason" not in approval_columns:
        op.add_column(
            "human_approvals",
            Column("decision_reason", String(32)),
        )
    op.execute(
        "ALTER TABLE human_approvals DROP CONSTRAINT IF EXISTS "
        "ck_human_approvals_decision_reason"
    )
    op.create_check_constraint(
        "ck_human_approvals_decision_reason",
        "human_approvals",
        "decision_reason IS NULL OR decision_reason IN "
        "('insufficient_evidence', 'incorrect_interpretation', "
        "'policy_mismatch', 'needs_more_analysis')",
    )
    if "uq_human_approvals_one_pending" not in _indexes("human_approvals"):
        op.create_index(
            "uq_human_approvals_one_pending",
            "human_approvals",
            ["tenant_id", "investigation_id"],
            unique=True,
            postgresql_where=text("status = 'pending'"),
        )

    if "audit_outbox" not in inspect(bind).get_table_names():
        audit_outbox.create(bind=bind)
    op.execute("ALTER TABLE audit_outbox ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_outbox FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS audit_outbox_tenant_isolation ON audit_outbox")
    op.execute(
        """
        CREATE POLICY audit_outbox_tenant_isolation ON audit_outbox
        USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON audit_outbox TO zentra_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_outbox")
    op.drop_index(
        "uq_human_approvals_one_pending",
        table_name="human_approvals",
        if_exists=True,
    )
    op.execute(
        "ALTER TABLE human_approvals DROP CONSTRAINT IF EXISTS "
        "ck_human_approvals_decision_reason"
    )
    if "decision_reason" in _columns("human_approvals"):
        op.drop_column("human_approvals", "decision_reason")

    op.execute(
        "ALTER TABLE investigations DROP CONSTRAINT IF EXISTS "
        "ck_investigations_status"
    )
    op.execute(
        """
        UPDATE investigations
        SET status = CASE status
          WHEN 'pending' THEN 'in_progress'
          WHEN 'running' THEN 'in_progress'
          WHEN 'evaluating' THEN 'in_progress'
          WHEN 'awaiting_approval' THEN 'pending_review'
          WHEN 'completed' THEN 'resolved'
          WHEN 'rejected' THEN 'resolved'
          WHEN 'failed' THEN 'cost_limited'
          WHEN 'cancelled' THEN 'resolved'
          ELSE status
        END
        """
    )
    op.create_check_constraint(
        "ck_investigations_status",
        "investigations",
        "status IN ('in_progress', 'pending_review', 'resolved', 'cost_limited')",
    )
    op.execute(
        "ALTER TABLE investigations DROP CONSTRAINT IF EXISTS ck_investigations_version"
    )
    op.execute(
        "ALTER TABLE investigations DROP CONSTRAINT IF EXISTS "
        "ck_investigations_evaluation_attempts"
    )
    for column in ("updated_at", "evaluation_attempts", "version", "scenario_key"):
        if column in _columns("investigations"):
            op.drop_column("investigations", column)
    if "finished_at" in _columns("investigations"):
        op.alter_column("investigations", "finished_at", new_column_name="resolved_at")
