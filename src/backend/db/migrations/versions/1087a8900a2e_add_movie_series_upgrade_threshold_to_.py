"""add movie/series upgrade threshold to language_profile

Revision ID: 1087a8900a2e
Revises: e72442d07845
Create Date: 2026-09-02 18:01:53.415366

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1087a8900a2e"
down_revision: str | Sequence[str] | None = "e72442d07845"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # integer column — adjust to fix the missing default autogenerate doesn't add.
    op.add_column(
        "languageprofile",
        sa.Column("movie_upgrade_threshold", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "languageprofile",
        sa.Column("series_upgrade_threshold", sa.Integer(), nullable=False, server_default="100"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("languageprofile", "series_upgrade_threshold")
    op.drop_column("languageprofile", "movie_upgrade_threshold")
