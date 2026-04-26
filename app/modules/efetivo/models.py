"""
app/modules/efetivo/models.py
Modelos ORM para a gestão de disponibilidade de pessoal.
"""

from __future__ import annotations
import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import Usuario

class Indisponibilidade(Base):
    """Registro de período onde um usuário não pode ser alocado para panes."""
    __tablename__ = "indisponibilidades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    usuario: Mapped["Usuario"] = relationship() # type: ignore
