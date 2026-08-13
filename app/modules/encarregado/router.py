"""
app/modules/encarregado/router.py
Endpoints REST do módulo Encarregado — Ciência de Alterações
(feature_encarregado_ciencia.md v2.0, §8).

Leitura aberta a qualquer autenticado; dar/desfazer ciência restrito a
ENCARREGADO/ADMINISTRADOR (§6).
"""

import uuid

from fastapi import APIRouter, status

from app.bootstrap.dependencies import CurrentUser, DBSession, EncarregadoOuAdmin
from app.modules.encarregado import schemas, service

router = APIRouter()


@router.get(
    "/pendentes",
    response_model=schemas.ListaPendentesResponse,
    summary="Listar alterações pendentes de ciência, agrupadas por categoria",
)
async def listar_pendentes(
    db: DBSession,
    _: CurrentUser,
) -> schemas.ListaPendentesResponse:
    return await service.listar_pendentes(db)


@router.post(
    "/ciencia",
    response_model=schemas.CienciaOut,
    status_code=status.HTTP_200_OK,
    summary="Registrar ciência de um item (idempotente)",
)
async def dar_ciencia(
    dados: schemas.DarCienciaRequest,
    db: DBSession,
    usuario_atual: EncarregadoOuAdmin,
) -> schemas.CienciaOut:
    return await service.dar_ciencia(db, dados, usuario_atual.id)


@router.delete(
    "/ciencia/{ciencia_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desfazer uma ciência já registrada",
)
async def desfazer_ciencia(
    ciencia_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> None:
    await service.desfazer_ciencia(db, ciencia_id)
