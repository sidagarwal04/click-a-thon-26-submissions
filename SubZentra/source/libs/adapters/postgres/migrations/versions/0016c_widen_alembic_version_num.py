"""Widen alembic_version.version_num before it must hold a 33-char revision.

Alembic's default VARCHAR(32) cannot hold "0017_chat_work_feed_visualization"
(33 characters). This repo's revision ids are full descriptive filenames, not
short hashes, so 32 characters is too tight a ceiling in general. This has to
land on the 0016_durable_execution_jobs branch, strictly before 0017 is ever
applied — by the time a later migration could widen the column, Alembic has
already tried (and failed) to write the too-long value while recording 0017
as current.
"""

import sqlalchemy as sa
from alembic import op

revision = "0016c_widen_alembic_version_num"
down_revision = "0016_durable_execution_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(255),
        existing_type=sa.String(32),
    )


def downgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(32),
        existing_type=sa.String(255),
    )
