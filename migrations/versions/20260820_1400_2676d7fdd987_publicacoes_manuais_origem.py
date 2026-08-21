"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""publicacoes: origem (Manutencao/Operacional) em manuais

Introduz `manuais.origem`, distinguindo os dois discos do acervo
(docs/backlog/modulo_publicacoes/11_achados_disco_completo.md §1: `Program/`
= manutenção, `Program_Operational/` = operacional). Os dois podem trazer o
mesmo `codigo` de manual com PDFs e revisão diferentes — esta rodada não
mescla, mantém os dois lado a lado (ver
docs/backlog/modulo_publicacoes/12_refinamento_gestao_e_envio.md §6, adiado).

A identidade do manual passa de `(edicao_id, codigo)` para
`(edicao_id, origem, codigo)`. Backfill via `server_default='MANUTENCAO'`:
todas as edições existentes (`2026`, `piloto-fim`) vieram de fonte única,
equivalente ao disco de manutenção — não há ambiguidade a resolver.

Revision ID: 2676d7fdd987
Revises: b63e385e3395
Create Date: 2026-08-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2676d7fdd987'
down_revision: Union[str, None] = 'b63e385e3395'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABELA = 'manuais'
_CONSTRAINT_ANTIGA = 'uq_manuais_edicao_codigo'
_CONSTRAINT_NOVA = 'uq_manuais_edicao_origem_codigo'


def upgrade() -> None:
    with op.batch_alter_table(_TABELA, schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'origem',
            sa.Enum('MANUTENCAO', 'OPERACIONAL', name='origemmanual', native_enum=False, length=20),
            nullable=False,
            server_default='MANUTENCAO',
            comment='Qual disco trouxe este manual — MANUTENCAO (Program/) ou OPERACIONAL (Program_Operational/)',
        ))
        batch_op.create_index(batch_op.f('ix_manuais_origem'), ['origem'], unique=False)
        batch_op.drop_constraint(_CONSTRAINT_ANTIGA, type_='unique')
        batch_op.create_unique_constraint(_CONSTRAINT_NOVA, ['edicao_id', 'origem', 'codigo'])


def downgrade() -> None:
    with op.batch_alter_table(_TABELA, schema=None) as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NOVA, type_='unique')
        batch_op.create_unique_constraint(_CONSTRAINT_ANTIGA, ['edicao_id', 'codigo'])
        batch_op.drop_index(batch_op.f('ix_manuais_origem'))
        batch_op.drop_column('origem')
