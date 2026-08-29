"""add movie_match_score and series_match_score to language_profile

Revision ID: 37624b260bfb
Revises: a0c2455e1618
Create Date: 2026-08-29 14:13:06.507760

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37624b260bfb"
down_revision: str | Sequence[str] | None = "a0c2455e1618"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # integer column — adjust to fix the missing default autogenerate doesn't add.
    op.add_column(
        "languageprofile",
        sa.Column("movie_match_score", sa.Integer(), nullable=False, server_default="40"),
    )
    op.add_column(
        "languageprofile",
        sa.Column("series_match_score", sa.Integer(), nullable=False, server_default="40"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("languageprofile", "series_match_score")
    op.drop_column("languageprofile", "movie_match_score")
