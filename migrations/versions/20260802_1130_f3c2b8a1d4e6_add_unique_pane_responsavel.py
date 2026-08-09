"""add_unique_pane_responsavel

Adiciona UNIQUE(pane_id, usuario_id) em pane_responsaveis.

Motivo (relatorio_panes_service.md, item #2): a verificação de duplicidade em
`adicionar_responsavel` e `concluir_pane` não é atômica (TOCTOU) — duas
requisições concorrentes podem passar na checagem e inserir o mesmo par
(pane_id, usuario_id). A constraint torna o `IntegrityError`, agora tratado no
service, a rede de segurança real.

Verificado antes de escrever esta migration: 0 duplicatas na base local
(`var/db`) para (pane_id, usuario_id) em pane_responsaveis.

Revision ID: f3c2b8a1d4e6
Revises: e7a1c3d9b2f4
Create Date: 2026-08-02 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f3c2b8a1d4e6'
down_revision: Union[str, None] = 'e7a1c3d9b2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('pane_responsaveis', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_pane_responsavel_pane_usuario', ['pane_id', 'usuario_id']
        )


def downgrade() -> None:
    with op.batch_alter_table('pane_responsaveis', schema=None) as batch_op:
        batch_op.drop_constraint('uq_pane_responsavel_pane_usuario', type_='unique')
