"""
app/panes/router.py
Endpoints de gestão de panes aeronáuticas.
"""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, File, UploadFile, Query, status
from fastapi.responses import FileResponse, RedirectResponse

from app.modules.panes import schemas, service
from app.bootstrap.dependencies import DBSession, CurrentUser, ensure_role

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
    texto: str | None = Query(default=None),
    status: schemas.StatusPane | None = Query(default=None),
    aeronave_id: uuid.UUID | None = Query(default=None),
    data_inicio: datetime | None = Query(default=None),
    data_fim: datetime | None = Query(default=None),
    excluidas: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[schemas.PaneListItem]:
    """Lista panes com filtros opcionais (texto, status, aeronave, data) e paginação."""
    filtros = schemas.FiltroPane(
        texto=texto,
        status=status,
        aeronave_id=aeronave_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        excluidas=excluidas,
        skip=skip,
        limit=limit,
    )
    panes = await service.listar_panes(db, filtros)
    resposta: list[schemas.PaneListItem] = []
    for pane, sequencia, ano in panes:
        item = schemas.PaneListItem.model_validate(pane).model_dump()
        item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
        resposta.append(schemas.PaneListItem(**item))
    return resposta


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
    resultado = await service.buscar_pane(db, pane_id)
    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pane não encontrada.",
        )
    
    pane, sequencia, ano = resultado
    item = schemas.PaneOut.model_validate(pane).model_dump()
    item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
    return schemas.PaneOut(**item)


@router.put(
    "/{pane_id}",
    response_model=schemas.PaneOut,
    summary="Editar pane (RF-10, RF-11)",
)
async def editar_pane(
    pane_id: uuid.UUID,
    dados: schemas.PaneUpdate,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> schemas.PaneOut:
    """Edita descrição e/ou status. RN-03: apenas panes não resolvidas."""
    if dados.descricao is not None or dados.sistema_subsistema is not None:
        ensure_role(usuario_atual, "ENCARREGADO", "ADMINISTRADOR")
    try:
        await service.editar_pane(db, pane_id, dados, usuario_atual.id)
        # Recarregar com ranking para devolver o código correto
        resultado = await service.buscar_pane(db, pane_id)
        if not resultado:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pane não encontrada.")
        
        pane, sequencia, ano = resultado
        item = schemas.PaneOut.model_validate(pane).model_dump()
        item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
        return schemas.PaneOut(**item)
    except ValueError as e:
        detail_str = str(e)
        if "não encontrada" in detail_str:
            status_code = status.HTTP_404_NOT_FOUND
        elif "abertas" in detail_str or "resolvida" in detail_str or "Transição" in detail_str:
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
        await service.concluir_pane(
            db, pane_id, usuario_atual.id, dados.observacao_conclusao
        )
        # Recarregar para pegar o ranking/código
        resultado = await service.buscar_pane(db, pane_id)
        if not resultado:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pane não encontrada.")
        
        pane, sequencia, ano = resultado
        item = schemas.PaneOut.model_validate(pane).model_dump()
        item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
        return schemas.PaneOut(**item)
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
    from app.shared.core.file_validators import validate_file_upload
    await validate_file_upload(arquivo)
    
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
    usuario_atual: CurrentUser,
) -> list[schemas.AnexoOut]:
    anexos = await service.listar_anexos(db, pane_id)
    return [schemas.AnexoOut.model_validate(a) for a in anexos]


@router.delete(
    "/{pane_id}/anexos/{anexo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover anexo da pane",
)
async def excluir_anexo(
    pane_id: uuid.UUID,
    anexo_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> None:
    """Remove o anexo (banco e arquivo físico). Restrito a Encarregados/Admins."""
    ensure_role(usuario_atual, "ENCARREGADO", "ADMINISTRADOR")
    try:
        await service.excluir_anexo(db, pane_id, anexo_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{pane_id}/anexos/{anexo_id}/download",
    summary="Baixar anexo autenticado",
)
async def baixar_anexo(
    pane_id: uuid.UUID,
    anexo_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,
):
    """Entrega o anexo apenas dentro do fluxo autenticado do sistema."""
    anexo = await service.buscar_anexo(db, pane_id, anexo_id)
    if not anexo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anexo não encontrado.",
        )
    try:
        url_or_path = await service.obter_url_anexo(anexo.caminho_arquivo)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        return RedirectResponse(url_or_path)

    caminho = Path(url_or_path)
    if not caminho.exists() or not caminho.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo físico do anexo não encontrado.",
        )
    media_type = "application/pdf" if caminho.suffix.lower() == ".pdf" else None
    return FileResponse(
        path=caminho,
        filename=caminho.name,
        media_type=media_type,
    )


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
    usuario_atual: CurrentUser,
) -> schemas.ResponsavelOut:
    # GESTORES podem atribuir qualquer um. MANTENEDORES podem atribuir apenas a si mesmos.
    if usuario_atual.funcao not in ["ENCARREGADO", "ADMINISTRADOR"]:
        if usuario_atual.id != dados.usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso restrito: você só pode assumir responsabilidades para si mesmo.",
            )
    
    try:
        resp = await service.adicionar_responsavel(db, pane_id, dados)
        return schemas.ResponsavelOut.model_validate(resp)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.delete(
    "/{pane_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete de pane",
    description="Marca a pane como inativa na base.",
)
async def deletar_pane(
    pane_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> None:
    ensure_role(usuario_atual, "ENCARREGADO", "ADMINISTRADOR")
    try:
        await service.excluir_pane(db, pane_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{pane_id}/restaurar",
    response_model=schemas.PaneOut,
    summary="Restaurar pane excluída",
)
async def restaurar_pane(
    pane_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> schemas.PaneOut:
    """Reativa uma pane que foi removida logicamente."""
    ensure_role(usuario_atual, "ENCARREGADO", "ADMINISTRADOR")
    try:
        await service.restaurar_pane(db, pane_id)
        # Recarregar para ranking
        resultado = await service.buscar_pane(db, pane_id)
        if not resultado:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pane não encontrada.")
        
        pane, sequencia, ano = resultado
        item = schemas.PaneOut.model_validate(pane).model_dump()
        item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
        return schemas.PaneOut(**item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
