"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""publicacoes_m4_unica_edicao_vigente

Índice único PARCIAL garantindo no máximo uma edição em `status='VIGENTE'`.

Por que só agora: até a Fase 1 nada ativava edição pela aplicação — o status
era escrito por script offline e `obter_edicao_vigente` disfarçava qualquer
duplicidade pegando a mais recente (`ORDER BY data_publicacao DESC LIMIT 1`).
Com `service.ativar_edicao` exposto por endpoint, duas ativações concorrentes
em workers diferentes poderiam deixar duas linhas VIGENTE, e a busca passaria a
depender de qual delas tem a data maior — falha silenciosa, não erro.

A regra também é imposta em `service.ativar_edicao`, dentro da transação, que é
onde ela produz mensagem legível. Este índice é a rede de segurança para o caso
que a validação em Python não cobre: dois processos, cada um na sua transação.

Índice parcial (`WHERE status = 'VIGENTE'`) e não UNIQUE simples porque
ANTERIOR e ARQUIVADA podem — e devem — repetir. SQLite suporta desde a 3.8.0
(2013) e o Postgres desde sempre; ambos os alvos do projeto atendem.

Saneamento antes de criar o índice: se o banco já tiver mais de uma linha
VIGENTE, `CREATE UNIQUE INDEX` falha e a migration aborta. Em vez de exigir
correção manual, o upgrade rebaixa as excedentes a ANTERIOR mantendo a de
`data_publicacao` mais recente — exatamente a que `obter_edicao_vigente`
já vinha devolvendo, então o comportamento observável não muda.

Revision ID: c4e7a91d2b58
Revises: 7b3acb4928f0
Create Date: 2026-08-06 11:30:14.882401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e7a91d2b58'
down_revision: Union[str, None] = '7b3acb4928f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NOME_INDICE = "uq_manuais_edicoes_vigente_unica"


def upgrade() -> None:
    # Saneamento: mantém a VIGENTE mais recente, rebaixa as outras.
    op.execute(
        sa.text(
            """
            UPDATE manuais_edicoes
               SET status = 'ANTERIOR'
             WHERE status = 'VIGENTE'
               AND id NOT IN (
                   SELECT id FROM manuais_edicoes
                    WHERE status = 'VIGENTE'
                    ORDER BY data_publicacao DESC
                    LIMIT 1
               )
            """
        )
    )

    op.create_index(
        NOME_INDICE,
        "manuais_edicoes",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'VIGENTE'"),
        postgresql_where=sa.text("status = 'VIGENTE'"),
    )


def downgrade() -> None:
    # Só o índice cai. O saneamento do upgrade não é revertido: não há registro
    # de quais linhas foram rebaixadas, e reintroduzir duas edições vigentes
    # seria restaurar um estado inconsistente, não desfazer uma mudança.
    op.drop_index(NOME_INDICE, table_name="manuais_edicoes")
