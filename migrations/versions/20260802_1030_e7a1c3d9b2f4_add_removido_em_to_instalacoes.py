"""add_removido_em_to_instalacoes

Cria a coluna dedicada ao timestamp do EVENTO de remoção em `instalacoes`.

Motivo (relatorio_equipamentos_services.md, item #10): `updated_at` vinha sendo
usado como "data da remoção", mas qualquer update posterior no registro
corrompia o histórico. `removido_em` é escrito apenas no ato da remoção.

O backfill copia COALESCE(updated_at, created_at) nas linhas já removidas,
preservando o histórico existente.

Revision ID: e7a1c3d9b2f4
Revises: 994ef3b91511
Create Date: 2026-08-02 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a1c3d9b2f4'
down_revision: Union[str, None] = '994ef3b91511'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('instalacoes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('removido_em', sa.DateTime(timezone=True), nullable=True))

    # Backfill: histórico já registrado passa a ter timestamp dedicado.
    op.execute(
        """
        UPDATE instalacoes
           SET removido_em = COALESCE(updated_at, created_at)
         WHERE data_remocao IS NOT NULL
           AND removido_em IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table('instalacoes', schema=None) as batch_op:
        batch_op.drop_column('removido_em')
