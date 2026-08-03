"""Admit `evidence_incomplete` as a Human Approval reason.

The deterministic publication policy can gate a Draft Finding because a
substantive claim cites nothing, or cites evidence that cannot be followed.
That is a different thing to tell a reviewer than low confidence — the model
may be perfectly sure and the reviewer still unable to check a word of it — so
it gets its own reason rather than being folded into `tenant_policy`.
"""

from alembic import op

revision = "0010_evidence_incomplete_reason"
down_revision = "0009_evidence_citations"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_human_approvals_reason"
REASONS = (
    "low_confidence",
    "irreversible_action",
    "contradiction_unresolved",
    "regulatory_exposure",
    "tenant_policy",
    "evidence_incomplete",
)


def _check(reasons: tuple[str, ...]) -> str:
    values = ", ".join(f"'{reason}'" for reason in reasons)
    return f"reason IN ({values})"


def upgrade() -> None:
    op.execute(f"ALTER TABLE human_approvals DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE human_approvals ADD CONSTRAINT {CONSTRAINT} "
        f"CHECK ({_check(REASONS)})"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE human_approvals DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    # NOT VALID: an approval already recorded with the new reason must survive
    # a rollback rather than block it.
    op.execute(
        f"ALTER TABLE human_approvals ADD CONSTRAINT {CONSTRAINT} "
        f"CHECK ({_check(REASONS[:-1])}) NOT VALID"
    )
