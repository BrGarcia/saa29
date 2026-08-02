"""
app/equipamentos/router.py
Endpoints de gestão de equipamentos, itens e inventário.
"""

import uuid

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Query
from fastapi.responses import Response

from app.modules.equipamentos import schemas, service
from app.bootstrap.dependencies import DBSession, CurrentUser, EncarregadoOuAdmin, AdminRequired, ExecucaoPermitida
from app.shared.exporter import gerar_csv, gerar_xlsx

router = APIRouter()

# Os services levantam exceções de domínio (app.shared.core.exceptions), que já
# carregam o status HTTP e são convertidas pelo handler global — por isso os
# endpoints abaixo não têm try/except de tradução de erro.


# ---- Equipamentos (Tipos / Part Numbers) ----

@router.get("/", response_model=list[schemas.ModeloEquipamentoOut], summary="Listar equipamentos")
async def listar_equipamentos(
    db: DBSession,
    _: CurrentUser,
    limit: int | None = Query(None, ge=1, le=service.LIMITE_MAXIMO_LISTAGEM),
    offset: int = Query(0, ge=0),
):
    """Lista o catálogo de PNs. Sem `limit`, retorna o catálogo completo."""
    equipamentos = await service.listar_modelos(db, limit=limit, offset=offset)
    return [schemas.ModeloEquipamentoOut.model_validate(e) for e in equipamentos]


@router.post(
    "/",
    response_model=schemas.ModeloEquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar equipamento",
)
async def criar_equipamento(
    dados: schemas.ModeloEquipamentoCreate,
    db: DBSession,
    _: AdminRequired,
):
    equipamento = await service.criar_modelo(db, dados)
    return schemas.ModeloEquipamentoOut.model_validate(equipamento)


@router.get("/{equipamento_id}", response_model=schemas.ModeloEquipamentoOut)
async def buscar_equipamento(
    equipamento_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
):
    equipamento = await service.buscar_modelo(db, equipamento_id)
    return schemas.ModeloEquipamentoOut.model_validate(equipamento)


@router.patch("/{equipamento_id}", response_model=schemas.ModeloEquipamentoOut, summary="Atualizar equipamento")
async def atualizar_equipamento(
    equipamento_id: uuid.UUID,
    dados: schemas.ModeloEquipamentoUpdate,
    db: DBSession,
    _: AdminRequired,
):
    equipamento = await service.atualizar_modelo(db, equipamento_id, dados)
    return schemas.ModeloEquipamentoOut.model_validate(equipamento)


@router.delete("/{equipamento_id}", summary="Excluir equipamento")
async def remover_equipamento(
    equipamento_id: uuid.UUID,
    db: DBSession,
    _: AdminRequired,
):
    await service.remover_modelo(db, equipamento_id)
    return {"success": True, "message": "Equipamento removido com sucesso."}


# ---- Slots de Inventário (Posições na ANV) ----

@router.get(
    "/slots/",
    response_model=list[schemas.SlotInventarioOut],
    summary="Listar todos os slots configurados",
)
async def listar_slots(db: DBSession, _: CurrentUser):
    from app.modules.equipamentos.models import SlotInventario
    from sqlalchemy import select
    result = await db.execute(select(SlotInventario))
    return [schemas.SlotInventarioOut.model_validate(s) for s in result.scalars().all()]


@router.post(
    "/slots/",
    response_model=schemas.SlotInventarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Configurar novo slot/posição",
)
async def criar_slot(
    dados: schemas.SlotInventarioCreate,
    db: DBSession,
    _: AdminRequired,
):
    try:
        slot = await service.criar_slot(db, dados)
        # O commit é feito automaticamente pela dependência get_db ao final do request
        return schemas.SlotInventarioOut.model_validate(slot)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---- Itens (Serial Number) ----

