"""
app/panes/router.py
Endpoints de gestão de panes aeronáuticas.
"""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, File, UploadFile, Query, status, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse, Response
from app.shared.exporter import gerar_csv, gerar_xlsx

from app.modules.panes import schemas, service
from app.bootstrap.dependencies import DBSession, CurrentUser, ensure_role, ExecucaoPermitida

router = APIRouter()


@router.get(
    "/sistemas",
    response_model=list[schemas.SistemaAtaOut],
    summary="Listar Sistemas ATA ativos",
)
async def listar_sistemas_ata(
    db: DBSession,
    _: CurrentUser,
) -> list[schemas.SistemaAtaOut]:
    """Retorna a lista de sistemas ATA para uso em formulários (Lookups)."""
    sistemas = await service.listar_sistemas_ata(db)
    return [schemas.SistemaAtaOut.model_validate(s) for s in sistemas]


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
        result = schemas.PaneOut.model_validate(pane)

        # Safety net: sincronizar status da aeronave via SQL direto.
        # Garante que a aeronave transite para INDISPONIVEL quando recebe
        # uma pane aberta, mesmo em cenários de cache de ORM.
        from sqlalchemy import update as sql_update
        from app.modules.aeronaves.models import Aeronave
        from app.shared.core.enums import StatusAeronave
        await db.execute(
            sql_update(Aeronave)
            .where(Aeronave.id == dados.aeronave_id)
            .where(Aeronave.status.in_([
                StatusAeronave.DISPONIVEL,
                StatusAeronave.OPERACIONAL,
            ]))
            .values(status=StatusAeronave.INDISPONIVEL)
        )

        return result
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
    "/export",
    summary="Exportar relatório de panes (CSV/XLSX)",
)
async def exportar_panes(
    db: DBSession,
    _: CurrentUser,
    fmt: str = Query("csv", alias="format", pattern="^(csv|xlsx)$"),
    status: schemas.StatusPane | None = None,
    aeronave_id: uuid.UUID | None = None,
):
    """Exporta relatórios de panes em formato CSV ou XLSX."""
    filtros = schemas.PaneFilter(status=status, aeronave_id=aeronave_id, skip=0, limit=1000)
    panes = await service.listar_panes(db, filtros)
    
    headers = ["Código", "Aeronave", "Status", "Descrição", "Data Abertura", "Data Conclusão"]
    rows = []
    for pane, sequencia, ano in panes:
        codigo = f"{sequencia:03d}/{str(ano)[-2:]}"
        anv = pane.aeronave.matricula if pane.aeronave else ""
        desc = pane.descricao or ""
        dt_ab = pane.data_abertura.strftime("%d/%m/%Y %H:%M") if pane.data_abertura else ""
        dt_con = pane.data_conclusao.strftime("%d/%m/%Y %H:%M") if pane.data_conclusao else ""
        rows.append([codigo, anv, pane.status, desc, dt_ab, dt_con])

    if fmt == "xlsx":
        content = gerar_xlsx("Panes", headers, rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="relatorio_panes.xlsx"'}
        )
    else:
        content_str = gerar_csv(headers, rows)
        return Response(
            content=content_str.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="relatorio_panes.csv"'}
        )


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
    resultado = await service.buscar_pane(db, pane_id, incluir_inativos=True)
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
    """Edita descrição e/ou status. RN-03: apenas panes não resolvidas.

    Item #24 (relatorio_panes_service.md): o service levanta exceções de
    domínio (`EntidadeNaoEncontradaError`/`ConflitoNegocioError`), que já
    carregam o status HTTP correto — sem string-matching de mensagem aqui.
    """
    if dados.descricao is not None or dados.sistema_ata_id is not None:
        ensure_role(usuario_atual, "ENCARREGADO", "INSPETOR", "ADMINISTRADOR")

    await service.editar_pane(db, pane_id, dados, usuario_atual.id)
    # Recarregar com ranking para devolver o código correto
    resultado = await service.buscar_pane(db, pane_id)
    if not resultado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pane não encontrada.")

    pane, sequencia, ano = resultado
    item = schemas.PaneOut.model_validate(pane).model_dump()
    item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
    return schemas.PaneOut(**item)


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
    # RN: MANTENEDOR, ENCARREGADO, INSPETOR e ADMIN podem concluir.
    ensure_role(usuario_atual, "MANTENEDOR", "ENCARREGADO", "INSPETOR", "ADMINISTRADOR")
    """Conclui a pane. Preenche data_conclusao automaticamente (RN-04).

    Item #24 (relatorio_panes_service.md): o service levanta exceções de
    domínio (`EntidadeNaoEncontradaError`/`ConflitoNegocioError`), que já
    carregam o status HTTP correto — sem string-matching de mensagem aqui.
    """
    # Buscar aeronave_id da pane antes de concluir
    pane_antes = await service.buscar_pane(db, pane_id)
    aeronave_id_pane = pane_antes[0].aeronave_id if pane_antes else None

    await service.concluir_pane(
        db, pane_id, usuario_atual.id, dados.observacao_conclusao
    )

    # Safety net: sincronizar status da aeronave via SQL direto apos conclusao.
    if aeronave_id_pane:
        from sqlalchemy import select as sql_select, update as sql_update, func
        from app.modules.panes.models import Pane
        from app.modules.aeronaves.models import Aeronave
        from app.shared.core.enums import StatusAeronave, StatusPane
        from app.modules.inspecoes.models import Inspecao
        from app.modules.inspecoes.service import STATUS_ATIVOS

        # Contar panes abertas restantes
        res = await db.execute(
            sql_select(func.count(Pane.id)).where(
                Pane.aeronave_id == aeronave_id_pane,
                Pane.status == StatusPane.ABERTA.value,
                Pane.ativo == True,
            )
        )
        panes_restantes = res.scalar() or 0

        # Contar inspecoes ativas
        res_insp = await db.execute(
            sql_select(func.count(Inspecao.id)).where(
                Inspecao.aeronave_id == aeronave_id_pane,
                Inspecao.status.in_(STATUS_ATIVOS),
            )
        )
        insp_ativas = res_insp.scalar() or 0

        if insp_ativas > 0:
            await db.execute(
                sql_update(Aeronave)
                .where(Aeronave.id == aeronave_id_pane)
                .values(status=StatusAeronave.INSPECAO)
            )
        elif panes_restantes == 0:
            await db.execute(
                sql_update(Aeronave)
                .where(Aeronave.id == aeronave_id_pane)
                .where(Aeronave.status == StatusAeronave.INDISPONIVEL)
                .values(status=StatusAeronave.DISPONIVEL)
            )

    # Recarregar para pegar o ranking/código
    resultado = await service.buscar_pane(db, pane_id)
    if not resultado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pane não encontrada.")

    pane, sequencia, ano = resultado
    item = schemas.PaneOut.model_validate(pane).model_dump()
    item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
    return schemas.PaneOut(**item)


