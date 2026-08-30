"""
app/modules/pedidos/models.py
Modelo ORM da Central de Pedidos — módulo standalone, desacoplado de
INVENTÁRIO e VENCIMENTOS (feature_controle_pedidos.md v2.0, §2.2).
"""

from __future__ import annotations
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import StatusPedido, TipoPedido

if TYPE_CHECKING:
    from app.modules.aeronaves.models import Aeronave
    from app.modules.auth.models import Usuario


class Pedido(Base):
    """Registro administrativo/logístico de um pedido de reposição de equipamento.

    Desacoplado de INVENTÁRIO/VENCIMENTOS por design: `part_number` e
    `nomenclatura` são atributos de texto imutáveis, não FKs para o catálogo
    de equipamentos — o pedido permanece auditável mesmo que o catálogo mude
    depois (feature_controle_pedidos.md §2.1).
    """
    __tablename__ = "pedidos"
    __table_args__ = (
        # O banco já tem esta constraint nomeada, criada pela migration que
        # introduziu o módulo. O model declarava a unicidade só via
        # `unique=True` na coluna, que o SQLAlchemy materializa como índice
        # único ANÔNIMO — então o `alembic --autogenerate` não encontrava
        # `uq_pedidos_numero_pedido` no metadata e propunha removê-la em toda
        # migration gerada no repositório. Declará-la aqui alinha model e
        # banco e silencia esse alarme falso.
        #
        # A unicidade em si nunca esteve em risco: o índice único
        # `ix_pedidos_numero_pedido` (do `unique=True` abaixo) já a garante
        # sozinho. Isto é redundância herdada, não correção de regra.
        UniqueConstraint("numero_pedido", name="uq_pedidos_numero_pedido"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    numero_pedido: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    aeronave_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeronaves.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    part_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    nomenclatura: Mapped[str] = mapped_column(String(100), nullable=False)

    tipo_pedido: Mapped[str] = mapped_column(String(20), nullable=False, default=TipoPedido.NORMAL.value)
    numero_emergencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatusPedido.PENDENTE.value, index=True
    )
    observacao: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    data_pedido: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    data_atendimento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_cancelamento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(500), nullable=True)

    solicitante_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    atendido_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    cancelado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )

    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relacionamentos unidirecionais (sem back_populates) — não é necessário
    # tocar Aeronave nem Usuario para este módulo funcionar, o que também
    # evita conflito de merge com outras equipes editando esses modelos.
    aeronave: Mapped["Aeronave"] = relationship(lazy="select")
    solicitante: Mapped["Usuario"] = relationship(foreign_keys=[solicitante_id], lazy="select")
    atendido_por: Mapped["Usuario | None"] = relationship(foreign_keys=[atendido_por_id], lazy="select")
    cancelado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[cancelado_por_id], lazy="select")

    def __repr__(self) -> str:
        return f"<Pedido id={self.id} numero={self.numero_pedido!r} status={self.status!r}>"
