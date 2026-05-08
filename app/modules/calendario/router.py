"""
Router do modulo de calendario.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.bootstrap.dependencies import CurrentUser, DBSession
from app.modules.calendario import schemas, service


router = APIRouter()


@router.get("/eventos", response_model=list[schemas.CalendarEventPayload])
async def listar_eventos(
    db: DBSession,
    current_user: CurrentUser,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
):
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date nao pode ser anterior a start_date.")
    return await service.get_events(db, start_date, end_date, current_user)


@router.post("/eventos", response_model=schemas.CalendarEventOut, status_code=status.HTTP_201_CREATED)
async def criar_evento(
    data: schemas.CalendarEventCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    try:
        return await service.create_event(db, data, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/eventos/{event_id}", response_model=schemas.CalendarEventOut)
async def atualizar_evento(
    event_id: uuid.UUID,
    data: schemas.CalendarEventUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    try:
        return await service.update_event(db, event_id, data, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/eventos/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_evento(
    event_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    try:
        deleted = await service.delete_event(db, event_id, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento nao encontrado.")
    return None

