"""
app/aeronaves/models.py
Modelo ORM para Aeronaves.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Date, Float, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import StatusAeronave

if TYPE_CHECKING:
    from app.modules.equipamentos.models import Instalacao
    from app.modules.panes.models import Pane


class Aeronave(Base):
    """
    Representa uma aeronave A-29 cadastrada no sistema.

    Uma aeronave pode ter múltiplas panes registradas.
    O controle de equipamentos é feito pelo módulo de instalações.
    """

    __tablename__ = "aeronaves"

    # --- Chave primária ---
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        comment="Identificador único universal da aeronave",
    )

    # --- Identificação ---
    part_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Part number da aeronave",
    )
    serial_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Número de série único da aeronave",
    )
    matricula: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Matrícula operacional (ex: 5916, 5902)",
    )
    modelo: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="A-29",
        comment="Modelo da aeronave",
    )

    # --- Status ---
    status: Mapped[StatusAeronave] = mapped_column(
        Enum(StatusAeronave, native_enum=False, length=20),
        nullable=False,
        default=StatusAeronave.DISPONIVEL,
        comment="Status operacional: DISPONIVEL | INDISPONIVEL | INSPEÇÃO | ESTOCADA | INATIVA",
    )

    # --- Controle de Horas e Tempo ---
    horas_voo_total: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Horas totais acumuladas da aeronave",
    )
    data_inicio_operacao: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Data de início de operação da aeronave",
    )
    horas_atualizadas_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Data e hora da última atualização das horas de voo",
    )

    # --- Auditoria ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="Atualizado automaticamente em cada modificação",
    )

    # --- Relacionamentos ---
    panes: Mapped[list] = relationship(
        "Pane",
        back_populates="aeronave",
        lazy="select",
    )
    instalacoes: Mapped[list] = relationship(
        "Instalacao",
        back_populates="aeronave",
        lazy="select",
    )
    inspecoes: Mapped[list] = relationship(
        "Inspecao",
        back_populates="aeronave",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Aeronave matricula={self.matricula!r} status={self.status.value!r}>"
