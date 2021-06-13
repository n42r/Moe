"""Initial generation.

Revision ID: 32f71e3629db
Revises:
Create Date: 2021-06-13 15:11:54.573755

"""
import sqlalchemy as sa

import moe
from alembic import op

# revision identifiers, used by Alembic.
revision = "32f71e3629db"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "albums",
        sa.Column("artist", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("path", moe.core.library.album._PathType(), nullable=False),
        sa.PrimaryKeyConstraint("artist", "title", "year"),
        sa.UniqueConstraint("path"),
    )
    op.create_table(
        "genres",
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "extras",
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("_albumartist", sa.String(), nullable=False),
        sa.Column("_album", sa.String(), nullable=False),
        sa.Column("_year", sa.Integer(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["_albumartist", "_album", "_year"],
            ["albums.artist", "albums.title", "albums.year"],
        ),
        sa.PrimaryKeyConstraint("filename", "_albumartist", "_album", "_year"),
    )
    op.create_table(
        "tracks",
        sa.Column("track_num", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("_albumartist", sa.String(), nullable=False),
        sa.Column("_album", sa.String(), nullable=False),
        sa.Column("_year", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("artist", sa.String(), nullable=False),
        sa.Column("file_ext", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["_albumartist", "_album", "_year"],
            ["albums.artist", "albums.title", "albums.year"],
        ),
        sa.PrimaryKeyConstraint("track_num", "_albumartist", "_album", "_year"),
    )
    op.create_table(
        "track_genres",
        sa.Column("genre", sa.String(), nullable=True),
        sa.Column("track_num", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("album", sa.String(), nullable=False),
        sa.Column("albumartist", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["genre"],
            ["genres.name"],
        ),
        sa.ForeignKeyConstraint(
            ["track_num", "album", "albumartist", "year"],
            [
                "tracks.track_num",
                "tracks._album",
                "tracks._albumartist",
                "tracks._year",
            ],
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("track_genres")
    op.drop_table("tracks")
    op.drop_table("extras")
    op.drop_table("genres")
    op.drop_table("albums")
    # ### end Alembic commands ###