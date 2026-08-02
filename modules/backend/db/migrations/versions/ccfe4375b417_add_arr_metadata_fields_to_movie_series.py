"""add arr metadata fields to movie/series

Revision ID: ccfe4375b417
Revises: 577dfb7a48c8
Create Date: 2026-08-02 11:48:16.143751

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ccfe4375b417"
down_revision: str | Sequence[str] | None = "577dfb7a48c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # boolean column — adjusted in from the missing default autogenerate doesn't add.
    op.add_column(
        "movie", sa.Column("monitored", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("movie", sa.Column("status", sa.String(), nullable=True))
    op.add_column("movie", sa.Column("quality_profile_id", sa.Integer(), nullable=True))
    op.add_column("movie", sa.Column("quality_profile_name", sa.String(), nullable=True))
    op.add_column(
        "series", sa.Column("monitored", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("series", sa.Column("status", sa.String(), nullable=True))
    op.add_column("series", sa.Column("quality_profile_id", sa.Integer(), nullable=True))
    op.add_column("series", sa.Column("quality_profile_name", sa.String(), nullable=True))
    op.add_column("series", sa.Column("episode_count", sa.Integer(), nullable=True))
    op.add_column("series", sa.Column("episode_file_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("series", "episode_file_count")
    op.drop_column("series", "episode_count")
    op.drop_column("series", "quality_profile_name")
    op.drop_column("series", "quality_profile_id")
    op.drop_column("series", "status")
    op.drop_column("series", "monitored")
    op.drop_column("movie", "quality_profile_name")
    op.drop_column("movie", "quality_profile_id")
    op.drop_column("movie", "status")
    op.drop_column("movie", "monitored")
