"""
app/modules/pedidos/service.py
Camada de serviço da Central de Pedidos — regras de negócio do ciclo de
vida administrativo/logístico (feature_controle_pedidos.md v2.0, §4).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.aeronaves.models import Aeronave
from app.modules.aeronaves.service import buscar_aeronave
from app.modules.pedidos.models import Pedido
from app.modules.pedidos.schemas import (
    FiltroPedido,
    PedidoCancelar,
    PedidoCreate,
    PedidoOut,
    PedidoResumo,
    PedidoUpdate,
)
from app.shared.core import exceptions as domain_exc
from app.shared.core.db_utils import escape_like
from app.shared.core.enums import StatusPedido, TipoPedido

_RELACOES_EAGER = (
    selectinload(Pedido.aeronave),
    selectinload(Pedido.solicitante),
    selectinload(Pedido.atendido_por),
    selectinload(Pedido.cancelado_por),
)


def _to_out(pedido: Pedido) -> PedidoOut:
    """Monta o PedidoOut plano a partir do ORM.

    Pressupõe que `aeronave`, `solicitante`, `atendido_por` e
    `cancelado_por` já foram carregados (selectinload) — acessá-los sem
    isso dispararia lazy-load síncrono sob AsyncSession (MissingGreenlet).
    """
    return PedidoOut(
        id=pedido.id,
        numero_pedido=pedido.numero_pedido,
        aeronave_id=pedido.aeronave_id,
        aeronave_matricula=pedido.aeronave.matricula if pedido.aeronave else "",
        part_number=pedido.part_number,
        nomenclatura=pedido.nomenclatura,
        tipo_pedido=pedido.tipo_pedido,
        numero_emergencia=pedido.numero_emergencia,
        status=pedido.status,
        quantidade=pedido.quantidade,
        observacao=pedido.observacao,
        data_pedido=pedido.data_pedido,
        data_atendimento=pedido.data_atendimento,
        data_cancelamento=pedido.data_cancelamento,
        motivo_cancelamento=pedido.motivo_cancelamento,
        solicitante_trigrama=pedido.solicitante.trigrama if pedido.solicitante else None,
        atendido_por_trigrama=pedido.atendido_por.trigrama if pedido.atendido_por else None,
        cancelado_por_trigrama=pedido.cancelado_por.trigrama if pedido.cancelado_por else None,
        ativo=pedido.ativo,
        created_at=pedido.created_at,
    )


async def _numero_pedido_em_uso(
    db: AsyncSession, numero: str, excluir_id: uuid.UUID | None = None
) -> bool:
    """Checa se o número já está em uso.

    NÃO filtra por `ativo`: a UNIQUE do banco cobre também os pedidos
    soft-deleted, então um pedido na lixeira continua ocupando o número —
    do contrário este pre-check passaria e o INSERT/UPDATE quebraria com
    IntegrityError.
    """
    query = select(Pedido.id).where(Pedido.numero_pedido == numero)
    if excluir_id is not None:
        query = query.where(Pedido.id != excluir_id)
    return (await db.execute(query.limit(1))).scalar_one_or_none() is not None


def _query_base(filtros: FiltroPedido | None):
    """Monta o SELECT + WHERE compartilhado por listagem, contagem e resumo."""
    query = select(Pedido)

    mostrar_excluidos = filtros.excluidos if filtros else False
    if mostrar_excluidos:
        query = query.where(Pedido.ativo == False)  # noqa: E712
    else:
        query = query.where(Pedido.ativo == True)  # noqa: E712

    if filtros:
        if filtros.status:
            query = query.where(Pedido.status == filtros.status.value)
        if filtros.tipo_pedido:
            query = query.where(Pedido.tipo_pedido == filtros.tipo_pedido.value)
        if filtros.aeronave_id:
            query = query.where(Pedido.aeronave_id == filtros.aeronave_id)
        if filtros.texto:
            texto_like = f"%{escape_like(filtros.texto.lower())}%"
            query = query.outerjoin(Aeronave, Pedido.aeronave_id == Aeronave.id).where(
                or_(
                    func.lower(Pedido.numero_pedido).like(texto_like, escape="\\"),
                    func.lower(Pedido.part_number).like(texto_like, escape="\\"),
                    func.lower(Pedido.nomenclatura).like(texto_like, escape="\\"),
                    func.lower(Aeronave.matricula).like(texto_like, escape="\\"),
                )
            )

    return query


async def criar_pedido(db: AsyncSession, dados: PedidoCreate, solicitante_id: uuid.UUID) -> Pedido:
    """Cria um novo pedido. Status inicial sempre PENDENTE (RN-05).

    RN-02: `numero_pedido` é informado manualmente pelo usuário — é o número
    emitido no sistema interno da FAB, apenas transcrito para o SAA29. O
    servidor não gera mais número nenhum; só garante unicidade.
    """
    aeronave = await buscar_aeronave(db, dados.aeronave_id)
    if not aeronave:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave não encontrada.")

    # RN-03/RN-04: reforçado no servidor como defesa em profundidade, além
    # da validação já feita no schema PedidoCreate.
    numero_emergencia = dados.numero_emergencia
    if dados.tipo_pedido == TipoPedido.EMERGENCIA and not numero_emergencia:
        raise domain_exc.ConflitoNegocioError(
            "numero_emergencia é obrigatório para pedidos de EMERGENCIA."
        )
    if dados.tipo_pedido == TipoPedido.NORMAL:
        numero_emergencia = None

    if await _numero_pedido_em_uso(db, dados.numero_pedido):
        raise domain_exc.ConflitoNegocioError(
            f"Já existe um pedido com o número '{dados.numero_pedido}'."
        )

    hoje = datetime.now(timezone.utc).date()

    pedido = Pedido(
        numero_pedido=dados.numero_pedido,
        aeronave_id=dados.aeronave_id,
        part_number=dados.part_number,
        nomenclatura=dados.nomenclatura,
        tipo_pedido=dados.tipo_pedido.value,
        numero_emergencia=numero_emergencia,
        quantidade=dados.quantidade,
        status=StatusPedido.PENDENTE.value,
        observacao=dados.observacao,
        data_pedido=hoje,
        solicitante_id=solicitante_id,
    )
    try:
        # SAVEPOINT: cobre a corrida entre duas criações concorrentes com o
        # mesmo numero_pedido (o pre-check acima não é atômico sozinho).
        async with db.begin_nested():
            db.add(pedido)
            await db.flush()
    except IntegrityError as exc:
        raise domain_exc.ConflitoNegocioError(
            f"Já existe um pedido com o número '{dados.numero_pedido}'."
        ) from exc

    await db.refresh(pedido, ["aeronave", "solicitante"])
    return pedido


async def listar_pedidos(db: AsyncSession, filtros: FiltroPedido) -> tuple[list[Pedido], int]:
    """Lista pedidos com filtros e paginação. Retorna (itens, total)."""
    query = _query_base(filtros)

    # `maintain_column_froms=True`: sem isso, with_only_columns recalcula o
    # FROM a partir apenas das novas colunas — como func.count(Pedido.id)
    # não referencia Aeronave, o outerjoin usado pelo filtro `texto` seria
    # descartado silenciosamente, mas o WHERE (que ainda cita
    # Aeronave.matricula) continuaria ali, quebrando a query.
    total_query = query.with_only_columns(func.count(Pedido.id), maintain_column_froms=True)
    total = (await db.execute(total_query)).scalar_one()

    query = (
        query.order_by(Pedido.data_pedido.desc(), Pedido.created_at.desc())
        .offset(filtros.skip)
        .limit(filtros.limit)
        .options(*_RELACOES_EAGER)
    )
    result = await db.execute(query)
    itens = list(result.scalars().unique().all())
    return itens, int(total)


async def obter_resumo(db: AsyncSession, filtros: FiltroPedido) -> PedidoResumo:
    """Contadores agregados para os cards de resumo — respeita os mesmos
    filtros da listagem (exceto paginação), numa única query."""
    base = _query_base(filtros)
    agregada = base.with_only_columns(
        func.count().label("total"),
        func.sum(case((Pedido.status == StatusPedido.PENDENTE.value, 1), else_=0)).label("pendentes"),
        func.sum(case((Pedido.status == StatusPedido.ATENDIDO.value, 1), else_=0)).label("atendidos"),
        func.sum(case((Pedido.status == StatusPedido.CANCELADO.value, 1), else_=0)).label("cancelados"),
        func.sum(case((Pedido.tipo_pedido == TipoPedido.EMERGENCIA.value, 1), else_=0)).label("emergencias"),
        maintain_column_froms=True,
    )

    row = (await db.execute(agregada)).one()
    return PedidoResumo(
        total=row.total or 0,
        pendentes=row.pendentes or 0,
        atendidos=row.atendidos or 0,
        cancelados=row.cancelados or 0,
        emergencias=row.emergencias or 0,
    )


async def _buscar_pedido_por_id(
    db: AsyncSession, pedido_id: uuid.UUID, incluir_inativos: bool = False
) -> Pedido | None:
    query = select(Pedido).where(Pedido.id == pedido_id).options(*_RELACOES_EAGER)
    if not incluir_inativos:
        query = query.where(Pedido.ativo == True)  # noqa: E712
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def buscar_pedido(db: AsyncSession, pedido_id: uuid.UUID, incluir_inativos: bool = False) -> Pedido | None:
    return await _buscar_pedido_por_id(db, pedido_id, incluir_inativos=incluir_inativos)


async def editar_pedido(db: AsyncSession, pedido_id: uuid.UUID, dados: PedidoUpdate) -> Pedido:
    """RN-09: apenas pedidos PENDENTE podem ser editados."""
    pedido = await _buscar_pedido_por_id(db, pedido_id)
    if not pedido:
        raise domain_exc.EntidadeNaoEncontradaError("Pedido não encontrado.")

    if StatusPedido(pedido.status) != StatusPedido.PENDENTE:
        raise domain_exc.ConflitoNegocioError(
            "Apenas pedidos com status PENDENTE podem ser editados."
        )

    if dados.numero_pedido is not None and dados.numero_pedido != pedido.numero_pedido:
        if await _numero_pedido_em_uso(db, dados.numero_pedido, excluir_id=pedido_id):
            raise domain_exc.ConflitoNegocioError(
                f"Já existe um pedido com o número '{dados.numero_pedido}'."
            )
        pedido.numero_pedido = dados.numero_pedido
    if dados.part_number is not None:
        pedido.part_number = dados.part_number
    if dados.nomenclatura is not None:
        pedido.nomenclatura = dados.nomenclatura
    if dados.quantidade is not None:
        pedido.quantidade = dados.quantidade
    if dados.observacao is not None:
        pedido.observacao = dados.observacao
    if dados.tipo_pedido is not None:
        pedido.tipo_pedido = dados.tipo_pedido.value
    if dados.numero_emergencia is not None:
        pedido.numero_emergencia = dados.numero_emergencia

    # Reforça a coerência tipo/emergência após aplicar as mudanças (RN-03/RN-04).
    if pedido.tipo_pedido == TipoPedido.NORMAL.value:
        pedido.numero_emergencia = None
    elif pedido.tipo_pedido == TipoPedido.EMERGENCIA.value and not pedido.numero_emergencia:
        raise domain_exc.ConflitoNegocioError(
            "numero_emergencia é obrigatório para pedidos de EMERGENCIA."
        )

    try:
        # SAVEPOINT: cobre a corrida entre duas edições concorrentes trocando
        # para o mesmo numero_pedido (o pre-check acima não é atômico sozinho).
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise domain_exc.ConflitoNegocioError(
            f"Já existe um pedido com o número '{dados.numero_pedido}'."
        ) from exc

    return pedido


async def atender_pedido(db: AsyncSession, pedido_id: uuid.UUID, usuario_id: uuid.UUID) -> Pedido:
    """RN-10/RN-11: marcação puramente administrativa — não escreve em
    nenhuma outra tabela (inventário/instalações permanecem intocados)."""
    pedido = await _buscar_pedido_por_id(db, pedido_id)
    if not pedido:
        raise domain_exc.EntidadeNaoEncontradaError("Pedido não encontrado.")

    if StatusPedido(pedido.status) != StatusPedido.PENDENTE:
        raise domain_exc.ConflitoNegocioError(
            "Apenas pedidos com status PENDENTE podem ser atendidos."
        )

    pedido.status = StatusPedido.ATENDIDO.value
    pedido.data_atendimento = datetime.now(timezone.utc)
    pedido.atendido_por_id = usuario_id

    await db.flush()
    await db.refresh(pedido, ["atendido_por"])
    return pedido


async def cancelar_pedido(
    db: AsyncSession, pedido_id: uuid.UUID, usuario_id: uuid.UUID, dados: PedidoCancelar
) -> Pedido:
    """RN-10/RN-12: cancelamento exige motivo e só é permitido a partir de PENDENTE."""
    pedido = await _buscar_pedido_por_id(db, pedido_id)
    if not pedido:
        raise domain_exc.EntidadeNaoEncontradaError("Pedido não encontrado.")

    if StatusPedido(pedido.status) != StatusPedido.PENDENTE:
        raise domain_exc.ConflitoNegocioError(
            "Apenas pedidos com status PENDENTE podem ser cancelados."
        )

    pedido.status = StatusPedido.CANCELADO.value
    pedido.data_cancelamento = datetime.now(timezone.utc)
    pedido.cancelado_por_id = usuario_id
    pedido.motivo_cancelamento = dados.motivo

    await db.flush()
    await db.refresh(pedido, ["cancelado_por"])
    return pedido


async def excluir_pedido(db: AsyncSession, pedido_id: uuid.UUID) -> Pedido:
    """RN-13: soft delete. Idempotência — já inativo é conflito."""
    pedido = await _buscar_pedido_por_id(db, pedido_id, incluir_inativos=True)
    if not pedido:
        raise domain_exc.EntidadeNaoEncontradaError("Pedido não encontrado.")

    if not pedido.ativo:
        raise domain_exc.ConflitoNegocioError("Pedido já está excluído.")

    pedido.ativo = False
    await db.flush()
    return pedido


async def restaurar_pedido(db: AsyncSession, pedido_id: uuid.UUID) -> Pedido:
    """RN-13: restaura um pedido soft-deleted. Idempotência — já ativo é conflito."""
    pedido = await _buscar_pedido_por_id(db, pedido_id, incluir_inativos=True)
    if not pedido:
        raise domain_exc.EntidadeNaoEncontradaError("Pedido não encontrado.")

    if pedido.ativo:
        raise domain_exc.ConflitoNegocioError("Pedido já está ativo.")

    pedido.ativo = True
    await db.flush()
    return pedido
