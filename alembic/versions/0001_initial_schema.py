"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_organizer_email"),
    )
    op.create_index("ix_organizers_email", "organizers", ["email"])

    op.create_table(
        "magic_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizer_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organizer_id"], ["organizers.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("token", name="uq_magic_link_token"),
    )
    op.create_index("ix_magic_links_token", "magic_links", ["token"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "format",
            sa.Enum("ambrose_4ball", name="event_format"),
            nullable=False,
        ),
        sa.Column("organizer_id", sa.Integer(), nullable=True),
        sa.Column("join_code", sa.String(32), nullable=False),
        sa.Column("hole_count", sa.Integer(), nullable=False, server_default="18"),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "closed", name="event_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organizer_id"], ["organizers.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("join_code", name="uq_event_join_code"),
    )
    op.create_index("ix_events_join_code", "events", ["join_code"])

    op.create_table(
        "holes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("hole_number", sa.Integer(), nullable=False),
        sa.Column("par", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id", "hole_number", name="uq_hole_event_number"),
    )

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("group_handicap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qr_token", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("qr_token", name="uq_group_qr_token"),
    )
    op.create_index("ix_groups_qr_token", "groups", ["qr_token"])

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("handicap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_scorer", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("hole_id", sa.Integer(), nullable=False),
        sa.Column("gross_score", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hole_id"], ["holes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("group_id", "hole_id", name="uq_score_group_hole"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("sender_name", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("scores")
    op.drop_table("players")
    op.drop_index("ix_groups_qr_token", table_name="groups")
    op.drop_table("groups")
    op.drop_table("holes")
    op.drop_index("ix_events_join_code", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_magic_links_token", table_name="magic_links")
    op.drop_table("magic_links")
    op.drop_index("ix_organizers_email", table_name="organizers")
    op.drop_table("organizers")
    op.execute("DROP TYPE IF EXISTS event_format")
    op.execute("DROP TYPE IF EXISTS event_status")
