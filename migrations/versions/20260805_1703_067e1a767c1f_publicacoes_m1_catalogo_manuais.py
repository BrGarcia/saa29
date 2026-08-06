"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""publicacoes_m1_catalogo_manuais

Cria o catálogo LEVE do acervo de manuais (M1 do módulo `publicacoes`):
manuais_edicoes, manuais, manuais_documentos, manuais_fim_map e a auditoria
publicacoes_acessos.

O índice de busca (`catalog.db`: pages/pages_fts/documents) NÃO está aqui de
propósito — é SQLite dedicado, gerado offline por
`python -m scripts.publicacoes.indexar` e descartável (ADR-004).

Três decisões que parecem omissão e não são
(docs/backlog/modulo_publicacoes/07_revisao_pre_implementacao.md):

- `manuais_documentos.ata_codigo` é String(4) indexado **sem FK** (B3): o
  acervo cobre 28 capítulos ATA e `sistemas_ata` seeda 8 — com PRAGMA
  foreign_keys=ON, a FK reprovaria a indexação de 20 dos 28.
- `manuais_documentos.id` não tem default: é UUID v5 determinístico de
  (edição, manual, file_key), calculado pelo indexador (B2).
- `publicacoes_acessos.documento_id` é SET NULL, não CASCADE (B4): o indexador
  remove documentos que sumiram do acervo, e a auditoria precisa sobreviver a
  isso — daí também o snapshot de `documento_titulo`.

A linha sintética de `manuais_edicoes` (`rotulo='piloto-fim'`) não é inserida
aqui: quem cria a edição é o indexador (get-or-create), porque o rótulo é
parâmetro dele.

