"""add hash_matched and hearing_impaired_matched to acquisition attempt

Revision ID: 7544fd7bf786
Revises: 37624b260bfb
Create Date: 2026-08-29 15:18:20.403872

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7544fd7bf786"
down_revision: str | Sequence[str] | None = "37624b260bfb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # boolean column — adjust to fix the missing default autogenerate doesn't add.
    op.add_column(
        "acquisitionattempt",
        sa.Column("hash_matched", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "acquisitionattempt", sa.Column("hearing_impaired_matched", sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("acquisitionattempt", "hearing_impaired_matched")
    op.drop_column("acquisitionattempt", "hash_matched")
