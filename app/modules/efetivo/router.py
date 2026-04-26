"""
app/modules/efetivo/router.py
Endpoints para a gestão de disponibilidade de pessoal.
"""

import uuid
from datetime import date
from fastapi import APIRouter, HTTPException, status, Query

from app.modules.efetivo import schemas, service
from app.bootstrap.dependencies import DBSession, CurrentUser, EncarregadoOuAdmin

router = APIRouter()

@router.post("/", response_model=schemas.IndisponibilidadeOut, status_code=status.HTTP_201_CREATED)
async def registrar_indisponibilidade(dados: schemas.IndisponibilidadeCreate, db: DBSession, _: EncarregadoOuAdmin):
    try:
        return await service.registrar_indisponibilidade(db, dados)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ativas", response_model=list[schemas.IndisponibilidadeOut])
async def listar_ativas(db: DBSession, _: CurrentUser, data_ref: date | None = Query(None)):
    return await service.listar_indisponibilidades_ativas(db, data_ref)

@router.get("/usuario/{usuario_id}", response_model=list[schemas.IndisponibilidadeOut])
async def listar_por_usuario(usuario_id: uuid.UUID, db: DBSession, _: CurrentUser):
    return await service.listar_indisponibilidades_por_usuario(db, usuario_id)

@router.delete("/{indisp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover(indisp_id: uuid.UUID, db: DBSession, _: EncarregadoOuAdmin):
    sucesso = await service.remover_indisponibilidade(db, indisp_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Indisponibilidade não encontrada")
    return None
