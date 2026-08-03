"""Carry the measurement an observed claim rests on.

`Claim` recorded prose and a `kind`. The Insight Agent validates each observed
claim against the validated aggregate — metric, value, and the period that
value covers — and all three were discarded before persistence, which left
`observed` as a label a reader had to take on trust.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0008_claim_measurement"
down_revision = "0007_register_insight_agent"
branch_labels = None
depends_on = None

COLUMNS = {"metric": sa.Text(), "claim_value": sa.Text(), "period": sa.Text()}
CONSTRAINT = "ck_draft_finding_claims_observed_is_measured"


def _existing() -> set[str]:
    return {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("draft_finding_claims")
    }


def _constraints() -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(op.get_bind()).get_check_constraints(
            "draft_finding_claims"
        )
    }


def upgrade() -> None:
    # 0001 builds from `schema.py` via create_all, so a fresh database already
    # has these and only an upgrade from 0006 needs them added.
    existing = _existing()
    for name, kind in COLUMNS.items():
        if name not in existing:
            op.add_column("draft_finding_claims", sa.Column(name, kind))

    if CONSTRAINT not in _constraints():
        op.create_check_constraint(
            CONSTRAINT,
            "draft_finding_claims",
            "kind <> 'observed' OR (metric IS NOT NULL AND claim_value IS NOT NULL)",
        )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE draft_finding_claims DROP CONSTRAINT IF EXISTS {CONSTRAINT}"
    )
    existing = _existing()
    for name in COLUMNS:
        if name in existing:
            op.drop_column("draft_finding_claims", name)
