"""
Servicos do modulo de calendario.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import Usuario
from app.modules.auth.roles import ADMIN_FUNCTIONS, PRIVILEGED_FUNCTIONS
from app.modules.calendario.models import CalendarEvent, EventType
from app.modules.calendario import schemas
from app.shared.core import exceptions as domain_exc

logger = logging.getLogger(__name__)

# Limite defensivo de registros por consulta (10.4)
_QUERY_LIMIT = 5_000


def has_privilege(current_user: Usuario) -> bool:
    """Verifica se o usuÃ¡rio tem papel privilegiado (ENCARREGADO ou ADMINISTRADOR)."""
    return current_user.funcao in PRIVILEGED_FUNCTIONS


def is_owner(event: CalendarEvent, current_user: Usuario) -> bool:
    return event.owner_user_id == current_user.id


def _should_censor(event: CalendarEvent, current_user: Usuario) -> bool:
    event_type = event.event_type
    is_private = event_type.visibility_type == "private"
    return is_private and not has_privilege(current_user) and not is_owner(event, current_user)


def format_event_for_user(event: CalendarEvent, current_user: Usuario) -> schemas.CalendarEventPayload:
    owner_trigram = event.owner.trigrama if event.owner else None
    can_edit = is_owner(event, current_user) or has_privilege(current_user)
    can_delete = current_user.funcao in ADMIN_FUNCTIONS

    # 10.2 â€” censura completa para eventos privados de terceiros
    if _should_censor(event, current_user):
        neutral_color = event.event_type.private_color or "#9CA3AF"
        return schemas.CalendarEventPayload(
            id=event.id,
            title="Particular",
            start=event.start_date,
            end=event.end_date,
            backgroundColor=neutral_color,
            icon="L",
            owner_trigram=None,        # nÃ£o vazar identidade
            notes=None,
            source="calendario",
            event_type_id=None,        # nÃ£o vazar tipo (deduz cor/natureza)
            owner_user_id=None,        # nÃ£o vazar UUID do dono
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


def _normalize_datetime_for_sort(dt: datetime) -> datetime:
    """Garante comparação segura entre datetimes aware e naive em sorted()."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def get_events(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    current_user: Usuario,
) -> list[schemas.CalendarEventPayload]:
    events = await _get_calendar_events(db, start_date, end_date, current_user)
    events.extend(await _get_inspection_events(db, start_date, end_date))
    return sorted(events, key=lambda event: _normalize_datetime_for_sort(event.start))


async def _get_calendar_events(
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
                CalendarEvent.deleted_at.is_(None),   # 10.5 â€” excluir soft-deletes
            )
        )
        .options(
            selectinload(CalendarEvent.owner),
            selectinload(CalendarEvent.event_type),
        )
        .order_by(CalendarEvent.start_date.asc())
        .limit(_QUERY_LIMIT)   # 10.4 â€” proteÃ§Ã£o contra DoS
    )
    result = await db.execute(stmt)
    events = list(result.scalars().all())

    if len(events) == _QUERY_LIMIT:  # 10.4 â€” alerta quando limite Ã© atingido
        logger.warning(
            "calendar_query_limit_hit",
            extra={
                "source": "calendar_events",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "limit": _QUERY_LIMIT,
            },
        )

    return [format_event_for_user(event, current_user) for event in events]


