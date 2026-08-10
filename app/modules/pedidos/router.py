"""
app/modules/pedidos/router.py
Endpoints REST da Central de Pedidos.
"""

import uuid

from fastapi import APIRouter, Query, Request, Response, status

from app.bootstrap.dependencies import CurrentUser, DBSession, EncarregadoInspetorOuAdmin
from app.modules.pedidos import schemas, service
from app.shared.core import exceptions as domain_exc
from app.shared.core.limiter import limiter
from app.shared.exporter import gerar_csv, gerar_xlsx

router = APIRouter()


@router.get(
    "/",
    response_model=list[schemas.PedidoOut],
    summary="Listar pedidos",
)
async def listar_pedidos(
    db: DBSession,
    _: CurrentUser,
    response: Response,
    texto: str | None = Query(default=None),
    # `status_filtro` evita sombrear `fastapi.status`, importado neste
    # módulo para os `status.HTTP_*` usados abaixo (RISCO-11 de panes/router.py).
    status_filtro: schemas.StatusPedido | None = Query(default=None, alias="status"),
    tipo_pedido: schemas.TipoPedido | None = Query(default=None),
    aeronave_id: uuid.UUID | None = Query(default=None),
    excluidos: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[schemas.PedidoOut]:
    filtros = schemas.FiltroPedido(
        texto=texto,
        status=status_filtro,
        tipo_pedido=tipo_pedido,
        aeronave_id=aeronave_id,
        excluidos=excluidos,
        skip=skip,
        limit=limit,
    )
    pedidos, total = await service.listar_pedidos(db, filtros)
    response.headers["X-Total-Count"] = str(total)
    return [service._to_out(p) for p in pedidos]


@router.get(
    "/resumo",
    response_model=schemas.PedidoResumo,
    summary="Contadores de resumo (cards)",
)
async def obter_resumo(
    db: DBSession,
    _: CurrentUser,
    texto: str | None = Query(default=None),
    status_filtro: schemas.StatusPedido | None = Query(default=None, alias="status"),
    tipo_pedido: schemas.TipoPedido | None = Query(default=None),
    aeronave_id: uuid.UUID | None = Query(default=None),
    excluidos: bool = Query(default=False),
) -> schemas.PedidoResumo:
    filtros = schemas.FiltroPedido(
        texto=texto,
        status=status_filtro,
        tipo_pedido=tipo_pedido,
        aeronave_id=aeronave_id,
        excluidos=excluidos,
    )
    return await service.obter_resumo(db, filtros)


@router.get(
    "/export",
    summary="Exportar relatório de pedidos (CSV/XLSX)",
)
@limiter.limit("10/minute")
async def exportar_pedidos(
    request: Request,
    db: DBSession,
    _: CurrentUser,
    fmt: str = Query("csv", alias="format", pattern="^(csv|xlsx)$"),
    texto: str | None = Query(default=None),
    status_filtro: schemas.StatusPedido | None = Query(default=None, alias="status"),
    tipo_pedido: schemas.TipoPedido | None = Query(default=None),
    aeronave_id: uuid.UUID | None = Query(default=None),
):
    limit_export = 1000
    filtros = schemas.FiltroPedido(
        texto=texto,
        status=status_filtro,
        tipo_pedido=tipo_pedido,
        aeronave_id=aeronave_id,
        skip=0,
        limit=limit_export,
    )
    pedidos, total = await service.listar_pedidos(db, filtros)

    headers = [
        "Nº Pedido", "Aeronave", "Status", "Tipo", "Nº Emergência",
        "Part Number", "Nomenclatura", "Quantidade", "Data Pedido", "Data Atendimento",
    ]
    rows = []
    for p in pedidos:
        out = service._to_out(p)
        rows.append([
            out.numero_pedido,
            out.aeronave_matricula,
            out.status,
            out.tipo_pedido,
            out.numero_emergencia or "",
            out.part_number,
            out.nomenclatura,
            out.quantidade,
            out.data_pedido.strftime("%d/%m/%Y") if out.data_pedido else "",
            out.data_atendimento.strftime("%d/%m/%Y %H:%M") if out.data_atendimento else "",
        ])

    extra_headers = {}
    if total > limit_export:
        extra_headers["X-Export-Truncated"] = "true"

    if fmt == "xlsx":
        content = gerar_xlsx("Pedidos", headers, rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="relatorio_pedidos.xlsx"',
                **extra_headers,
            }
        )
    else:
        content_str = gerar_csv(headers, rows)
        return Response(
            content=content_str.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="relatorio_pedidos.csv"',
                **extra_headers,
            }
        )


@router.post(
    "/",
    response_model=schemas.PedidoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo pedido",
)
async def criar_pedido(
    dados: schemas.PedidoCreate,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.PedidoOut:
    pedido = await service.criar_pedido(db, dados, usuario_atual.id)
    return service._to_out(pedido)


@router.get(
    "/{pedido_id}",
    response_model=schemas.PedidoOut,
    summary="Detalhar pedido",
)
async def buscar_pedido(
    pedido_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> schemas.PedidoOut:
    pedido = await service.buscar_pedido(db, pedido_id, incluir_inativos=True)
    if not pedido:
        raise domain_exc.EntidadeNaoEncontradaError("Pedido não encontrado.")
    return service._to_out(pedido)


@router.put(
    "/{pedido_id}",
    response_model=schemas.PedidoOut,
    summary="Editar pedido (somente PENDENTE)",
)
async def editar_pedido(
    pedido_id: uuid.UUID,
    dados: schemas.PedidoUpdate,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.PedidoOut:
    pedido = await service.editar_pedido(db, pedido_id, dados)
    return service._to_out(pedido)


@router.post(
    "/{pedido_id}/atender",
    response_model=schemas.PedidoOut,
    summary="Marcar pedido como ATENDIDO",
)
async def atender_pedido(
    pedido_id: uuid.UUID,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.PedidoOut:
    pedido = await service.atender_pedido(db, pedido_id, usuario_atual.id)
    return service._to_out(pedido)


@router.post(
    "/{pedido_id}/cancelar",
    response_model=schemas.PedidoOut,
    summary="Marcar pedido como CANCELADO",
)
async def cancelar_pedido(
    pedido_id: uuid.UUID,
    dados: schemas.PedidoCancelar,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.PedidoOut:
    pedido = await service.cancelar_pedido(db, pedido_id, usuario_atual.id, dados)
    return service._to_out(pedido)


@router.delete(
    "/{pedido_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete de pedido",
)
async def deletar_pedido(
    pedido_id: uuid.UUID,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> None:
    await service.excluir_pedido(db, pedido_id)


@router.post(
    "/{pedido_id}/restaurar",
    response_model=schemas.PedidoOut,
    summary="Restaurar pedido excluído",
)
async def restaurar_pedido(
    pedido_id: uuid.UUID,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.PedidoOut:
    pedido = await service.restaurar_pedido(db, pedido_id)
    return service._to_out(pedido)