@router.post(
    "/{pane_id}/anexos",
    response_model=schemas.AnexoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de anexo com processamento em background (RF-11)",
)
async def upload_anexo(
    pane_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(description="Imagem (jpg/png) ou documento"),
) -> schemas.AnexoOut:
    ensure_role(usuario_atual, "MANTENEDOR", "ENCARREGADO", "INSPETOR", "ADMINISTRADOR")
    from app.shared.core.file_validators import validate_file_upload
    await validate_file_upload(arquivo)
    
    conteudo = await arquivo.read()
    filename = arquivo.filename or "unknown"
    content_type = arquivo.content_type or "application/octet-stream"
    try:
        anexo, precisa_bg = await service.upload_anexo(
            db, pane_id, conteudo, filename, content_type, is_background=True
        )
        if precisa_bg:
            background_tasks.add_task(
                service.processar_imagem_background,
                anexo.id,
                conteudo,
                filename,
                content_type
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
    anexo = await service.buscar_anexo(db, pane_id, anexo_id, incluir_inativos=True)
    if not anexo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anexo não encontrado.",
        )

    if anexo.caminho_arquivo in ("processando", "ERRO"):
        status_detail = "Anexo ainda está sendo processado." if anexo.caminho_arquivo == "processando" else "Falha no processamento do anexo."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=status_detail)

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
    usuario_atual: ExecucaoPermitida,
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