Revision ID: 067e1a767c1f
Revises: a6b7c8d9e0f1
Create Date: 2026-08-05 17:03:03.476913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '067e1a767c1f'
down_revision: Union[str, None] = 'a6b7c8d9e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'manuais_edicoes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('rotulo', sa.String(length=20), nullable=False, comment="Rótulo da edição (ex: '2027', 'piloto-fim') — entra no UUID v5 dos documentos"),
        sa.Column('data_publicacao', sa.DateTime(timezone=True), nullable=False, comment='Quando a edição foi publicada no SAA29'),
        sa.Column('snapshot_key', sa.String(length=255), nullable=True, comment='Chave do snapshot ZIP no R2 (M4)'),
        sa.Column('hash_sha256', sa.String(length=64), nullable=True, comment='Hash do snapshot inteiro (M4)'),
        sa.Column('status', sa.Enum('AGUARDANDO_ATIVACAO', 'VIGENTE', 'ANTERIOR', 'ARQUIVADA', name='statusedicao', native_enum=False, length=20), nullable=False),
        sa.Column('publicado_por_id', sa.Uuid(), nullable=True, comment='NULL quando a edição foi criada por script offline, sem usuário logado'),
        sa.Column('relatorio_diff', sa.Text(), nullable=True, comment='Markdown do relatório de diff da publicação (M4)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['publicado_por_id'], ['usuarios.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rotulo'),
    )
    with op.batch_alter_table('manuais_edicoes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_manuais_edicoes_publicado_por_id'), ['publicado_por_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_manuais_edicoes_status'), ['status'], unique=False)

    op.create_table(
        'manuais',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('edicao_id', sa.Uuid(), nullable=False),
        sa.Column('codigo', sa.String(length=40), nullable=False, comment="Nome do diretório do manual (ex: 'FIM_1741', 'AMM_PART1_1651')"),
        sa.Column('descricao_pt', sa.String(length=200), nullable=False, comment='Descrição legível — de categorias_manuais.toml, com fallback para o código'),
        sa.Column('categoria', sa.String(length=60), nullable=False, comment="De categorias_manuais.toml (RN-04); manual desconhecido cai em 'Outros' (E-04)"),
        sa.Column('path', sa.String(length=255), nullable=False, comment='Caminho relativo ao PUBLICACOES_ACERVO_DIR'),
        sa.Column('revisao', sa.String(length=10), nullable=True),
        sa.Column('revisao_data', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['edicao_id'], ['manuais_edicoes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('edicao_id', 'codigo', name='uq_manuais_edicao_codigo'),
    )
    with op.batch_alter_table('manuais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_manuais_categoria'), ['categoria'], unique=False)
        batch_op.create_index(batch_op.f('ix_manuais_edicao_id'), ['edicao_id'], unique=False)

    op.create_table(
        'manuais_documentos',
        sa.Column('id', sa.Uuid(), nullable=False, comment='UUID v5 determinístico de (edição, manual, file_key) — sem default aleatório'),
        sa.Column('manual_id', sa.Uuid(), nullable=False),
        sa.Column('capitulo', sa.String(length=80), nullable=False, comment='Último segmento de `chapter` (Lucene) ou do diretório físico'),
        sa.Column('ata_codigo', sa.String(length=4), nullable=True),
        sa.Column('file_key', sa.String(length=500), nullable=False, comment='Caminho relativo ao diretório de entrada'),
        sa.Column('titulo', sa.String(length=300), nullable=False, comment='RN-02: título do Lucene quando houver, senão nome de arquivo tratado'),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='Prefixo numérico do nome do arquivo (RN-05); sem prefixo vai para o fim'),
        sa.Column('paginas', sa.Integer(), nullable=True),
        sa.Column('has_text', sa.Boolean(), nullable=False, comment='False quando o PDF não tem camada de texto (E-01) — some da busca, não da navegação'),
        sa.Column('revision_status', sa.Enum('UNCHANGED', 'REVISED', 'NOVO', 'DESCONHECIDO', name='revisionstatus', native_enum=False, length=20), nullable=False),
        sa.Column('hash_sha256', sa.String(length=64), nullable=True, comment='Dedup entre edições retidas (M4)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['manual_id'], ['manuais.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('manual_id', 'file_key', name='uq_manuais_documentos_manual_file'),
    )
    with op.batch_alter_table('manuais_documentos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_manuais_documentos_ata_codigo'), ['ata_codigo'], unique=False)
        batch_op.create_index(batch_op.f('ix_manuais_documentos_manual_id'), ['manual_id'], unique=False)

    op.create_table(
        'manuais_fim_map',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('mensagem', sa.String(length=20), nullable=False, comment="Ex: 'ADC 001'"),
        sa.Column('procedimento', sa.String(length=30), nullable=False, comment="Ex: '34-15-00-810-801-A'"),
        sa.Column('documento_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['documento_id'], ['manuais_documentos.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mensagem', name='uq_manuais_fim_map_mensagem'),
    )
    with op.batch_alter_table('manuais_fim_map', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_manuais_fim_map_procedimento'), ['procedimento'], unique=False)

    op.create_table(
        'publicacoes_acessos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('documento_id', sa.Uuid(), nullable=True),
        sa.Column('documento_titulo', sa.String(length=300), nullable=False, comment='Snapshot do título no acesso — legível mesmo após remoção do documento'),
        sa.Column('edicao_id', sa.Uuid(), nullable=False),
        sa.Column('pagina', sa.Integer(), nullable=True),
        sa.Column('quando', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['documento_id'], ['manuais_documentos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['edicao_id'], ['manuais_edicoes.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('publicacoes_acessos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_publicacoes_acessos_documento_id'), ['documento_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_publicacoes_acessos_quando'), ['quando'], unique=False)
        batch_op.create_index(batch_op.f('ix_publicacoes_acessos_usuario_id'), ['usuario_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('publicacoes_acessos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_publicacoes_acessos_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_publicacoes_acessos_quando'))
        batch_op.drop_index(batch_op.f('ix_publicacoes_acessos_documento_id'))
    op.drop_table('publicacoes_acessos')

    with op.batch_alter_table('manuais_fim_map', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_manuais_fim_map_procedimento'))
    op.drop_table('manuais_fim_map')

    with op.batch_alter_table('manuais_documentos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_manuais_documentos_manual_id'))
        batch_op.drop_index(batch_op.f('ix_manuais_documentos_ata_codigo'))
    op.drop_table('manuais_documentos')

    with op.batch_alter_table('manuais', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_manuais_edicao_id'))
        batch_op.drop_index(batch_op.f('ix_manuais_categoria'))
    op.drop_table('manuais')

    with op.batch_alter_table('manuais_edicoes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_manuais_edicoes_status'))
        batch_op.drop_index(batch_op.f('ix_manuais_edicoes_publicado_por_id'))
    op.drop_table('manuais_edicoes')
