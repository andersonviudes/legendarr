"""add auto_translate to language_profile

Revision ID: e72442d07845
Revises: 175cd2a539ac
Create Date: 2026-09-02 13:01:36.728522

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e72442d07845"
down_revision: str | Sequence[str] | None = "175cd2a539ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so the ADD COLUMN doesn't fail against existing rows on a NOT NULL
    # boolean column — adjust to fix the missing default autogenerate doesn't add.
    op.add_column(
        "languageprofile",
        sa.Column("auto_translate", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("languageprofile", "auto_translate")
