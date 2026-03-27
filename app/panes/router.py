"""
app/panes/router.py
Endpoints de gestão de panes aeronáuticas.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, Query, status

from app.panes import schemas, service
from app.dependencies import DBSession, CurrentUser

router = APIRouter()


@router.post(
    "/",
    response_model=schemas.PaneOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nova pane (RF-07, RF-08)",
)
async def criar_pane(
    dados: schemas.PaneCreate,
    db: DBSession = Depends(),
    usuario_atual: CurrentUser = Depends(),
) -> schemas.PaneOut:
    """Abre uma nova pane vinculada a uma aeronave. Status inicial = ABERTA."""
    # TODO (Dia 4): return await service.criar_pane(db, dados, usuario_atual.id)
    raise NotImplementedError


@router.get(
    "/",
    response_model=list[schemas.PaneListItem],
    summary="Listar panes (RF-03, RF-06)",
)
async def listar_panes(
    texto: str | None = Query(default=None, description="Filtro por texto"),
    status_pane: schemas.StatusPane | None = Query(default=None, alias="status"),
    aeronave_id: uuid.UUID | None = Query(default=None),
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> list[schemas.PaneListItem]:
    """Lista panes com filtros opcionais (texto, status, aeronave, data)."""
    # TODO (Dia 4):
    # filtros = FiltroPane(texto=texto, status=status_pane, aeronave_id=aeronave_id)
    # return await service.listar_panes(db, filtros)
    raise NotImplementedError


@router.get(
    "/{pane_id}",
    response_model=schemas.PaneOut,
    summary="Detalhar pane (RF-09)",
)
async def buscar_pane(
    pane_id: uuid.UUID,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.PaneOut:
    """Retorna dados completos da pane com anexos e responsáveis."""
    # TODO (Dia 4): return await service.buscar_pane(db, pane_id) or 404
    raise NotImplementedError


@router.put(
    "/{pane_id}",
    response_model=schemas.PaneOut,
    summary="Editar pane (RF-10, RF-11)",
)
async def editar_pane(
    pane_id: uuid.UUID,
    dados: schemas.PaneUpdate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.PaneOut:
    """Edita descrição e/ou status. RN-03: apenas panes não resolvidas."""
    # TODO (Dia 4): return await service.editar_pane(db, pane_id, dados)
    raise NotImplementedError


@router.post(
    "/{pane_id}/concluir",
    response_model=schemas.PaneOut,
    summary="Concluir pane (RF-12, RF-13)",
)
async def concluir_pane(
    pane_id: uuid.UUID,
    dados: schemas.PaneConcluir,
    db: DBSession = Depends(),
    usuario_atual: CurrentUser = Depends(),
) -> schemas.PaneOut:
    """Conclui a pane. Preenche data_conclusao automaticamente (RN-04)."""
    # TODO (Dia 4): return await service.concluir_pane(db, pane_id, usuario_atual.id)
    raise NotImplementedError


@router.post(
    "/{pane_id}/anexos",
    response_model=schemas.AnexoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de anexo (RF-11)",
)
async def upload_anexo(
    pane_id: uuid.UUID,
    arquivo: Annotated[UploadFile, File(description="Imagem (jpg/png) ou documento")],
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.AnexoOut:
    """Faz upload de imagem ou documento vinculado à pane."""
    # TODO (Dia 4):
    # conteudo = await arquivo.read()
    # return await service.upload_anexo(db, pane_id, conteudo, arquivo.filename, arquivo.content_type)
    raise NotImplementedError


@router.get(
    "/{pane_id}/anexos",
    response_model=list[schemas.AnexoOut],
    summary="Listar anexos da pane",
)
async def listar_anexos(
    pane_id: uuid.UUID,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> list[schemas.AnexoOut]:
    # TODO (Dia 4)
    raise NotImplementedError


@router.post(
    "/{pane_id}/responsaveis",
    response_model=schemas.ResponsavelOut,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar responsável à pane",
)
async def adicionar_responsavel(
    pane_id: uuid.UUID,
    dados: schemas.AdicionarResponsavel,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.ResponsavelOut:
    # TODO (Dia 4)
    raise NotImplementedError
