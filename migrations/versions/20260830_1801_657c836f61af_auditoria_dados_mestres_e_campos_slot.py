"""auditoria_dados_mestres_e_campos_slot

Migration 3a do módulo de inventário — ADITIVA.

Só adiciona: tabela nova de auditoria e colunas novas em `slots_inventario`,
todas nullable ou com server_default. Não altera nulabilidade, não cria
UNIQUE, não toca em dado existente. Pode ser aplicada sem portão manual.

A parte destrutiva (`sistema`/`posicao_xlsx`/`created_at` → NOT NULL e a
UNIQUE `uq_slot_nome_sistema`) fica isolada na migration 3b, num PR próprio,
porque o pipeline migra produção sozinho: `deploy.yml` e `scripts/start.sh`
rodam `alembic upgrade head` sob `set -e`, e uma migration que falha impede
o container de subir. Ver docs/BACKLOG/modulo_inventario/plano_implementacao.md §0.1.

NOTA — este arquivo foi editado à mão após o --autogenerate. O comando
detectou também desalinhamentos PRÉ-EXISTENTES entre models e banco, alheios
a este PR, que foram removidos de propósito:
  - `manuais.origem` (server_default)
  - `pedidos` (unique constraint uq_pedidos_numero_pedido)
  - `publicacoes_upload_jobs.status` e `.modo_processamento` (VARCHAR -> Enum)
Cada um precisa de análise própria; carregá-los aqui misturaria mudanças de
outros módulos numa migration de inventário.

Revision ID: 657c836f61af
Revises: 2676d7fdd987
Create Date: 2026-08-30 18:01:34.949381
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '657c836f61af'
down_revision: Union[str, None] = '2676d7fdd987'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Trilha de auditoria de dados mestres (append-only).
    op.create_table(
        'auditoria_dados_mestres',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('entidade', sa.String(length=30), nullable=False),
        sa.Column('entidade_id', sa.Uuid(), nullable=False),
        sa.Column('acao', sa.String(length=10), nullable=False),
        sa.Column('valores_anteriores', sa.JSON(), nullable=True),
        sa.Column('valores_novos', sa.JSON(), nullable=True),
        sa.Column('justificativa', sa.String(length=500), nullable=True),
        sa.Column('usuario_id', sa.Uuid(), nullable=True),
        sa.Column('ip_origem', sa.String(length=45), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('auditoria_dados_mestres', schema=None) as batch_op:
        batch_op.create_index('ix_auditoria_criado_em', ['criado_em'], unique=False)
        batch_op.create_index('ix_auditoria_entidade', ['entidade', 'entidade_id'], unique=False)

    # 2. Campos novos de slot. `ativo` nasce com server_default='1' para que as
    #    linhas já existentes não fiquem NULL após o ALTER.
    with op.batch_alter_table('slots_inventario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('descricao', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('ordem_exibicao', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # 3. Backfill de created_at nas linhas existentes. A promoção a NOT NULL
    #    fica para a 3b — aqui a coluna permanece nullable, espelhando o model.
    op.execute("UPDATE slots_inventario SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")


def downgrade() -> None:
    with op.batch_alter_table('slots_inventario', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('ativo')
        batch_op.drop_column('ordem_exibicao')
        batch_op.drop_column('descricao')

    with op.batch_alter_table('auditoria_dados_mestres', schema=None) as batch_op:
        batch_op.drop_index('ix_auditoria_entidade')
        batch_op.drop_index('ix_auditoria_criado_em')

    op.drop_table('auditoria_dados_mestres')
