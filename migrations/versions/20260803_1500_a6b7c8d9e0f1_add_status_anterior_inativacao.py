"""add_status_anterior_inativacao

Adiciona aeronaves.status_anterior_inativacao (nullable).

Motivo (RISCO-05, docs/backlog/revisor/achados_aeronaves.md): o toggle de
status sempre reativava uma aeronave desativada para DISPONIVEL, mesmo que
ela estivesse ESTOCADA (ou outro status) antes da inativação — perdendo essa
informação permanentemente. A nova coluna guarda o status imediatamente
anterior à inativação, restaurado ao reativar.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-08-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6b7c8d9e0f1'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('aeronaves', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'status_anterior_inativacao',
            sa.String(length=20),
            nullable=True,
        ))


def downgrade() -> None:
    with op.batch_alter_table('aeronaves', schema=None) as batch_op:
        batch_op.drop_column('status_anterior_inativacao')
