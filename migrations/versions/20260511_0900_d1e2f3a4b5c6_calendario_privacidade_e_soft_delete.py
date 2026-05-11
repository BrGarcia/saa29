"""Calendario auditoria 10.2 e 10.5 - private_color e soft-delete

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-05-11 09:00:00.000000

Correções:
  - 10.2: EventType.private_color (String 20, nullable) — cor neutra para eventos privados censurados
  - 10.5: CalendarEvent.deleted_at (DateTime tz, nullable, indexed)
          CalendarEvent.deleted_by_user_id (UUID FK usuarios.id, nullable, indexed)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 10.2 — EventType.private_color
    with op.batch_alter_table("event_types", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("private_color", sa.String(length=20), nullable=True)
        )

    # Preencher private_color com valor padrão para tipos já privados
    op.execute(
        "UPDATE event_types SET private_color = '#9CA3AF' WHERE visibility_type = 'private'"
    )

    # 10.5 — CalendarEvent soft-delete
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deleted_by_user_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_calendar_events_deleted_at"), ["deleted_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_calendar_events_deleted_by_user_id"), ["deleted_by_user_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_calendar_events_deleted_by_user_id_usuarios",
            "usuarios",
            ["deleted_by_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    # 10.5 — reverter soft-delete
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_calendar_events_deleted_by_user_id_usuarios", type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_calendar_events_deleted_by_user_id"))
        batch_op.drop_index(batch_op.f("ix_calendar_events_deleted_at"))
        batch_op.drop_column("deleted_by_user_id")
        batch_op.drop_column("deleted_at")

    # 10.2 — reverter private_color
    with op.batch_alter_table("event_types", schema=None) as batch_op:
        batch_op.drop_column("private_color")
