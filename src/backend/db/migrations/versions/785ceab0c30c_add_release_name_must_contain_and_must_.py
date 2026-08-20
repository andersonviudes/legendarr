"""add release name must-contain and must-not-contain filters to language_profile

Revision ID: 785ceab0c30c
Revises: 29af7d3d2106
Create Date: 2026-08-19 21:59:37.136986

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "785ceab0c30c"
down_revision: str | Sequence[str] | None = "29af7d3d2106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # column — an empty string means no must-contain/must-not-contain filter, same as
    # the model's own default.
    op.add_column(
        "languageprofile",
        sa.Column("release_name_must_contain", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "languageprofile",
        sa.Column("release_name_must_not_contain", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("languageprofile", "release_name_must_not_contain")
    op.drop_column("languageprofile", "release_name_must_contain")
