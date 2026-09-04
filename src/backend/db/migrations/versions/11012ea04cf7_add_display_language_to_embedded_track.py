"""add display_language to embedded_track

Revision ID: 11012ea04cf7
Revises: 26b381fb9308
Create Date: 2026-09-04 11:55:01.227589

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "11012ea04cf7"
down_revision: str | Sequence[str] | None = "26b381fb9308"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Added nullable first so the ADD COLUMN doesn't fail against existing rows on a NOT
    # NULL string column with no server default — backfilled from the existing (region-
    # collapsed) `language` column, the best available approximation until the next scan
    # re-probes and can tell a region-qualified container tag from a bare one, then made
    # NOT NULL. SQLite can't ALTER a column directly, hence batch mode for the last step.
    op.add_column("embeddedtrack", sa.Column("display_language", sa.String(), nullable=True))
    op.execute("UPDATE embeddedtrack SET display_language = language")
    with op.batch_alter_table("embeddedtrack") as batch_op:
        batch_op.alter_column("display_language", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("embeddedtrack", "display_language")
