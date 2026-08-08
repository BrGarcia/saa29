"""
migrations/script.py.mako
Template para geração de scripts de migração pelo Alembic.
"""

"""publicacoes_m5_fim_map_por_edicao

Escopa `manuais_fim_map` por edição — corrige o BUG-03 de
`docs/backlog/modulo_publicacoes/dividas/achados_service.md`.

O problema: a tabela era global (sem coluna de edição) e
`sincronizar_fim_map` fazia `DELETE FROM manuais_fim_map` sem `WHERE` antes de
repopular, resolvendo `documento_id` contra a edição que estava sendo
indexada — não necessariamente a VIGENTE. No fluxo normal de publicação
(indexar uma edição nova, que nasce `AGUARDANDO_ATIVACAO` enquanto a anterior
segue `VIGENTE`), o mapa do FIM passava a apontar para documentos da edição
nova até alguém ativá-la: `GET /api/fim` e `/api/fim/por-ata/{ata}` devolviam
`doc_id`/`viewer_url` de uma edição diferente da que o resto do módulo serve.

A correção: `edicao_id` (FK CASCADE) em cada linha do mapa. `sincronizar_fim_map`
passa a apagar e reescrever só a fatia da edição indexada; as leituras
(`buscar_por_mensagem_fim`, `listar_fim_por_ata`, `status_do_catalogo`) passam
a filtrar pela edição VIGENTE. A `UniqueConstraint` de `mensagem`, que era
global, vira `(edicao_id, mensagem)` — sem isso, a mesma mensagem não poderia
existir em duas edições retidas ao mesmo tempo, o que é exatamente o estado
normal entre uma publicação e a próxima.

Backfill: a tabela não guarda de qual indexação cada linha veio, então a
edição é inferida a partir do que o banco já sabe.

1. Procedimento com `documento_id` resolvido: usa a edição REAL do documento
   referenciado (via `manuais_documentos` → `manuais`) — preserva o que os
   dados já mostram, sem presumir que a linha sempre pertenceu à vigente
   (é exatamente essa presunção que o BUG-03 diz estar errada hoje).
2. Procedimento sem PDF (`documento_id IS NULL`): não há como saber de qual
   indexação veio — cai na edição VIGENTE mais recente, que é o estado que a
   aplicação mostra como verdade atualmente.
3. Sobra sem VIGENTE nenhuma (acervo nunca ativado): descartada. A tabela é
   100% derivada de `fim.json`/`sincronizar_fim_map` e é regravada por
   inteiro na próxima indexação — não há dado a preservar aqui.

Revision ID: b523f301e9f1
Revises: c4e7a91d2b58
Create Date: 2026-08-08 07:29:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b523f301e9f1'
down_revision: Union[str, None] = 'c4e7a91d2b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'manuais_fim_map',
        sa.Column('edicao_id', sa.Uuid(), nullable=True),
    )

    # Backfill 1: procedimento com PDF resolvido — edição real do documento.
    op.execute(
        sa.text(
            """
            UPDATE manuais_fim_map
               SET edicao_id = (
                   SELECT m.edicao_id
                     FROM manuais_documentos d
                     JOIN manuais m ON m.id = d.manual_id
                    WHERE d.id = manuais_fim_map.documento_id
               )
             WHERE documento_id IS NOT NULL
            """
        )
    )

    # Backfill 2: procedimento sem PDF — cai na VIGENTE mais recente.
    op.execute(
        sa.text(
            """
            UPDATE manuais_fim_map
               SET edicao_id = (
                   SELECT id FROM manuais_edicoes
                    WHERE status = 'VIGENTE'
                    ORDER BY data_publicacao DESC
                    LIMIT 1
               )
             WHERE edicao_id IS NULL
            """
        )
    )

    # Sobra sem nenhuma VIGENTE para herdar: descarta. `sincronizar_fim_map`
    # regrava a tabela inteira na próxima indexação de qualquer forma.
    op.execute(sa.text("DELETE FROM manuais_fim_map WHERE edicao_id IS NULL"))

    with op.batch_alter_table('manuais_fim_map', schema=None) as batch_op:
        batch_op.alter_column(
            'edicao_id', existing_type=sa.Uuid(), nullable=False
        )
        batch_op.create_foreign_key(
            'fk_manuais_fim_map_edicao_id',
            'manuais_edicoes',
            ['edicao_id'],
            ['id'],
            ondelete='CASCADE',
        )
        batch_op.drop_constraint('uq_manuais_fim_map_mensagem', type_='unique')
        batch_op.create_unique_constraint(
            'uq_manuais_fim_map_edicao_mensagem', ['edicao_id', 'mensagem']
        )
        batch_op.create_index(
            batch_op.f('ix_manuais_fim_map_edicao_id'), ['edicao_id'], unique=False
        )


def downgrade() -> None:
    # Só o esquema volta. O conteúdo NÃO é revertido para o estado global
    # anterior — a próxima indexação reescreve a tabela inteira de qualquer
    # forma, então não há dado "perdido" que valha reconstruir aqui.
    with op.batch_alter_table('manuais_fim_map', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_manuais_fim_map_edicao_id'))
        batch_op.drop_constraint(
            'uq_manuais_fim_map_edicao_mensagem', type_='unique'
        )
        batch_op.create_unique_constraint('uq_manuais_fim_map_mensagem', ['mensagem'])
        batch_op.drop_constraint('fk_manuais_fim_map_edicao_id', type_='foreignkey')
        batch_op.drop_column('edicao_id')
