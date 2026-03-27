"""
app/aeronaves/router.py
Endpoints de gestão de aeronaves.
"""

import uuid

from fastapi import APIRouter, Depends, status

from app.aeronaves import schemas, service
from app.dependencies import DBSession, CurrentUser

router = APIRouter()


@router.get(
    "/",
    response_model=list[schemas.AeronaveListItem],
    summary="Listar aeronaves",
    description="Retorna a lista de todas as aeronaves cadastradas. (RF-15)",
)
async def listar_aeronaves(
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> list[schemas.AeronaveListItem]:
    # TODO (Dia 4): return await service.listar_aeronaves(db)
    raise NotImplementedError


@router.post(
    "/",
    response_model=schemas.AeronaveOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar aeronave",
)
async def criar_aeronave(
    dados: schemas.AeronaveCreate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.AeronaveOut:
    # TODO (Dia 4): return await service.criar_aeronave(db, dados)
    raise NotImplementedError


@router.get(
    "/{aeronave_id}",
    response_model=schemas.AeronaveOut,
    summary="Detalhar aeronave",
)
async def buscar_aeronave(
    aeronave_id: uuid.UUID,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.AeronaveOut:
    # TODO (Dia 4): return await service.buscar_aeronave(db, aeronave_id) or 404
    raise NotImplementedError


@router.put(
    "/{aeronave_id}",
    response_model=schemas.AeronaveOut,
    summary="Atualizar aeronave",
)
async def atualizar_aeronave(
    aeronave_id: uuid.UUID,
    dados: schemas.AeronaveUpdate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.AeronaveOut:
    # TODO (Dia 4): return await service.atualizar_aeronave(db, aeronave_id, dados)
    raise NotImplementedError


@router.delete(
    "/{aeronave_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover aeronave",
)
async def remover_aeronave(
    aeronave_id: uuid.UUID,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> None:
    # TODO (Dia 4): await service.remover_aeronave(db, aeronave_id)
    raise NotImplementedError