@router.get("/itens/", response_model=list[schemas.ItemEquipamentoOut], summary="Listar itens")
async def listar_itens(
    db: DBSession,
    _: CurrentUser,
    equipamento_id: uuid.UUID | None = None,
    limit: int | None = Query(None, ge=1, le=service.LIMITE_MAXIMO_LISTAGEM),
    offset: int = Query(0, ge=0),
):
    """Lista itens físicos (S/N). Sem `limit`, retorna todos os itens do filtro."""
    itens = await service.listar_itens(db, equipamento_id, limit=limit, offset=offset)
    return [schemas.ItemEquipamentoOut.model_validate(i) for i in itens]


@router.post(
    "/itens/",
    response_model=schemas.ItemEquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar item (herda controles do equipamento)",
)
async def criar_item(
    dados: schemas.ItemEquipamentoCreate,
    db: DBSession,
    _: AdminRequired,
):
    item = await service.criar_item_com_heranca(db, dados)
    return schemas.ItemEquipamentoOut.model_validate(item)


# ---- Instalações ----

@router.post(
    "/itens/{item_id}/instalar",
    response_model=schemas.InstalacaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Instalar item em aeronave",
)
async def instalar_item(
    item_id: uuid.UUID,
    dados: schemas.InstalacaoCreate,
    db: DBSession,
    current_user: ExecucaoPermitida,
):
    instalacao = await service.instalar_item(
        db, item_id, dados.aeronave_id, dados.slot_id, dados.data_instalacao, current_user.id
    )
    return schemas.InstalacaoOut.model_validate(instalacao)


@router.patch(
    "/instalacoes/{instalacao_id}/remover",
    response_model=schemas.InstalacaoOut,
    summary="Registrar remoção de item",
)
async def remover_item(
    instalacao_id: uuid.UUID,
    dados: schemas.InstalacaoRemocao,
    db: DBSession,
    current_user: ExecucaoPermitida,
):
    instalacao = await service.remover_item(
        db, instalacao_id, dados.data_remocao, usuario_id=current_user.id
    )
    return schemas.InstalacaoOut.model_validate(instalacao)


# ---- Inventário ----

@router.get(
    "/inventario/historico",
    response_model=list[schemas.InventarioHistoricoOut],
    summary="Listar últimas alterações no inventário",
)
async def listar_historico_inventario(
    db: DBSession, 
    _: CurrentUser,
    limit: int = 15,
    offset: int = 0
):
    """Retorna as últimas movimentações de equipamentos com paginação."""
    return await service.listar_historico_recente(db, limit=limit, offset=offset)


# IMPORTANTE: rotas literais devem vir ANTES de /inventario/{aeronave_id},
# senão "export" é interpretado como aeronave_id e a requisição falha com 422.
@router.get(
    "/inventario/export",
    summary="Exportar relatório de inventário de aeronave (CSV/XLSX)",
)
async def exportar_inventario(
    db: DBSession,
    _: CurrentUser,
    aeronave_id: uuid.UUID,
    fmt: str = Query("csv", alias="format", pattern="^(csv|xlsx)$"),
):
    """Exporta o inventário da aeronave especificada em CSV ou XLSX."""
    inventario = await service.listar_inventario_aeronave(db, aeronave_id)
    headers = ["Slot", "Part Number (PN)", "Nome Equipamento", "Número de Série (SN)", "Status Slot"]
    rows = [
        [
            item.nome_posicao,
            item.part_number,
            item.nome_generico,
            item.numero_serie or "",
            item.status_item.value if item.status_item else "VAZIO",
        ]
        for item in inventario
    ]

    if fmt == "xlsx":
        content = gerar_xlsx("Inventario", headers, rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="inventario_aeronave.xlsx"'}
        )
    else:
        content_str = gerar_csv(headers, rows)
        return Response(
            content=content_str.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="inventario_aeronave.csv"'}
        )


