"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""publicacoes_m3_favoritos

Cria publicacoes_favoritos — favorito transversal aos dois acervos (manual e
avulsa), M3.

Achado B1 (07_revisao_pre_implementacao.md): o desenho original usava PK
composta com colunas nullable, inválido em SQL padrão. Corrigido para PK
surrogate + CheckConstraint XOR + duas UniqueConstraint — NULLs são distintos
em UNIQUE tanto no SQLite quanto no Postgres, então duplicatas reais são
bloqueadas e os dois lados do XOR não conflitam entre si.

`ondelete="CASCADE"` nos dois alvos é deliberado (diferente de
`publicacoes_acessos`, que usa SET NULL): favorito de documento/avulsa
removido DEVE sumir — não é auditoria, é atalho pessoal do usuário.

Revision ID: 7b3acb4928f0
Revises: 7daf099e56ed
Create Date: 2026-08-05 22:13:22.747338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b3acb4928f0'
down_revision: Union[str, None] = '7daf099e56ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'publicacoes_favoritos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('documento_id', sa.Uuid(), nullable=True),
        sa.Column('avulsa_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('(documento_id IS NULL) != (avulsa_id IS NULL)', name='ck_publicacoes_favoritos_alvo_unico'),
        sa.ForeignKeyConstraint(['avulsa_id'], ['publicacoes_avulsas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['documento_id'], ['manuais_documentos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('usuario_id', 'avulsa_id', name='uq_publicacoes_favoritos_usuario_avulsa'),
        sa.UniqueConstraint('usuario_id', 'documento_id', name='uq_publicacoes_favoritos_usuario_documento'),
    )
    with op.batch_alter_table('publicacoes_favoritos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_publicacoes_favoritos_usuario_id'), ['usuario_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('publicacoes_favoritos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_publicacoes_favoritos_usuario_id'))
    op.drop_table('publicacoes_favoritos')
