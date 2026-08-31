"""slot_not_null_e_unique

Migration 3b do módulo de inventário — DESTRUTIVA.

Aperta `slots_inventario`: `sistema`, `posicao_xlsx` e `created_at` passam a
NOT NULL, e a chave natural (nome_posicao, sistema) vira UNIQUE.

PORTÕES OBRIGATÓRIOS ANTES DE MESCLAR EM `main`
-----------------------------------------------
O pipeline migra produção sozinho: `deploy.yml` e `scripts/start.sh` rodam
`alembic upgrade head` sob `set -e`. Uma migration que falha não degrada — o
container não sobe. Por isso:

1. Pré-check no banco de PRODUÇÃO (não no local), imediatamente antes:
       SELECT nome_posicao, sistema, COUNT(*) FROM slots_inventario
       GROUP BY 1,2 HAVING COUNT(*) > 1;
       SELECT COUNT(*) FROM slots_inventario
       WHERE sistema IS NULL OR posicao_xlsx IS NULL;
   O backfill abaixo resolve NULO; NÃO resolve DUPLICATA — com duplicidade a
   UNIQUE falha mesmo assim. Sanear antes.

2. Snapshot manual do banco. O backup automático para o R2 é disparado por
   escrita (app/bootstrap/tasks.py) e sobrescreve o estado pré-migration em
   segundos; não serve como ponto de retorno.

Ver docs/BACKLOG/modulo_inventario/plano_implementacao.md §0.1.

NOTA — arquivo editado à mão após o --autogenerate, que também acusou
desalinhamentos PRÉ-EXISTENTES e alheios a este PR, removidos de propósito:
`publicacoes_upload_jobs.status` e `.modo_processamento` (VARCHAR -> Enum).
Precisam de migration própria, no módulo deles.

Revision ID: c40c48254161
Revises: 657c836f61af
Create Date: 2026-08-31 05:31:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c40c48254161'
down_revision: Union[str, None] = '657c836f61af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Backfill ANTES do ALTER. Promover a NOT NULL com linhas nulas falha o
    #    ALTER TABLE mesmo em modo batch.
    op.execute("UPDATE slots_inventario SET sistema = '' WHERE sistema IS NULL")
    op.execute("UPDATE slots_inventario SET posicao_xlsx = '' WHERE posicao_xlsx IS NULL")
    op.execute(
        "UPDATE slots_inventario SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
    )

    # 2. batch_alter_table é obrigatório em SQLite (env.py:53 já liga
    #    render_as_batch para URLs sqlite).
    with op.batch_alter_table('slots_inventario', schema=None) as batch_op:
        batch_op.alter_column(
            'sistema', existing_type=sa.VARCHAR(length=50), nullable=False
        )
        batch_op.alter_column(
            'posicao_xlsx', existing_type=sa.VARCHAR(length=20), nullable=False
        )
        batch_op.alter_column(
            'created_at', existing_type=sa.DATETIME(), nullable=False
        )
        batch_op.create_unique_constraint('uq_slot_nome_sistema', ['nome_posicao', 'sistema'])


def downgrade() -> None:
    # Caminho de retorno se a UNIQUE estourar em produção. Executar de fato
    # antes do merge — um downgrade só lido não é plano de rollback.
    with op.batch_alter_table('slots_inventario', schema=None) as batch_op:
        batch_op.drop_constraint('uq_slot_nome_sistema', type_='unique')
        batch_op.alter_column('created_at', existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column(
            'posicao_xlsx', existing_type=sa.VARCHAR(length=20), nullable=True
        )
        batch_op.alter_column('sistema', existing_type=sa.VARCHAR(length=50), nullable=True)
