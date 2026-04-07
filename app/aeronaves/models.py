"""
app/aeronaves/models.py
Modelo ORM para Aeronaves.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.enums import StatusAeronave


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
        comment="Matrícula operacional (ex: 5900, 5901)",
    )
    modelo: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="A-29",
        comment="Modelo da aeronave",
    )

    # --- Status ---
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=StatusAeronave.OPERACIONAL.value,
        comment="Status operacional: OPERACIONAL | MANUTENCAO | INATIVA",
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

    def __repr__(self) -> str:
        return f"<Aeronave matricula={self.matricula!r} status={self.status!r}>"
