"""
app/aeronaves/router.py
Endpoints de gestao de aeronaves.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.modules.aeronaves import schemas, service
from app.bootstrap.dependencies import AdminRequired, CurrentUser, DBSession, EncarregadoOuAdmin, EncarregadoInspetorOuAdmin

router = APIRouter()


@router.get(
    "/",
    response_model=list[schemas.AeronaveListItem],
    summary="Listar aeronaves",
    description="Retorna a lista de aeronaves cadastradas. (RF-15)",
)
async def listar_aeronaves(
    db: DBSession,
    _: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    incluir_inativas: bool = Query(default=False),
) -> list[schemas.AeronaveListItem]:
    aeronaves = await service.listar_aeronaves(
        db,
        skip=skip,
        limit=limit,
        incluir_inativas=incluir_inativas,
    )
    return [schemas.AeronaveListItem.model_validate(a) for a in aeronaves]


@router.post(
    "/",
    response_model=schemas.AeronaveOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar aeronave",
)
async def criar_aeronave(
    dados: schemas.AeronaveCreate,
    db: DBSession,
    _: AdminRequired,
) -> schemas.AeronaveOut:
    try:
        aeronave = await service.criar_aeronave(db, dados)
        return schemas.AeronaveOut.model_validate(aeronave)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{aeronave_id}",
    response_model=schemas.AeronaveOut,
    summary="Detalhar aeronave",
)
async def buscar_aeronave(
    aeronave_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> schemas.AeronaveOut:
    aeronave = await service.buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aeronave não encontrada.",
        )
    return schemas.AeronaveOut.model_validate(aeronave)


@router.put(
    "/{aeronave_id}",
    response_model=schemas.AeronaveOut,
    summary="Atualizar aeronave",
)
async def atualizar_aeronave(
    aeronave_id: uuid.UUID,
    dados: schemas.AeronaveUpdate,
    db: DBSession,
    _: AdminRequired,
) -> schemas.AeronaveOut:
    try:
        aeronave = await service.atualizar_aeronave(db, aeronave_id, dados)
        return schemas.AeronaveOut.model_validate(aeronave)
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrada" in detail.lower()
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=status_code,
            detail=detail,
        ) from exc


@router.post(
    "/{aeronave_id}/toggle-status",
    response_model=schemas.AeronaveOut,
    summary="Alternar status operacional da aeronave",
)
async def alternar_status_aeronave(
    aeronave_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> schemas.AeronaveOut:
    try:
        aeronave = await service.alternar_status_aeronave(db, aeronave_id)
        return schemas.AeronaveOut.model_validate(aeronave)
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrada" in detail.lower()
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=status_code,
            detail=detail,
        ) from exc
