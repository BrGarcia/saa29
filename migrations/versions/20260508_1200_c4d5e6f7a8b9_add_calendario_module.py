"""Add calendario module

Revision ID: c4d5e6f7a8b9
Revises: 48d0005f8339
Create Date: 2026-05-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "48d0005f8339"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("visibility_type", sa.String(length=20), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("icon", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("visibility_type IN ('public', 'private')", name="ck_event_types_visibility_type"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("event_types", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_event_types_active"), ["active"], unique=False)
        batch_op.create_index(batch_op.f("ix_event_types_name"), ["name"], unique=True)
        batch_op.create_index(batch_op.f("ix_event_types_visibility_type"), ["visibility_type"], unique=False)

    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("end_date >= start_date", name="ck_calendar_events_period"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["event_type_id"], ["event_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_calendar_events_created_by_user_id"), ["created_by_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_calendar_events_end_date"), ["end_date"], unique=False)
        batch_op.create_index(batch_op.f("ix_calendar_events_event_type_id"), ["event_type_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_calendar_events_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_calendar_events_start_date"), ["start_date"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_calendar_events_start_date"))
        batch_op.drop_index(batch_op.f("ix_calendar_events_owner_user_id"))
        batch_op.drop_index(batch_op.f("ix_calendar_events_event_type_id"))
        batch_op.drop_index(batch_op.f("ix_calendar_events_end_date"))
        batch_op.drop_index(batch_op.f("ix_calendar_events_created_by_user_id"))
    op.drop_table("calendar_events")

    with op.batch_alter_table("event_types", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_event_types_visibility_type"))
        batch_op.drop_index(batch_op.f("ix_event_types_name"))
        batch_op.drop_index(batch_op.f("ix_event_types_active"))
    op.drop_table("event_types")

