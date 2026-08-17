"""add content_hash and translated_from_hash to subtitle

Revision ID: 29af7d3d2106
Revises: 4d483fda231a
Create Date: 2026-08-17 17:25:27.067170

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "29af7d3d2106"
down_revision: str | Sequence[str] | None = "4d483fda231a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # column — the next scan recomputes a real hash for every existing row anyway.
    op.add_column(
        "subtitle",
        sa.Column("content_hash", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "subtitle",
        sa.Column("translated_from_hash", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("subtitle", "translated_from_hash")
    op.drop_column("subtitle", "content_hash")
