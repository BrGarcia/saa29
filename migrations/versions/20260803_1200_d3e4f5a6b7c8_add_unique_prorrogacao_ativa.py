"""add_unique_prorrogacao_ativa

Adiciona índice único parcial em prorrogacoes_vencimento(controle_id) WHERE
ativo = 1.

Motivo (RISCO-03, docs/backlog/revisor/achados_vencimentos.md): a invariante
"no máximo uma prorrogação ativa por controle" era garantida apenas por
lógica de aplicação (UPDATE + INSERT sem SAVEPOINT) — duas chamadas
concorrentes de `prorrogar_vencimento` podiam ambas ler "nenhuma ativa" e
inserir duas prorrogações `ativo=True` para o mesmo controle. O índice
único parcial torna essa corrida impossível no banco; o service passa a
tratar o `IntegrityError` como rede de segurança, no mesmo padrão já usado
para `uq_equip_controle` e `uq_pane_responsavel_pane_usuario`.

Verificado antes de escrever esta migration: 0 controles com mais de uma
prorrogação ativa simultânea na base local (`var/db`).

Revision ID: d3e4f5a6b7c8
Revises: c9d8e7f6a5b4
Create Date: 2026-08-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_prorrogacao_ativa_por_controle',
        'prorrogacoes_vencimento',
        ['controle_id'],
        unique=True,
        sqlite_where=sa.text('ativo = 1'),
    )


def downgrade() -> None:
    op.drop_index('uq_prorrogacao_ativa_por_controle', table_name='prorrogacoes_vencimento')
