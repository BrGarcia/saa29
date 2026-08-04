"""
Modelos ORM do modulo de calendario.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.bootstrap.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import Usuario


class UTCDateTime(TypeDecorator):
    """`DateTime(timezone=True)` com round-trip garantido em UTC (BUG-02).

    O dialeto SQLite (`aiosqlite`) não tem suporte nativo a timezone: ele
    grava só os campos de data/hora (sem o offset) e devolve um `datetime`
    *naive* na leitura — se o valor gravado não estivesse em UTC, o offset
    original seria perdido silenciosamente, não apenas o `tzinfo`. Por isso
    esta classe normaliza os dois lados: converte para UTC antes de gravar
    (`process_bind_param`) e reanexa `tzinfo=UTC` ao ler de volta
    (`process_result_value`). Sem isso, comparar o valor lido contra um
    `datetime` aware vindo do payload da API também levanta
    `TypeError: can't compare offset-naive and offset-aware datetimes`.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class EventType(Base):
    """Catalogo de tipos de evento exibidos no calendario."""

    __tablename__ = "event_types"
    __table_args__ = (
        CheckConstraint(
            "visibility_type IN ('public', 'private')",
            name="ck_event_types_visibility_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    visibility_type: Mapped[str] = mapped_column(String(20), nullable=False, default="public", index=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    # Cor alternativa neutra exibida quando evento é censurado por privacidade (10.2)
    private_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    icon: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, onupdate=func.now(), nullable=True)

    events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="event_type",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<EventType name={self.name!r} visibility={self.visibility_type!r}>"


class CalendarEvent(Base):
    """Evento proprio do calendario, associado a um militar e a um tipo."""

    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_calendar_events_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    end_date: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, onupdate=func.now(), nullable=True)
    # Soft-delete (10.5): nao remove fisicamente do banco, apenas marca como excluido
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    owner: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[owner_user_id], lazy="selectin")
    created_by: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[created_by_user_id], lazy="selectin")
    deleted_by: Mapped["Usuario | None"] = relationship("Usuario", foreign_keys=[deleted_by_user_id], lazy="selectin")
    event_type: Mapped[EventType] = relationship(back_populates="events", lazy="selectin")

    def __repr__(self) -> str:
        return f"<CalendarEvent id={self.id} owner={self.owner_user_id} start={self.start_date}>"

