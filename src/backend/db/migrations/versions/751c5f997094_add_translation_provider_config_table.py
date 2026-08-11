"""add translation provider config table

Revision ID: 751c5f997094
Revises: 6cb9853f56b6
Create Date: 2026-07-23 23:41:49.091482

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from legendarr_backend.security.encrypted_string import EncryptedString

# revision identifiers, used by Alembic.
revision: str = "751c5f997094"
down_revision: str | Sequence[str] | None = "6cb9853f56b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "translationproviderconfig",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("api_key", EncryptedString(), nullable=True),
        sa.Column("endpoint", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("connection_verified", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_translationproviderconfig_kind"),
        "translationproviderconfig",
        ["kind"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_translationproviderconfig_kind"), table_name="translationproviderconfig")
    op.drop_table("translationproviderconfig")
