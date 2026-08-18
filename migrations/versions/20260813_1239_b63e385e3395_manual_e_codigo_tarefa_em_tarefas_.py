"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""manual e codigo_tarefa em tarefas_catalogo e inspecao_tarefas

Revision ID: b63e385e3395
Revises: e1a2b3c4d5f6
Create Date: 2026-08-13 12:39:53.324693

Nota: o autogenerate também detectou diffs sem relação com esta mudança
(remoção de `encarregado_ciencias` — falta o import do módulo em
`migrations/env.py`; troca de tipo em `publicacoes_upload_jobs` — falso
positivo do autogenerate comparando VARCHAR refletido do SQLite com
`sa.Enum(create_constraint=False)`; drop de `uq_pedidos_numero_pedido`).
Nenhum desses pertence a esta melhoria — foram removidos manualmente deste
arquivo para que a revisão contenha só as duas colunas novas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b63e385e3395'
down_revision: Union[str, None] = 'e1a2b3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tarefas_catalogo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('manual', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('codigo_tarefa', sa.String(length=60), nullable=True))

    with op.batch_alter_table('inspecao_tarefas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('manual', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('codigo_tarefa', sa.String(length=60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('inspecao_tarefas', schema=None) as batch_op:
        batch_op.drop_column('codigo_tarefa')
        batch_op.drop_column('manual')

    with op.batch_alter_table('tarefas_catalogo', schema=None) as batch_op:
        batch_op.drop_column('codigo_tarefa')
        batch_op.drop_column('manual')