@router.get(
    "/inventario/{aeronave_id}",
    response_model=list[schemas.InventarioItemOut],
    summary="Listar inventário da aeronave",
)
async def listar_inventario(
    aeronave_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
    nome: str | None = None,
):
    """Retorna inventário de itens instalados na aeronave.
    Aceita filtro opcional por nome de equipamento (?nome=...).
    """
    return await service.listar_inventario_aeronave(db, aeronave_id, nome=nome)


@router.post(
    "/inventario/ajuste",
    response_model=schemas.AjusteInventarioResponse,
    summary="Ajustar (sincronizar) S/N de uma aeronave/equipamento",
)
async def ajustar_inventario(
    dados: schemas.AjusteInventarioCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    """
    Ajusta o número de série físico de um equipamento.
    Lida com transferências e criação de novos itens.
    """
    from sqlalchemy.exc import IntegrityError
    try:
        return await service.ajustar_inventario_item(db, dados)
    except IntegrityError as e:
        if "FOREIGN KEY constraint failed" in str(e):
            return schemas.AjusteInventarioResponse(
                sucesso=False, 
                mensagem="Erro de integridade: Usuário ou Aeronave não encontrados. Tente fazer logoff e login novamente."
            )
        raise e


@router.post(
    "/inventario/upload-xlsx/preview",
    response_model=schemas.XlsxPreviewOut,
    summary="Obter prévia do inventário via XLSX",
)
async def upload_inventario_xlsx_preview(
    db: DBSession,
    _: EncarregadoOuAdmin,
    file: UploadFile = File(...),
):
    """
    Recebe um arquivo XLSX, cruza os PNs com o catálogo e retorna 
    uma prévia das alterações sem persistir.
    """
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo deve ser do tipo .xlsx"
        )

    content = await file.read()
    from app.modules.equipamentos.xlsx_service import obter_previa_xlsx_inventario
    return await obter_previa_xlsx_inventario(db, content, file.filename)


@router.post(
    "/inventario/upload-xlsx/process",
    summary="Processar e persistir inventário via XLSX",
)
async def upload_inventario_xlsx_process(
    dados: schemas.XlsxProcessRequest,
    db: DBSession,
    current_user: EncarregadoOuAdmin,
):
    """
    Recebe a lista confirmada de itens e persiste no banco de dados.
    """
    from app.modules.equipamentos.xlsx_service import processar_confirmacao_xlsx
    resultado = await processar_confirmacao_xlsx(
        db, dados.aeronave_id, dados.itens, current_user.id
    )

    return {
        "sucesso": len(resultado.erros) == 0,
        "total_linhas": resultado.total_linhas,
        "itens_atualizados": resultado.itens_atualizados,
        "erros": resultado.erros,
        "detalhes": resultado.detalhes,
    }


@router.post(
    "/inventario/upload-xlsx",
    summary="Carregar inventário via XLSX (Legado/Direto)",
)
async def upload_inventario_xlsx(
    db: DBSession,
    current_user: EncarregadoOuAdmin,
    file: UploadFile = File(...),
):
    """
    Recebe um arquivo XLSX nomeado como MATRICULA.xlsx,
    cruza os PNs com o catálogo e atualiza os seriais da aeronave.
    """
    # Validar extensão
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo deve ser do tipo .xlsx"
        )

    # Validar tamanho (máximo 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo excede o tamanho máximo de 5MB."
        )

    from app.modules.equipamentos.xlsx_service import processar_xlsx_inventario
    resultado = await processar_xlsx_inventario(
        db, content, file.filename, current_user.id
    )

    return {
        "sucesso": len(resultado.erros) == 0,
        "matricula": resultado.matricula,
        "total_linhas": resultado.total_linhas,
        "pns_encontrados": resultado.pns_encontrados,
        "pns_ignorados": resultado.pns_ignorados,
        "itens_atualizados": resultado.itens_atualizados,
        "erros": resultado.erros,
        "detalhes": resultado.detalhes,
    }

