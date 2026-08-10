"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""add_pedidos_module

Cria a tabela `pedidos` — módulo standalone da Central de Pedidos,
desacoplado de INVENTÁRIO/VENCIMENTOS (feature_controle_pedidos.md v2.0).
`part_number`/`nomenclatura` são atributos de texto imutáveis, não FKs para
o catálogo de equipamentos.

Revision ID: a6ebf9f13490
Revises: dc6bbdf4335a
Create Date: 2026-08-10 09:32:48.604941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6ebf9f13490'
down_revision: Union[str, None] = 'dc6bbdf4335a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pedidos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("numero_pedido", sa.String(length=50), nullable=False),
        sa.Column("aeronave_id", sa.Uuid(), nullable=False),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("nomenclatura", sa.String(length=100), nullable=False),
        sa.Column("tipo_pedido", sa.String(length=20), nullable=False),
        sa.Column("numero_emergencia", sa.String(length=50), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("observacao", sa.String(length=1000), nullable=True),
        sa.Column("data_pedido", sa.Date(), nullable=False),
        sa.Column("data_atendimento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_cancelamento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_cancelamento", sa.String(length=500), nullable=True),
        sa.Column("solicitante_id", sa.Uuid(), nullable=False),
        sa.Column("atendido_por_id", sa.Uuid(), nullable=True),
        sa.Column("cancelado_por_id", sa.Uuid(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["aeronave_id"], ["aeronaves.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["solicitante_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["atendido_por_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelado_por_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero_pedido", name="uq_pedidos_numero_pedido"),
    )
    with op.batch_alter_table("pedidos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pedidos_numero_pedido"), ["numero_pedido"], unique=True)
        batch_op.create_index(batch_op.f("ix_pedidos_aeronave_id"), ["aeronave_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_pedidos_part_number"), ["part_number"], unique=False)
        batch_op.create_index(batch_op.f("ix_pedidos_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_pedidos_ativo"), ["ativo"], unique=False)


def downgrade() -> None:
    op.drop_table("pedidos")
