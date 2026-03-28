"""
app/panes/router.py
Endpoints de gestão de panes aeronáuticas.
"""

import uuid

from fastapi import APIRouter, HTTPException, File, UploadFile, Query, status

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
    db: DBSession,
    usuario_atual: CurrentUser,
) -> schemas.PaneOut:
    """Abre uma nova pane vinculada a uma aeronave. Status inicial = ABERTA."""
    try:
        pane = await service.criar_pane(db, dados, usuario_atual.id)
        return schemas.PaneOut.model_validate(pane)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/",
    response_model=list[schemas.PaneListItem],
    summary="Listar panes (RF-03, RF-06)",
)
async def listar_panes(
    db: DBSession,
    _: CurrentUser,
    texto: str | None = Query(default=None, description="Filtro por texto"),
    status_pane: schemas.StatusPane | None = Query(default=None, alias="status"),
    aeronave_id: uuid.UUID | None = Query(default=None),
) -> list[schemas.PaneListItem]:
    """Lista panes com filtros opcionais (texto, status, aeronave, data)."""
    filtros = schemas.FiltroPane(
        texto=texto,
        status=status_pane,
        aeronave_id=aeronave_id,
    )
    panes = await service.listar_panes(db, filtros)
    return [schemas.PaneListItem.model_validate(p) for p in panes]


@router.get(
    "/{pane_id}",
    response_model=schemas.PaneOut,
    summary="Detalhar pane (RF-09)",
)
async def buscar_pane(
    pane_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> schemas.PaneOut:
    """Retorna dados completos da pane com anexos e responsáveis."""
    pane = await service.buscar_pane(db, pane_id)
    if not pane:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pane não encontrada.",
        )
    return schemas.PaneOut.model_validate(pane)


@router.put(
    "/{pane_id}",
    response_model=schemas.PaneOut,
    summary="Editar pane (RF-10, RF-11)",
)
async def editar_pane(
    pane_id: uuid.UUID,
    dados: schemas.PaneUpdate,
    db: DBSession,
    _: CurrentUser,
) -> schemas.PaneOut:
    """Edita descrição e/ou status. RN-03: apenas panes não resolvidas."""
    try:
        pane = await service.editar_pane(db, pane_id, dados)
        return schemas.PaneOut.model_validate(pane)
    except ValueError as e:
        detail_str = str(e)
        if "não encontrada" in detail_str:
            status_code = status.HTTP_404_NOT_FOUND
        elif "resolvida" in detail_str or "Transição" in detail_str:
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail_str)


@router.post(
    "/{pane_id}/concluir",
    response_model=schemas.PaneOut,
    summary="Concluir pane (RF-12, RF-13)",
)
async def concluir_pane(
    pane_id: uuid.UUID,
    dados: schemas.PaneConcluir,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> schemas.PaneOut:
    """Conclui a pane. Preenche data_conclusao automaticamente (RN-04)."""
    try:
        pane = await service.concluir_pane(db, pane_id, usuario_atual.id)
        return schemas.PaneOut.model_validate(pane)
    except ValueError as e:
        detail_str = str(e)
        if "não encontrada" in detail_str:
            status_code = status.HTTP_404_NOT_FOUND
        elif "resolvida" in detail_str:
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail_str)


@router.post(
    "/{pane_id}/anexos",
    response_model=schemas.AnexoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de anexo (RF-11)",
)
async def upload_anexo(
    pane_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
    arquivo: UploadFile = File(description="Imagem (jpg/png) ou documento"),
) -> schemas.AnexoOut:
    """Faz upload de imagem ou documento vinculado à pane."""
    conteudo = await arquivo.read()
    filename = arquivo.filename or "unknown"
    content_type = arquivo.content_type or "application/octet-stream"
    try:
        anexo = await service.upload_anexo(
            db, pane_id, conteudo, filename, content_type
        )
        return schemas.AnexoOut.model_validate(anexo)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get(
    "/{pane_id}/anexos",
    response_model=list[schemas.AnexoOut],
    summary="Listar anexos da pane",
)
async def listar_anexos(
    pane_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> list[schemas.AnexoOut]:
    anexos = await service.listar_anexos(db, pane_id)
    return [schemas.AnexoOut.model_validate(a) for a in anexos]


@router.post(
    "/{pane_id}/responsaveis",
    response_model=schemas.ResponsavelOut,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar responsável à pane",
)
async def adicionar_responsavel(
    pane_id: uuid.UUID,
    dados: schemas.AdicionarResponsavel,
    db: DBSession,
    _: CurrentUser,
) -> schemas.ResponsavelOut:
    try:
        resp = await service.adicionar_responsavel(db, pane_id, dados)
        return schemas.ResponsavelOut.model_validate(resp)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
