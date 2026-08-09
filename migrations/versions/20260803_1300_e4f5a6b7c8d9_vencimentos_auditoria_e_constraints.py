"""vencimentos_auditoria_e_constraints

Achados adicionais de docs/backlog/revisor/achados_vencimentos.md (fora do
escopo das 7 perguntas originais, adicionados pelo desenvolvedor na resposta
ao review):

- `equipamento_controles`: adiciona `created_at`/`updated_at`/`alterado_por_id`
  (trilha de auditoria — "quem mudou a periodicidade de 12 para 24 meses e
  quando" é pergunta típica de fiscalização) e `CheckConstraint` garantindo
  `periodicidade_meses > 0` (hoje só validado no schema Pydantic, sem rede de
  segurança no banco para escritas fora da API).
- Nova tabela `execucoes_vencimento_historico`: registro append-only de cada
  execução de um `ControleVencimento`. Sem isso, `registrar_execucao`
  sobrescrevia `data_ultima_exec`/`executado_por_id` sem deixar rastro de
  execuções anteriores — lacuna de auditoria para manutenção de aeronave,
  onde o registro histórico precisa ser reconstituível.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-08-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('equipamento_controles', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'created_at', sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('alterado_por_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            'fk_equipamento_controles_alterado_por_id_usuarios',
            'usuarios', ['alterado_por_id'], ['id'],
        )
        batch_op.create_check_constraint(
            'ck_equipamento_controle_periodicidade_positiva', 'periodicidade_meses > 0'
        )

    op.create_table(
        'execucoes_vencimento_historico',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('controle_id', sa.Uuid(), nullable=False),
        sa.Column('data_execucao', sa.Date(), nullable=False),
        sa.Column('data_vencimento_calculada', sa.Date(), nullable=False),
        sa.Column('periodicidade_meses', sa.Integer(), nullable=False),
        sa.Column('executado_por_id', sa.Uuid(), nullable=True),
        sa.Column('observacao', sa.String(length=500), nullable=True),
        sa.Column('registrado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['controle_id'], ['controle_vencimentos.id']),
        sa.ForeignKeyConstraint(['executado_por_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_execucoes_vencimento_historico_controle_id'),
        'execucoes_vencimento_historico', ['controle_id'],
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_execucoes_vencimento_historico_controle_id'),
        table_name='execucoes_vencimento_historico',
    )
    op.drop_table('execucoes_vencimento_historico')

    with op.batch_alter_table('equipamento_controles', schema=None) as batch_op:
        batch_op.drop_constraint('ck_equipamento_controle_periodicidade_positiva', type_='check')
        batch_op.drop_constraint('fk_equipamento_controles_alterado_por_id_usuarios', type_='foreignkey')
        batch_op.drop_column('alterado_por_id')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
