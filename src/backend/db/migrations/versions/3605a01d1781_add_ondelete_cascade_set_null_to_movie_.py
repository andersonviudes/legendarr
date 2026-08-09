"""add ondelete cascade/set null to movie/series fks

Revision ID: 3605a01d1781
Revises: 6de10a94ec84
Create Date: 2026-07-20 18:12:05.506581

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3605a01d1781"
down_revision: str | Sequence[str] | None = "6de10a94ec84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The arr_service_id FKs were created unnamed back in 39f01288c6ac — SQLite allows that,
# but batch mode needs a name to target them for dropping, so give reflection a convention
# to derive one. language_profile_id's FK already has an explicit name from 35527f37e677.
_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite can't ALTER a constraint's ON DELETE clause directly — batch mode
    # (copy-and-move) is required, same as when these FKs were first added.
    with op.batch_alter_table("movie", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("fk_movie_arr_service_id_arrservice", type_="foreignkey")
        batch_op.drop_constraint("fk_movie_language_profile_id_languageprofile", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_movie_arr_service_id_arrservice",
            "arrservice",
            ["arr_service_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_movie_language_profile_id_languageprofile",
            "languageprofile",
            ["language_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("series", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("fk_series_arr_service_id_arrservice", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_series_language_profile_id_languageprofile", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_series_arr_service_id_arrservice",
            "arrservice",
            ["arr_service_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_series_language_profile_id_languageprofile",
            "languageprofile",
            ["language_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("series", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(
            "fk_series_language_profile_id_languageprofile", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_series_arr_service_id_arrservice", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_series_language_profile_id_languageprofile",
            "languageprofile",
            ["language_profile_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_series_arr_service_id_arrservice",
            "arrservice",
            ["arr_service_id"],
            ["id"],
        )
    with op.batch_alter_table("movie", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("fk_movie_language_profile_id_languageprofile", type_="foreignkey")
        batch_op.drop_constraint("fk_movie_arr_service_id_arrservice", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_movie_language_profile_id_languageprofile",
            "languageprofile",
            ["language_profile_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_movie_arr_service_id_arrservice",
            "arrservice",
            ["arr_service_id"],
            ["id"],
        )
