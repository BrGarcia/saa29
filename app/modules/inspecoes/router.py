"""
Endpoints do modulo isolado de inspecoes.

Ordem das rotas: SEMPRE defina rotas estaticas antes de rotas dinamicas
(ex: /tarefas-catalogo antes de /{inspecao_id}) para evitar que o FastAPI
capture segmentos fixos como UUIDs invalidos (HTTP 422).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.bootstrap.dependencies import CurrentUser, DBSession, EncarregadoOuAdmin, AdminRequired, ExecucaoPermitida, EncarregadoInspetorOuAdmin
from app.modules.inspecoes import schemas, service, pdf_service
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusInspecao
from app.shared.exporter import gerar_csv, gerar_xlsx

router = APIRouter()


@router.get(
    "/tipos",
    response_model=list[schemas.TipoInspecaoOut],
    summary="Listar tipos de inspecao",
)
async def listar_tipos_inspecao(
    db: DBSession,
    _: CurrentUser,
    incluir_inativos: bool = Query(default=False),
) -> list[schemas.TipoInspecaoOut]:
    tipos = await service.listar_tipos_inspecao(db, incluir_inativos=incluir_inativos)
    return [schemas.TipoInspecaoOut.model_validate(tipo) for tipo in tipos]


@router.post(
    "/tipos",
    response_model=schemas.TipoInspecaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tipo de inspecao",
)
async def criar_tipo_inspecao(
    dados: schemas.TipoInspecaoCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> schemas.TipoInspecaoOut:
    tipo = await service.criar_tipo_inspecao(db, dados)
    return schemas.TipoInspecaoOut.model_validate(tipo)


@router.put(
    "/tipos/{tipo_id}",
    response_model=schemas.TipoInspecaoOut,
    summary="Atualizar tipo de inspecao",
)
@router.patch(
    "/tipos/{tipo_id}",
    response_model=schemas.TipoInspecaoOut,
    summary="Atualizar tipo de inspecao (parcial)",
)
async def atualizar_tipo_inspecao(
    tipo_id: uuid.UUID,
    dados: schemas.TipoInspecaoUpdate,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> schemas.TipoInspecaoOut:
    tipo = await service.atualizar_tipo_inspecao(db, tipo_id, dados)
    return schemas.TipoInspecaoOut.model_validate(tipo)


@router.delete(
    "/tipos/{tipo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Desativar tipo de inspecao",
)
async def desativar_tipo_inspecao(
    tipo_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> None:
    await service.desativar_tipo_inspecao(db, tipo_id)


@router.get(
    "/tarefas-catalogo",
    response_model=list[schemas.TarefaCatalogoOut],
    summary="Listar tarefas do catalogo",
)
async def listar_tarefas_catalogo(
    db: DBSession,
    _: CurrentUser,
    incluir_inativos: bool = Query(default=False),
) -> list[schemas.TarefaCatalogoOut]:
    tarefas = await service.listar_tarefas_catalogo(db, incluir_inativos=incluir_inativos)
    return [schemas.TarefaCatalogoOut.model_validate(tarefa) for tarefa in tarefas]


@router.post(
    "/tarefas-catalogo",
    response_model=schemas.TarefaCatalogoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tarefa no catalogo",
)
async def criar_tarefa_catalogo(
    dados: schemas.TarefaCatalogoCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> schemas.TarefaCatalogoOut:
    tarefa = await service.criar_tarefa_catalogo(db, dados)
    return schemas.TarefaCatalogoOut.model_validate(tarefa)


@router.put(
    "/tarefas-catalogo/{tarefa_id}",
    response_model=schemas.TarefaCatalogoOut,
    summary="Atualizar tarefa no catalogo",
)
async def atualizar_tarefa_catalogo(
    tarefa_id: uuid.UUID,
    dados: schemas.TarefaCatalogoUpdate,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> schemas.TarefaCatalogoOut:
    tarefa = await service.atualizar_tarefa_catalogo(db, tarefa_id, dados)
    return schemas.TarefaCatalogoOut.model_validate(tarefa)


@router.delete(
    "/tarefas-catalogo/{tarefa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Desativar tarefa no catalogo",
)
async def desativar_tarefa_catalogo(
    tarefa_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> None:
    await service.desativar_tarefa_catalogo(db, tarefa_id)


@router.get(
    "/tipos/{tipo_id}/tarefas",
    response_model=list[schemas.TarefaTemplateOut],
    summary="Listar tarefas template de um tipo",
)
async def listar_tarefas_template(
    tipo_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> list[schemas.TarefaTemplateOut]:
    tarefas = await service.listar_tarefas_template(db, tipo_id)
    return [schemas.TarefaTemplateOut.model_validate(tarefa) for tarefa in tarefas]


@router.post(
    "/tipos/{tipo_id}/tarefas",
    response_model=schemas.TarefaTemplateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar tarefa template",
)
async def criar_tarefa_template(
    tipo_id: uuid.UUID,
    dados: schemas.TarefaTemplateCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> schemas.TarefaTemplateOut:
    tarefa = await service.criar_tarefa_template(db, tipo_id, dados)
    return schemas.TarefaTemplateOut.model_validate(tarefa)


@router.put(
    "/tarefas-template/{tarefa_id}",
    response_model=schemas.TarefaTemplateOut,
    summary="Atualizar tarefa template",
)
async def atualizar_tarefa_template(
    tarefa_id: uuid.UUID,
    dados: schemas.TarefaTemplateUpdate,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> schemas.TarefaTemplateOut:
    tarefa = await service.atualizar_tarefa_template(db, tarefa_id, dados)
    return schemas.TarefaTemplateOut.model_validate(tarefa)


@router.delete(
    "/tarefas-template/{tarefa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Remover tarefa template",
)
async def remover_tarefa_template(
    tarefa_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> None:
    await service.remover_tarefa_template(db, tarefa_id)


@router.patch(
    "/tipos/{tipo_id}/tarefas/reordenar",
    response_model=list[schemas.TarefaTemplateOut],
    summary="Reordenar tarefas template",
)
async def reordenar_tarefas_template(
    tipo_id: uuid.UUID,
    dados: schemas.ReordenarTarefas,
    db: DBSession,
    _: EncarregadoOuAdmin,
) -> list[schemas.TarefaTemplateOut]:
    tarefas = await service.reordenar_tarefas_template(db, tipo_id, dados)
    return [schemas.TarefaTemplateOut.model_validate(tarefa) for tarefa in tarefas]


# ---------------------------------------------------------------------------
# Rotas de inspeção — PUT /tarefas/{tarefa_id} definido ANTES de /{inspecao_id}
# para evitar conflito de captura pelo segmento dinâmico.
# ---------------------------------------------------------------------------

@router.put(
    "/tarefas/{tarefa_id}",
    response_model=schemas.InspecaoTarefaOut,
    summary="Atualizar tarefa de inspecao",
)
async def atualizar_tarefa_inspecao(
    tarefa_id: uuid.UUID,
    dados: schemas.InspecaoTarefaUpdate,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> schemas.InspecaoTarefaOut:
    tarefa = await service.atualizar_tarefa_inspecao(
        db,
        tarefa_id,
        dados,
        usuario_padrao_id=usuario_atual.id,
    )
    return schemas.InspecaoTarefaOut.model_validate(tarefa)


@router.get(
    "/",
    response_model=list[schemas.InspecaoListItem],
    summary="Listar inspecoes",
)
async def listar_inspecoes(
    db: DBSession,
    _: CurrentUser,
    aeronave_id: uuid.UUID | None = Query(default=None),
    tipo_inspecao_id: uuid.UUID | None = Query(default=None),
    status_inspecao: StatusInspecao | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[schemas.InspecaoListItem]:
    filtros = schemas.FiltroInspecao(
        aeronave_id=aeronave_id,
        tipo_inspecao_id=tipo_inspecao_id,
        status=status_inspecao,
        skip=skip,
        limit=limit,
    )
    inspecoes = await service.listar_inspecoes(db, filtros)
    resposta: list[schemas.InspecaoListItem] = []
    for inspecao in inspecoes:
        total, concluidas, percentual = service.calcular_progresso(inspecao)
        item = schemas.InspecaoListItem.model_validate(inspecao).model_dump()
        item["total_tarefas"] = total
        item["tarefas_concluidas"] = concluidas
        item["progresso_percentual"] = percentual
        resposta.append(schemas.InspecaoListItem(**item))
    return resposta


@router.get(
    "/export",
    summary="Exportar relatorio de inspecoes (CSV/XLSX)",
)
async def exportar_inspecoes(
    db: DBSession,
    _: CurrentUser,
    fmt: str = Query("csv", alias="format", pattern="^(csv|xlsx)$"),
    aeronave_id: uuid.UUID | None = Query(default=None),
    status_inspecao: StatusInspecao | None = Query(default=None, alias="status"),
):
    """Exporta lista de inspecoes em CSV ou XLSX."""
    filtros = schemas.FiltroInspecao(
        aeronave_id=aeronave_id,
        status=status_inspecao,
        skip=0,
        limit=1000,
    )
    inspecoes = await service.listar_inspecoes(db, filtros)
    headers = ["Aeronave", "Tipo Inspeção", "Status", "Data Início", "Data Prevista (DPE)", "Progresso %"]
    rows = []
    for insp in inspecoes:
        total, concluidas, percentual = service.calcular_progresso(insp)
        anv = insp.aeronave.matricula if insp.aeronave else ""
        tipo = insp.tipo_inspecao.nome if insp.tipo_inspecao else ""
        dt_ini = insp.data_inicio.strftime("%d/%m/%Y") if insp.data_inicio else ""
        dt_dpe = insp.dpe.strftime("%d/%m/%Y") if insp.dpe else ""
        rows.append([anv, tipo, insp.status.value if hasattr(insp.status, "value") else str(insp.status), dt_ini, dt_dpe, f"{percentual:.1f}%"])

    if fmt == "xlsx":
        content = gerar_xlsx("Inspecoes", headers, rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="relatorio_inspecoes.xlsx"'}
        )
    else:
        content_str = gerar_csv(headers, rows)
        return Response(
            content=content_str.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="relatorio_inspecoes.csv"'}
        )


@router.get(
    "/{inspecao_id}/pdf",
    summary="Gerar PDF da Ordem de Inspeção (OS)",
)
async def gerar_pdf_inspecao(
    inspecao_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
):
    """Gera o arquivo PDF formatado da Ordem de Inspeção com Checklist e Inventário Controlado."""
    try:
        pdf_bytes = await pdf_service.gerar_pdf_ordem_inspecao(db, inspecao_id)
        filename = f"OS_Inspecao_{str(inspecao_id)[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except (ValueError, domain_exc.EntidadeNaoEncontradaError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{inspecao_id}/checklist",
    summary="Gerar PDF do Checklist da Inspeção",
)
async def gerar_checklist_inspecao(
    inspecao_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
):
    """Gera o arquivo PDF formatado do Checklist de Delineamento da Inspeção."""
    try:
        pdf_bytes = await pdf_service.gerar_pdf_checklist_inspecao(db, inspecao_id)
        filename = f"Checklist_Inspecao_{str(inspecao_id)[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except (ValueError, domain_exc.EntidadeNaoEncontradaError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{inspecao_id}",
    response_model=schemas.InspecaoOut,
    summary="Detalhar inspecao",
)
async def buscar_inspecao(
    inspecao_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> schemas.InspecaoOut:
    inspecao = await service.buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspecao nao encontrada.")
    return schemas.InspecaoOut.model_validate(inspecao)


@router.post(
    "/",
    response_model=schemas.InspecaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir inspecao",
)
async def abrir_inspecao(
    dados: schemas.InspecaoCreate,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.InspecaoOut:
    inspecao = await service.abrir_inspecao(db, dados, usuario_atual.id)
    return schemas.InspecaoOut.model_validate(inspecao)


@router.put(
    "/{inspecao_id}",
    response_model=schemas.InspecaoOut,
    summary="Atualizar observacoes da inspecao",
)
async def atualizar_inspecao(
    inspecao_id: uuid.UUID,
    dados: schemas.InspecaoUpdate,
    db: DBSession,
    _: EncarregadoInspetorOuAdmin,
) -> schemas.InspecaoOut:
    inspecao = await service.atualizar_inspecao(db, inspecao_id, dados)
    return schemas.InspecaoOut.model_validate(inspecao)


@router.post(
    "/{inspecao_id}/concluir",
    response_model=schemas.InspecaoOut,
    summary="Concluir inspecao",
)
async def concluir_inspecao(
    inspecao_id: uuid.UUID,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.InspecaoOut:
    inspecao = await service.concluir_inspecao(db, inspecao_id, usuario_atual.id)
    return schemas.InspecaoOut.model_validate(inspecao)


@router.post(
    "/{inspecao_id}/cancelar",
    response_model=schemas.InspecaoOut,
    summary="Cancelar inspecao",
)
async def cancelar_inspecao(
    inspecao_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoInspetorOuAdmin,
) -> schemas.InspecaoOut:
    inspecao = await service.cancelar_inspecao(db, inspecao_id)
    return schemas.InspecaoOut.model_validate(inspecao)


@router.get(
    "/{inspecao_id}/tarefas",
    response_model=list[schemas.InspecaoTarefaOut],
    summary="Listar tarefas de uma inspecao",
)
async def listar_tarefas_inspecao(
    inspecao_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> list[schemas.InspecaoTarefaOut]:
    inspecao = await service.buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspecao nao encontrada.")
    return [schemas.InspecaoTarefaOut.model_validate(tarefa) for tarefa in inspecao.tarefas]


@router.post(
    "/{inspecao_id}/tarefas",
    response_model=schemas.InspecaoTarefaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar tarefa avulsa a inspecao",
)
async def adicionar_tarefa_avulsa(
    inspecao_id: uuid.UUID,
    dados: schemas.InspecaoTarefaCreate,
    db: DBSession,
    _: CurrentUser,
) -> schemas.InspecaoTarefaOut:
    tarefa = await service.adicionar_tarefa_avulsa(db, inspecao_id, dados)
    return schemas.InspecaoTarefaOut.model_validate(tarefa)
