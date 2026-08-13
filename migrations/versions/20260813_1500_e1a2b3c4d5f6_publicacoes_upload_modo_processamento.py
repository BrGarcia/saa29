"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""publicacoes upload modo_processamento e status AGUARDANDO_PROCESSAMENTO

Revision ID: e1a2b3c4d5f6
Revises: 3dd0faeb4666
Create Date: 2026-08-13 15:00:00.000000

Nota: `status`/`modo_processamento` são armazenados como VARCHAR sem CHECK
constraint (sa.Enum(create_constraint=False), o padrão do projeto) — então
adicionar 'AGUARDANDO_PROCESSAMENTO' ao enum não exige alterar o tipo da
coluna no banco, só o índice parcial de single-flight que lista os status
ativos. O índice é recriado via SQL puro (fora de batch_alter_table) porque
o reflection do SQLite não recupera a cláusula WHERE de índices parciais,
o que faz o drop_index em modo batch falhar tentando comparar com o índice
refletido (sem o WHERE) e não encontrar correspondência.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5f6'
down_revision: Union[str, None] = '3dd0faeb4666'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDICE = 'uq_publicacoes_upload_jobs_ativo_unico'
_TABELA = 'publicacoes_upload_jobs'


def upgrade() -> None:
    with op.batch_alter_table(_TABELA, schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'modo_processamento',
            sa.String(length=20),
            nullable=False,
            server_default='AGENDADO',
            comment='IMEDIATO dispara o worker ao concluir o upload; AGENDADO espera o horário noturno configurado',
        ))

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(f'DROP INDEX IF EXISTS {_INDICE}')
        op.execute(
            f"CREATE UNIQUE INDEX {_INDICE} ON {_TABELA} ((1)) "
            "WHERE status IN ('ENVIANDO', 'AGUARDANDO_PROCESSAMENTO', 'PROCESSANDO')"
        )
    else:
        op.execute(f'DROP INDEX IF EXISTS {_INDICE}')
        op.execute(
            f"CREATE UNIQUE INDEX {_INDICE} ON {_TABELA} (1) "
            "WHERE status IN ('ENVIANDO', 'AGUARDANDO_PROCESSAMENTO', 'PROCESSANDO')"
        )


def downgrade() -> None:
    # A ordem importa: batch_alter_table recria a tabela inteira no SQLite
    # (o reflection não recupera índices parciais/de expressão — daí o aviso
    # "Skipped unsupported reflection of expression-based index" — e a
    # recriação NÃO os restaura sozinha). Por isso o drop_column roda
    # primeiro, e o índice é (re)criado por último, depois que a tabela já
    # está no formato final.
    with op.batch_alter_table(_TABELA, schema=None) as batch_op:
        batch_op.drop_column('modo_processamento')

    bind = op.get_bind()
    op.execute(f'DROP INDEX IF EXISTS {_INDICE}')
    if bind.dialect.name == 'postgresql':
        op.execute(
            f"CREATE UNIQUE INDEX {_INDICE} ON {_TABELA} ((1)) "
            "WHERE status IN ('ENVIANDO', 'PROCESSANDO')"
        )
    else:
        op.execute(
            f"CREATE UNIQUE INDEX {_INDICE} ON {_TABELA} (1) "
            "WHERE status IN ('ENVIANDO', 'PROCESSANDO')"
        )