async def _get_inspection_events(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> list[schemas.CalendarEventPayload]:
    # Import lazy para evitar ciclo (inspecoes -> calendario seria circular)
    from app.modules.inspecoes.models import Inspecao  # noqa: PLC0415
    from app.shared.core.enums import StatusInspecao  # noqa: PLC0415

    stmt = (
        select(Inspecao)
        .where(
            Inspecao.data_fim_prevista.is_not(None),
            Inspecao.data_fim_prevista >= start_date,
            Inspecao.data_fim_prevista <= end_date,
            # 10.1 â€” filtrar apenas inspeÃ§Ãµes em curso
            Inspecao.status.in_([StatusInspecao.ABERTA.value, StatusInspecao.EM_ANDAMENTO.value]),
        )
        .options(
            selectinload(Inspecao.aeronave),
            selectinload(Inspecao.tipos_aplicados),
        )
        .order_by(Inspecao.data_fim_prevista.asc())
        .limit(_QUERY_LIMIT)   # 10.4
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    if len(rows) == _QUERY_LIMIT:
        logger.warning(
            "calendar_query_limit_hit",
            extra={
                "source": "inspection_events",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "limit": _QUERY_LIMIT,
            },
        )

    payloads: list[schemas.CalendarEventPayload] = []
    for inspecao in rows:
        dpe = inspecao.data_fim_prevista
        if dpe is None:
            continue
        if dpe.tzinfo is None:
            dpe = dpe.replace(tzinfo=timezone.utc)
        matricula = getattr(inspecao.aeronave, "matricula", None) or "ANV"
        tipos = ", ".join(tipo.codigo for tipo in inspecao.tipos_aplicados) or "Inspecao"
        payloads.append(
            schemas.CalendarEventPayload(
                id=inspecao.id,
                title=f"DPE {matricula} {tipos}",
                start=dpe,
                end=dpe,
                backgroundColor="#0f766e",
                icon="DPE",
                owner_trigram=inspecao.aberto_por_trigrama,
                notes=inspecao.observacoes,
                source="inspecao",
                can_edit=False,
                can_delete=False,
            )
        )
    return payloads


async def list_event_types(db: AsyncSession, only_active: bool = True) -> list[EventType]:
    stmt = select(EventType)
    if only_active:
        stmt = stmt.where(EventType.active == True)  # noqa: E712
    stmt = stmt.order_by(EventType.active.desc(), EventType.name.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_event_type(
    db: AsyncSession,
    data: schemas.EventTypeCreate,
) -> EventType:
    # RISCO-03: sem pre-check separado de nome duplicado — um SELECT seguido
    # de INSERT deixaria uma janela TOCTOU entre checar e gravar. O UNIQUE
    # de EventType.name (models.py) é a única fonte de verdade; o SAVEPOINT
    # cobre tanto o caso comum (nome já existe) quanto a corrida real, com o
    # mesmo ValueError/400 já usado pelo restante do módulo.
    event_type = EventType(**data.model_dump())
    try:
        async with db.begin_nested():
            db.add(event_type)
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao criar tipo de evento %r: %s", data.name, exc.orig)
        raise ValueError(f"Ja existe um tipo de evento com o nome '{data.name}'.") from exc
    await db.refresh(event_type)
    return event_type


async def update_event_type(
    db: AsyncSession,
    type_id: uuid.UUID,
    data: schemas.EventTypeUpdate,
) -> EventType:
    event_type = await db.get(EventType, type_id)
    if event_type is None:
        raise domain_exc.EntidadeNaoEncontradaError("Tipo de evento nao encontrado.")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event_type, field, value)

    try:
        # RISCO-03: mesmo raciocínio de create_event_type — sem pre-check
        # separado, o SAVEPOINT + UNIQUE é a única checagem de duplicidade.
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao atualizar tipo de evento %s: %s", type_id, exc.orig)
        nome = update_data.get("name", event_type.name)
        raise ValueError(f"Ja existe um tipo de evento com o nome '{nome}'.") from exc
    await db.refresh(event_type)
    return event_type


async def delete_event_type(
    db: AsyncSession,
    type_id: uuid.UUID,
) -> None:
    event_type = await db.get(EventType, type_id)
    if event_type is None:
        raise domain_exc.EntidadeNaoEncontradaError("Tipo de evento nao encontrado.")

    # Verificar se existem eventos vinculados (incluindo os soft-deletados)
    stmt = select(CalendarEvent).where(CalendarEvent.event_type_id == type_id)
    result = await db.execute(stmt)
    if result.scalars().first() is not None:
        raise ValueError(
            "Nao e possivel excluir esta categoria pois existem eventos associados a ela. "
            "Desative-a em vez disso."
        )

    await db.delete(event_type)
    await db.flush()


async def create_event(
    db: AsyncSession,
    data: schemas.CalendarEventCreate,
    current_user: Usuario,
) -> CalendarEvent:
    if data.owner_user_id != current_user.id and not has_privilege(current_user):
        raise domain_exc.PermissaoNegadaError("Apenas perfis privilegiados podem lancar eventos para terceiros.")

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
        raise domain_exc.PermissaoNegadaError("Apenas o dono ou perfil privilegiado pode editar o evento.")

    update_data = data.model_dump(exclude_unset=True)
    start_date = update_data.get("start_date", event.start_date)
    end_date = update_data.get("end_date", event.end_date)
    if end_date < start_date:
        raise ValueError("A data de termino nao pode ser anterior a data de inicio.")

    if "owner_user_id" in update_data:
        if update_data["owner_user_id"] != current_user.id and not has_privilege(current_user):
            raise domain_exc.PermissaoNegadaError("Apenas perfis privilegiados podem transferir eventos.")
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
    # 10.3 — verificação de papel feita no router via AdminRequired;
    # mantida aqui apenas como última linha de defesa.
    #
    # DÚVIDA-08 (decisão de produto, achados_calendario.md): exclusão exige
    # ADMIN_FUNCTIONS especificamente, mais restrito que PRIVILEGED_FUNCTIONS
    # (usado por criar/editar/transferir e para ler `notes` de evento
    # privado de terceiro). Assimetria proposital, não descuido — excluir é
    # destrutivo e não tem tela de restauração para o soft-delete (10.5).
    if current_user.funcao not in ADMIN_FUNCTIONS:
        raise domain_exc.PermissaoNegadaError("Apenas administrador pode excluir eventos.")

    event = await db.get(CalendarEvent, event_id)
    if event is None or event.deleted_at is not None:
        return False

    # 10.5 — log estruturado antes do soft-delete
    logger.warning(
        "calendar_event_deleted",
        extra={
            "event_id": str(event.id),
            "deleted_by": str(current_user.id),
            "owner_user_id": str(event.owner_user_id),
            "event_type_id": str(event.event_type_id),
            "start_date": event.start_date.isoformat(),
        },
    )

    # 10.5 — soft-delete: preserva registro para auditoria
    event.deleted_at = datetime.now(timezone.utc)
    event.deleted_by_user_id = current_user.id
    await db.flush()
    return True


async def _ensure_user_exists(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await db.get(Usuario, user_id)
    if user is None:
        raise domain_exc.EntidadeNaoEncontradaError("Usuario nao encontrado.")


async def _ensure_event_type_exists(db: AsyncSession, event_type_id: uuid.UUID) -> None:
    event_type = await db.get(EventType, event_type_id)
    if event_type is None or not event_type.active:
        raise domain_exc.EntidadeNaoEncontradaError("Tipo de evento nao encontrado ou inativo.")


async def _get_event_or_raise(db: AsyncSession, event_id: uuid.UUID) -> CalendarEvent:
    """Retorna evento ativo (não soft-deletado) ou levanta EntidadeNaoEncontradaError."""
    stmt = (
        select(CalendarEvent)
        .where(
            CalendarEvent.id == event_id,
            CalendarEvent.deleted_at.is_(None),   # 10.5
        )
        .options(
            selectinload(CalendarEvent.owner),
            selectinload(CalendarEvent.event_type),
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    if event is None:
        raise domain_exc.EntidadeNaoEncontradaError("Evento nao encontrado.")
    return event
