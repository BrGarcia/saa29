"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""publicacoes_m2_avulsas

Cria o acervo B do módulo `publicacoes` — BO/BS/NPO/BT: publicacoes_avulsas,
publicacao_avulsa_anexos (upload fora do pipeline de imagem, `file_key` do
StorageService) e publicacao_avulsa_aeronaves (N:N; ausência de linha para
uma avulsa = aplicável à frota inteira, §9.2 do parecer).

Independente do M1: não referencia manuais_*, catalog.db nem pypdfium2.

Revision ID: 7daf099e56ed
Revises: 067e1a767c1f
Create Date: 2026-08-05 21:41:30.976112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7daf099e56ed'
down_revision: Union[str, None] = '067e1a767c1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'publicacoes_avulsas',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tipo', sa.Enum('BO', 'BS', 'NPO', 'BT', 'OUTRO', name='tipopublicacao', native_enum=False, length=10), nullable=False),
        sa.Column('numero', sa.String(length=60), nullable=False, comment="Ex: 'BS 314-24-0021'"),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('data_emissao', sa.Date(), nullable=False),
        sa.Column('data_recebimento', sa.Date(), nullable=False, comment='Data que conta para o esquadrão (§9.2 do parecer)'),
        sa.Column('emissor', sa.String(length=100), nullable=False),
        sa.Column('titulo', sa.String(length=300), nullable=False),
        sa.Column('ementa', sa.Text(), nullable=False, comment='Campo mais valioso — principal insumo de busca'),
        sa.Column('sistema_ata_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.Enum('VIGENTE', 'CANCELADO', 'SUBSTITUIDO', name='statuspublicacaoavulsa', native_enum=False, length=15), nullable=False),
        sa.Column('substituida_por_id', sa.Uuid(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, comment='Soft delete'),
        sa.Column('cadastrada_por_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['cadastrada_por_id'], ['usuarios.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['sistema_ata_id'], ['sistemas_ata.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['substituida_por_id'], ['publicacoes_avulsas.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo', 'numero', 'ano', name='uq_publicacoes_avulsas_tipo_numero_ano'),
    )
    with op.batch_alter_table('publicacoes_avulsas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_publicacoes_avulsas_ano'), ['ano'], unique=False)
        batch_op.create_index(batch_op.f('ix_publicacoes_avulsas_ativo'), ['ativo'], unique=False)
        batch_op.create_index(batch_op.f('ix_publicacoes_avulsas_sistema_ata_id'), ['sistema_ata_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_publicacoes_avulsas_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_publicacoes_avulsas_tipo'), ['tipo'], unique=False)

    op.create_table(
        'publicacao_avulsa_aeronaves',
        sa.Column('avulsa_id', sa.Uuid(), nullable=False),
        sa.Column('aeronave_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['aeronave_id'], ['aeronaves.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['avulsa_id'], ['publicacoes_avulsas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('avulsa_id', 'aeronave_id'),
    )

    op.create_table(
        'publicacao_avulsa_anexos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('avulsa_id', sa.Uuid(), nullable=False),
        sa.Column('file_key', sa.String(length=500), nullable=False, comment='Retorno de StorageService.upload()'),
        sa.Column('nome_original', sa.String(length=255), nullable=False),
        sa.Column('tamanho_bytes', sa.Integer(), nullable=False),
        sa.Column('principal', sa.Boolean(), nullable=False, comment='Qual anexo abre por padrão quando há mais de um'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['avulsa_id'], ['publicacoes_avulsas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('publicacao_avulsa_anexos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_publicacao_avulsa_anexos_avulsa_id'), ['avulsa_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('publicacao_avulsa_anexos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_publicacao_avulsa_anexos_avulsa_id'))
    op.drop_table('publicacao_avulsa_anexos')

    op.drop_table('publicacao_avulsa_aeronaves')

    with op.batch_alter_table('publicacoes_avulsas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_publicacoes_avulsas_tipo'))
        batch_op.drop_index(batch_op.f('ix_publicacoes_avulsas_status'))
        batch_op.drop_index(batch_op.f('ix_publicacoes_avulsas_sistema_ata_id'))
        batch_op.drop_index(batch_op.f('ix_publicacoes_avulsas_ativo'))
        batch_op.drop_index(batch_op.f('ix_publicacoes_avulsas_ano'))
    op.drop_table('publicacoes_avulsas')
