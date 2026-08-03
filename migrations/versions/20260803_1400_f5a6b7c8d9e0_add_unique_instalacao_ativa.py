"""add_unique_instalacao_ativa

Adiciona índice único parcial em instalacoes(slot_id, aeronave_id) WHERE
data_remocao IS NULL.

Motivo (RISCO-05, docs/backlog/revisor/achados_equipamentos.md): a invariante
"no máximo uma Instalacao ativa por slot" era garantida apenas por lógica de
aplicação (leitura + decisão, sem SAVEPOINT) — duas chamadas concorrentes de
`ajustar_inventario`/`instalar_item` no mesmo slot/aeronave podiam ambas ler
"nenhuma instalação ativa" e inserir duas instalações `data_remocao IS NULL`
para o mesmo slot na mesma aeronave.

Nota de correção sobre o achado original: o texto do achado propõe a
constraint só em `slot_id`, mas um slot é uma posição compartilhada por toda
a frota — cada aeronave tem sua própria instalação ativa no mesmo slot_id.
A invariante real, confirmada em `_obter_instalacao_ativa_no_slot`
(app/modules/equipamentos/service.py), é por par (slot_id, aeronave_id).

Verificado antes de escrever esta migration: 0 violações em `var/db`
agrupando por (slot_id, aeronave_id) — agrupar só por slot_id (como o texto
do achado sugeria) reportava dezenas de "duplicatas" que eram, na verdade,
aeronaves diferentes com instalação ativa no mesmo slot — o comportamento
normal e esperado da frota.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-08-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_instalacao_ativa_por_slot_aeronave',
        'instalacoes',
        ['slot_id', 'aeronave_id'],
        unique=True,
        sqlite_where=sa.text('data_remocao IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_instalacao_ativa_por_slot_aeronave', table_name='instalacoes')
