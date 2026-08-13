"""add_encarregado_ciencias

Cria a tabela `encarregado_ciencias` — única tabela de escrita do módulo
Encarregado (feature_encarregado_ciencia.md v2.0). Sem FK para as tabelas
de origem (panes/inspecao_tarefas/instalacoes/controle_vencimentos): o
módulo é exclusivamente de leitura sobre elas, e `registro_id` guarda o
UUID de origem como texto por design.

Revision ID: 3dd0faeb4666
Revises: a6ebf9f13490
Create Date: 2026-08-12 20:26:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3dd0faeb4666'
down_revision: Union[str, None] = 'a6ebf9f13490'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "encarregado_ciencias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("categoria", sa.String(length=20), nullable=False),
        sa.Column("evento", sa.String(length=20), nullable=False),
        sa.Column("registro_id", sa.String(length=36), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("dado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "categoria", "evento", "registro_id",
            name="uq_encarregado_ciencia_evento_unico",
        ),
    )
    with op.batch_alter_table("encarregado_ciencias", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_encarregado_ciencias_categoria"), ["categoria"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_encarregado_ciencias_registro_id"), ["registro_id"], unique=False
        )


def downgrade() -> None:
    op.drop_table("encarregado_ciencias")
