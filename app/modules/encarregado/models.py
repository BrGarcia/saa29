"""
app/modules/encarregado/models.py
Modelo ORM da ciência de alterações do Encarregado.

EncarregadoCiencia é a ÚNICA tabela de escrita deste módulo. Não possui FK
para panes/inspecao_tarefas/instalacoes/controle_vencimentos por design —
o módulo consulta essas tabelas apenas em leitura (service.py) e nunca as
referencia estruturalmente, para garantir que nenhuma migração ou exclusão
nos módulos de origem possa quebrar o histórico de ciência
(feature_encarregado_ciencia.md §1.2/§3.1).
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import Usuario


class EncarregadoCiencia(Base):
    """
    Registro de que um usuário deu ciência de uma alteração de origem, para
    fins de transcrição posterior no SILOMS. A ciência é global (não por
    usuário): uma vez registrada, o item some da lista de pendentes para
    todos, e a própria linha guarda quem/quando a deu.
    """

    __tablename__ = "encarregado_ciencias"
    __table_args__ = (
        UniqueConstraint(
            "categoria", "evento", "registro_id",
            name="uq_encarregado_ciencia_evento_unico",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    categoria: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    evento: Mapped[str] = mapped_column(String(20), nullable=False)
    registro_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False,
    )
    dado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    usuario: Mapped["Usuario"] = relationship(lazy="select")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<EncarregadoCiencia categoria={self.categoria!r} evento={self.evento!r} registro={self.registro_id}>"
