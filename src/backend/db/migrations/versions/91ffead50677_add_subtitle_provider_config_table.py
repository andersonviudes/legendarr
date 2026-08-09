"""add subtitle provider config table

Revision ID: 91ffead50677
Revises: 3605a01d1781
Create Date: 2026-07-22 12:24:14.762309

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from legendarr_backend.security.encrypted_string import EncryptedString

# revision identifiers, used by Alembic.
revision: str = "91ffead50677"
down_revision: str | Sequence[str] | None = "3605a01d1781"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "subtitleproviderconfig",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("api_key", EncryptedString(), nullable=True),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("password", EncryptedString(), nullable=True),
        sa.Column("connection_verified", sa.Boolean(), nullable=False),
        # OpenSubtitles-only search options — see SubtitleProviderConfig for defaults;
        # no server_default needed here since the table (and any rows in it) is new.
        sa.Column("use_hash", sa.Boolean(), nullable=False),
        sa.Column("include_ai_translated", sa.Boolean(), nullable=False),
        sa.Column("include_machine_translated", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subtitleproviderconfig_kind"), "subtitleproviderconfig", ["kind"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_subtitleproviderconfig_kind"), table_name="subtitleproviderconfig")
    op.drop_table("subtitleproviderconfig")
