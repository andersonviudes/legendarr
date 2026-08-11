"""add forced/hearing_impaired to subtitle

Revision ID: facb42a665b3
Revises: ccfe4375b417
Create Date: 2026-08-10 23:52:36.173282

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "facb42a665b3"
down_revision: str | Sequence[str] | None = "ccfe4375b417"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # boolean column — adjust to fix the missing default autogenerate doesn't add.
    op.add_column(
        "subtitle",
        sa.Column("forced", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "subtitle",
        sa.Column("hearing_impaired", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("subtitle", "hearing_impaired")
    op.drop_column("subtitle", "forced")
