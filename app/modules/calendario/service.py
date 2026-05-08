"""
Servicos do modulo de calendario.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import Usuario
from app.modules.calendario.models import CalendarEvent, EventType
from app.modules.calendario import schemas


PRIVILEGED_ROLES = {"ENCARREGADO", "ADMINISTRADOR", "ADMIN"}
ADMIN_ROLES = {"ADMINISTRADOR", "ADMIN"}


def has_privilege(current_user: Usuario) -> bool:
    return current_user.funcao in PRIVILEGED_ROLES


def is_owner(event: CalendarEvent, current_user: Usuario) -> bool:
    return event.owner_user_id == current_user.id


def should_censor(event: CalendarEvent, current_user: Usuario) -> bool:
    event_type = event.event_type
    is_private = event_type.visibility_type == "private"
    return is_private and not has_privilege(current_user) and not is_owner(event, current_user)


def format_event_for_user(event: CalendarEvent, current_user: Usuario) -> schemas.CalendarEventPayload:
    owner_trigram = event.owner.trigrama if event.owner else None
    can_edit = is_owner(event, current_user) or has_privilege(current_user)
    can_delete = current_user.funcao in ADMIN_ROLES

    if should_censor(event, current_user):
        return schemas.CalendarEventPayload(
            id=event.id,
            title="Particular",
            start=event.start_date,
            end=event.end_date,
            backgroundColor=event.event_type.color,
            icon="L",
            owner_trigram=owner_trigram,
            notes=None,
            source="calendario",
            owner_user_id=event.owner_user_id,
            can_edit=False,
            can_delete=False,
        )

    return schemas.CalendarEventPayload(
        id=event.id,
        title=event.event_type.name,
        start=event.start_date,
        end=event.end_date,
        backgroundColor=event.event_type.color,
        icon=event.event_type.icon,
        owner_trigram=owner_trigram,
        notes=event.notes,
        source="calendario",
        event_type_id=event.event_type_id,
        owner_user_id=event.owner_user_id,
        can_edit=can_edit,
        can_delete=can_delete,
    )


async def get_events(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    current_user: Usuario,
) -> list[schemas.CalendarEventPayload]:
    stmt = (
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.start_date <= end_date,
                CalendarEvent.end_date >= start_date,
            )
        )
        .options(
            selectinload(CalendarEvent.owner),
            selectinload(CalendarEvent.event_type),
        )
        .order_by(CalendarEvent.start_date.asc())
    )
    result = await db.execute(stmt)
    events = list(result.scalars().all())
    return [format_event_for_user(event, current_user) for event in events]


async def list_event_types(db: AsyncSession) -> list[EventType]:
    result = await db.execute(
        select(EventType)
        .where(EventType.active == True)  # noqa: E712
        .order_by(EventType.name.asc())
    )
    return list(result.scalars().all())


async def create_event(
    db: AsyncSession,
    data: schemas.CalendarEventCreate,
    current_user: Usuario,
) -> CalendarEvent:
    if data.owner_user_id != current_user.id and not has_privilege(current_user):
        raise PermissionError("Apenas perfis privilegiados podem lancar eventos para terceiros.")

    await _ensure_user_exists(db, data.owner_user_id)
    await _ensure_event_type_exists(db, data.event_type_id)

    event = CalendarEvent(
        **data.model_dump(),
        created_by_user_id=current_user.id,
    )
    db.add(event)
    await db.flush()
    return await _get_event_or_raise(db, event.id)


async def update_event(
    db: AsyncSession,
    event_id: uuid.UUID,
    data: schemas.CalendarEventUpdate,
    current_user: Usuario,
) -> CalendarEvent:
    event = await _get_event_or_raise(db, event_id)
    if not is_owner(event, current_user) and not has_privilege(current_user):
        raise PermissionError("Apenas o dono ou perfil privilegiado pode editar o evento.")

    update_data = data.model_dump(exclude_unset=True)
    start_date = update_data.get("start_date", event.start_date)
    end_date = update_data.get("end_date", event.end_date)
    if end_date < start_date:
        raise ValueError("A data de termino nao pode ser anterior a data de inicio.")

    if "owner_user_id" in update_data:
        if update_data["owner_user_id"] != current_user.id and not has_privilege(current_user):
            raise PermissionError("Apenas perfis privilegiados podem transferir eventos.")
        await _ensure_user_exists(db, update_data["owner_user_id"])

    if "event_type_id" in update_data:
        await _ensure_event_type_exists(db, update_data["event_type_id"])

    for field, value in update_data.items():
        setattr(event, field, value)

    await db.flush()
    return await _get_event_or_raise(db, event.id)


async def delete_event(
    db: AsyncSession,
    event_id: uuid.UUID,
    current_user: Usuario,
) -> bool:
    if current_user.funcao not in ADMIN_ROLES:
        raise PermissionError("Apenas administrador pode excluir eventos.")

    event = await db.get(CalendarEvent, event_id)
    if event is None:
        return False

    await db.delete(event)
    await db.flush()
    return True


async def _ensure_user_exists(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await db.get(Usuario, user_id)
    if user is None:
        raise LookupError("Usuario nao encontrado.")


async def _ensure_event_type_exists(db: AsyncSession, event_type_id: uuid.UUID) -> None:
    event_type = await db.get(EventType, event_type_id)
    if event_type is None or not event_type.active:
        raise LookupError("Tipo de evento nao encontrado ou inativo.")


async def _get_event_or_raise(db: AsyncSession, event_id: uuid.UUID) -> CalendarEvent:
    stmt = (
        select(CalendarEvent)
        .where(CalendarEvent.id == event_id)
        .options(
            selectinload(CalendarEvent.owner),
            selectinload(CalendarEvent.event_type),
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    if event is None:
        raise LookupError("Evento nao encontrado.")
    return event
