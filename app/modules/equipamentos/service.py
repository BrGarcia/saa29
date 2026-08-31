"""
app/equipamentos/service.py
Camada de serviço para gestão de equipamentos seguindo a arquitetura PN vs Slot.

Convenções deste módulo:
    - Normalização de PN/SN é responsabilidade dos schemas Pydantic (fonte única).
    - Erros de negócio usam as exceções de domínio de `app.shared.core.exceptions`,
      que já carregam o status HTTP e são tratadas pelo handler global.
    - Colunas de status são `String`; sempre gravar `Enum.value` (nunca o enum cru).
"""

import logging
import uuid
from datetime import date, datetime
from sqlalchemy import select, or_, desc, union_all, literal, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Modelos podem ser importados no topo com segurança: models nunca importam services,
# portanto não há ciclo.
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.shared.core import exceptions as domain_exc
from app.shared.core.db_utils import escape_like
from app.shared.core.enums import AcaoAuditoria, EntidadeAuditada, StatusItem
from app.modules.equipamentos.models import (
    ModeloEquipamento,
    SlotInventario,
    ItemEquipamento,
    Instalacao,
)
# ControleVencimento entra aqui pela mesma razão que EquipamentoControle já
# estava: excluir um item precisa bloquear quando há vínculo, senão o DELETE
# estoura IntegrityError (500) em vez de devolver 409 com explicação.
from app.modules.vencimentos.models import ControleVencimento, EquipamentoControle
from app.modules.equipamentos.schemas import (
    ModeloEquipamentoCreate,
    ModeloEquipamentoUpdate,
    SlotInventarioCreate,
    ItemEquipamentoCreate,
    SlotInventarioUpdate,
    ItemEquipamentoUpdate,
    InventarioItemOut,
    AjusteInventarioCreate,
    AjusteInventarioResponse,
)
from app.modules.equipamentos import auditoria_service
# A criação dos controles de vencimento pertence ao domínio de vencimentos;
# aqui apenas orquestramos a chamada (vencimentos.service não importa este módulo).
from app.modules.vencimentos.service import criar_controles_para_item

logger = logging.getLogger(__name__)

# Teto de segurança para listagens paginadas
LIMITE_MAXIMO_LISTAGEM = 200


# ============================================================
# Catálogo (ModeloEquipamento / PN)
# ============================================================

async def criar_modelo(
    db: AsyncSession,
    dados: ModeloEquipamentoCreate,
    usuario_id: uuid.UUID | None = None,
    ip_origem: str | None = None,
) -> ModeloEquipamento:
    """Cadastra um novo Part Number no catálogo.

    O PN já chega normalizado (maiúsculas, sem espaços) pelo schema.

    Raises:
        ConflitoNegocioError: PN já cadastrado — tanto na verificação prévia
            quanto na violação da constraint UNIQUE (criação concorrente).
    """
    part_number = dados.part_number
    if await buscar_modelo_por_pn(db, part_number):
        raise domain_exc.ConflitoNegocioError(f"O Part Number '{part_number}' já está cadastrado.")

    modelo = ModeloEquipamento(
        part_number=part_number,
        nome_generico=dados.nome_generico,
        descricao=dados.descricao
    )
    try:
        # SAVEPOINT: em caso de violação de UNIQUE, desfaz apenas este insert
        # e mantém a transação da requisição utilizável.
        async with db.begin_nested():
            db.add(modelo)
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao criar PN %s: %s", part_number, exc.orig)
        raise domain_exc.ConflitoNegocioError(
            f"O Part Number '{part_number}' já está cadastrado."
        ) from exc

    await auditoria_service.registrar(
        db,
        entidade=EntidadeAuditada.MODELO_EQUIPAMENTO,
        entidade_id=modelo.id,
        acao=AcaoAuditoria.CREATE,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        novos=auditoria_service.snapshot(modelo),
    )
    return modelo

async def buscar_modelo_por_pn(db: AsyncSession, pn: str) -> ModeloEquipamento | None:
    """Busca um PN do catálogo pelo part number exato (já normalizado)."""
    result = await db.execute(select(ModeloEquipamento).where(ModeloEquipamento.part_number == pn))
    return result.scalar_one_or_none()

async def buscar_modelo(db: AsyncSession, modelo_id: uuid.UUID) -> ModeloEquipamento:
    """Busca um PN do catálogo pelo id.

    Raises:
        EntidadeNaoEncontradaError: PN inexistente.
    """
    result = await db.execute(select(ModeloEquipamento).where(ModeloEquipamento.id == modelo_id))
    modelo = result.scalar_one_or_none()
    if not modelo:
        raise domain_exc.EntidadeNaoEncontradaError("Equipamento não encontrado.")
    return modelo

async def listar_modelos(
    db: AsyncSession,
    limit: int | None = None,
    offset: int = 0,
) -> list[ModeloEquipamento]:
    """Lista o catálogo de PNs em ordem alfabética.

    Args:
        limit: Máximo de registros. `None` retorna todos (o catálogo é consumido
            inteiro pelo frontend para montar seletores).
        offset: Registros a saltar (paginação).
    """
    stmt = select(ModeloEquipamento).order_by(ModeloEquipamento.part_number)
    stmt = _aplicar_paginacao(stmt, limit, offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def atualizar_modelo(
    db: AsyncSession,
    modelo_id: uuid.UUID,
    dados: ModeloEquipamentoUpdate,
    usuario_id: uuid.UUID | None = None,
    ip_origem: str | None = None,
) -> ModeloEquipamento:
    """Atualiza os dados cadastrais de um PN.

    Raises:
        EntidadeNaoEncontradaError: PN inexistente.
        ConflitoNegocioError: novo part number já usado por outro PN.
    """
    result = await db.execute(select(ModeloEquipamento).where(ModeloEquipamento.id == modelo_id))
    modelo = result.scalar_one_or_none()
    if not modelo:
        raise domain_exc.EntidadeNaoEncontradaError("Equipamento não encontrado.")

    antes = auditoria_service.snapshot(modelo)

    if dados.part_number is not None:
        part_number = dados.part_number
        if part_number != modelo.part_number:
            if await buscar_modelo_por_pn(db, part_number):
                raise domain_exc.ConflitoNegocioError(
                    f"O Part Number '{part_number}' já está cadastrado."
                )
        modelo.part_number = part_number

    if dados.nome_generico is not None:
        modelo.nome_generico = dados.nome_generico
    if dados.descricao is not None:
        modelo.descricao = dados.descricao

    await db.flush()

    anteriores, novos = auditoria_service.diff_campos(antes, auditoria_service.snapshot(modelo))
    if novos:
        await auditoria_service.registrar(
            db,
            entidade=EntidadeAuditada.MODELO_EQUIPAMENTO,
            entidade_id=modelo.id,
            acao=AcaoAuditoria.UPDATE,
            usuario_id=usuario_id,
            ip_origem=ip_origem,
            anteriores=anteriores,
            novos=novos,
        )
    return modelo

async def remover_modelo(
    db: AsyncSession,
    modelo_id: uuid.UUID,
    usuario_id: uuid.UUID | None = None,
    ip_origem: str | None = None,
    justificativa: str | None = None,
) -> None:
    """Exclui um PN do catálogo.

    Raises:
        EntidadeNaoEncontradaError: PN inexistente.
        ConflitoNegocioError: existem itens físicos, slots ou controles de
            vencimento (EquipamentoControle) dependentes do PN.
    """
    result = await db.execute(select(ModeloEquipamento).where(ModeloEquipamento.id == modelo_id))
    modelo = result.scalar_one_or_none()
    if not modelo:
        raise domain_exc.EntidadeNaoEncontradaError("Equipamento não encontrado.")

    # Verificar se existem itens físicos atrelados
    res_itens = await db.execute(select(ItemEquipamento.id).where(ItemEquipamento.modelo_id == modelo_id))
    if res_itens.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: existem itens físicos (Serial Numbers) cadastrados para este PN."
        )

    # Verificar se existem slots atrelados
    res_slots = await db.execute(select(SlotInventario.id).where(SlotInventario.modelo_id == modelo_id))
    if res_slots.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: este PN está associado a slots na configuração da aeronave."
        )

    # Verificar se existem controles de vencimento (templates) atrelados —
    # a FK usa ondelete=CASCADE, então sem esta checagem a exclusão apagaria
    # esses templates silenciosamente (MELHORIA-06, achados_equipamentos.md).
    res_controles = await db.execute(
        select(EquipamentoControle.id).where(EquipamentoControle.modelo_id == modelo_id)
    )
    if res_controles.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: este PN tem controles de vencimento (regras de periodicidade) cadastrados."
        )

    antes = auditoria_service.snapshot(modelo)
    await db.delete(modelo)
    await db.flush()
    await auditoria_service.registrar(
        db,
        entidade=EntidadeAuditada.MODELO_EQUIPAMENTO,
        entidade_id=modelo_id,
        acao=AcaoAuditoria.DELETE,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        anteriores=antes,
        justificativa=justificativa,
    )


# ============================================================
# Itens (Serial Number)
# ============================================================

async def criar_item_com_heranca(
    db: AsyncSession,
    dados: ItemEquipamentoCreate,
    usuario_id: uuid.UUID | None = None,
    ip_origem: str | None = None,
) -> ItemEquipamento:
    """Cria um item físico (S/N) e herda os controles definidos no PN.

    Efeito colateral: cria os `ControleVencimento` herdados do template do PN
    (delegado a `vencimentos.service.criar_controles_para_item`).

    Raises:
        ConflitoNegocioError: S/N já cadastrado para o PN — na verificação prévia
            ou na violação de `uq_item_sn_per_pn` (criação concorrente).
    """
    # 1. Verificar se SN já existe para este PN
    if await _buscar_item_por_sn(db, dados.modelo_id, dados.numero_serie):
        raise domain_exc.ConflitoNegocioError(
            f"S/N '{dados.numero_serie}' já cadastrado para este P/N."
        )

    item = ItemEquipamento(
        id=uuid.uuid4(),
        modelo_id=dados.modelo_id,
        numero_serie=dados.numero_serie,
        status=dados.status.value,
    )
    try:
        async with db.begin_nested():
            db.add(item)
            await db.flush()
    except IntegrityError as exc:
        logger.warning(
            "Conflito de UNIQUE ao criar S/N %s (PN %s): %s",
            dados.numero_serie, dados.modelo_id, exc.orig
        )
        raise domain_exc.ConflitoNegocioError(
            f"S/N '{dados.numero_serie}' já cadastrado para este P/N."
        ) from exc

    # 2. Herdar controles do Modelo (regra do domínio de vencimentos)
    await criar_controles_para_item(db, item.id, item.modelo_id)

    await auditoria_service.registrar(
        db,
        entidade=EntidadeAuditada.ITEM,
        entidade_id=item.id,
        acao=AcaoAuditoria.CREATE,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        novos=auditoria_service.snapshot(item),
    )
    return item

async def listar_itens(
    db: AsyncSession,
    modelo_id: uuid.UUID | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[ItemEquipamento]:
    """Lista itens físicos (Serial Numbers), opcionalmente filtrados por PN.

    Args:
        modelo_id: Restringe a um PN específico.
        limit: Máximo de registros. `None` retorna todos.
        offset: Registros a saltar (paginação).
    """
    stmt = select(ItemEquipamento).options(selectinload(ItemEquipamento.modelo))
    if modelo_id:
        stmt = stmt.where(ItemEquipamento.modelo_id == modelo_id)
    stmt = _aplicar_paginacao(stmt.order_by(ItemEquipamento.numero_serie), limit, offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _aplicar_paginacao(stmt, limit: int | None, offset: int):
    """Aplica limit/offset a um select, respeitando o teto de segurança."""
    if limit is not None:
        stmt = stmt.limit(min(limit, LIMITE_MAXIMO_LISTAGEM))
    if offset:
        stmt = stmt.offset(offset)
    return stmt


# ============================================================
# Slots (Configuração da Aeronave)
# ============================================================

async def criar_slot(
    db: AsyncSession,
    dados: SlotInventarioCreate,
    usuario_id: uuid.UUID | None = None,
    ip_origem: str | None = None,
) -> SlotInventario:
    """Define um novo slot/posição de inventário.

    Raises:
        EntidadeNaoEncontradaError: `modelo_id` não corresponde a um PN cadastrado.
        ConflitoNegocioError: já existe slot com o mesmo (nome_posicao, sistema).
    """
    if not await db.get(ModeloEquipamento, dados.modelo_id):
        raise domain_exc.EntidadeNaoEncontradaError(f"Equipamento {dados.modelo_id} não encontrado.")

    if await _slot_duplicado(db, dados.nome_posicao, dados.sistema):
        raise domain_exc.ConflitoNegocioError("Já existe um slot com este nome nesta localização.")

    slot = SlotInventario(**dados.model_dump())
    db.add(slot)
    await db.flush()

    await auditoria_service.registrar(
        db,
        entidade=EntidadeAuditada.SLOT,
        entidade_id=slot.id,
        acao=AcaoAuditoria.CREATE,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        novos=auditoria_service.snapshot(slot),
    )
    return slot


async def _slot_duplicado(
    db: AsyncSession, nome_posicao: str, sistema: str | None, excluir_id: uuid.UUID | None = None
) -> bool:
    """Há outro slot com esta chave natural (nome_posicao, sistema)?

    A UNIQUE que formaliza isso no banco só chega na fatia 3; até lá a
    verificação em Python é a única barreira.
    """
    stmt = select(SlotInventario.id).where(
        SlotInventario.nome_posicao == nome_posicao,
        SlotInventario.sistema == sistema,
    )
    if excluir_id:
        stmt = stmt.where(SlotInventario.id != excluir_id)
    return (await db.execute(stmt)).first() is not None


async def listar_slots(db: AsyncSession, incluir_inativos: bool = False) -> list[SlotInventario]:
    """Lista os slots configurados (alimenta GET /equipamentos/slots/).

    ATENÇÃO: esta função é distinta de `_buscar_slots`, que alimenta a grade
    de /inventario. As duas precisam filtrar inativos — filtrar só numa deixa
    o slot desligado aparecendo do outro lado.

    `incluir_inativos=True` é o que permite à tela de gestão exibir — e
    reativar — um slot desligado. Sem esse parâmetro, inativar seria uma
    operação sem volta pela aplicação.
    """
    stmt = select(SlotInventario).options(selectinload(SlotInventario.modelo))
    if not incluir_inativos:
        stmt = stmt.where(SlotInventario.ativo.is_(True))
    stmt = stmt.order_by(
        SlotInventario.ordem_exibicao.nulls_last(),
        SlotInventario.sistema,
        SlotInventario.nome_posicao,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ============================================================
# Inventário de Aeronave e Instalações
# ============================================================

async def listar_inventario_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
    nome: str | None = None,
) -> list[InventarioItemOut]:
    """Retorna a situação de TODOS os slots da aeronave (ocupados e vazios).

    Executa um número fixo de queries (independente da quantidade de slots):
    slots, instalações ativas, aeronave anterior de cada item e última remoção
    por slot. A montagem de cada linha é pura (sem I/O).

    Raises:
        EntidadeNaoEncontradaError: aeronave inexistente.
    """
    await _garantir_aeronave_existe(db, aeronave_id)

    try:
        slots = await _buscar_slots(db, nome)
        inst_map = await _mapear_instalacoes_ativas(db, aeronave_id)
        item_ids = [row[1].id for row in inst_map.values()]
        ant_map = await _mapear_aeronaves_anteriores(db, item_ids, aeronave_id)
        rem_map = await _mapear_ultimas_remocoes(db, aeronave_id)

        inventario = [
            _montar_linha_inventario(slot, inst_map, ant_map, rem_map)
            for slot in slots
        ]
        # `ordem_exibicao` só funciona aqui: um ORDER BY na query seria
        # sobrescrito por este sort. Slots sem ordem definida vão para o fim.
        inventario.sort(
            key=lambda x: (
                x.ordem_exibicao if x.ordem_exibicao is not None else 10**6,
                x.sistema or "ZZZ",
                x.nome_posicao,
            )
        )
        return inventario

    except Exception:
        logger.exception("Erro ao listar inventário da aeronave %s", aeronave_id)
        raise


async def _garantir_aeronave_existe(db: AsyncSession, aeronave_id: uuid.UUID) -> None:
    """Valida a existência da aeronave sem depender do service de aeronaves.

    Raises:
        EntidadeNaoEncontradaError: aeronave inexistente.
    """
    res = await db.execute(select(Aeronave.id).where(Aeronave.id == aeronave_id))
    if res.first() is None:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave não encontrada.")


async def _buscar_slots(
    db: AsyncSession, nome: str | None = None, apenas_ativos: bool = True
) -> list[SlotInventario]:
    """Retorna os slots configurados, com filtro opcional por posição ou PN.

    Alimenta a grade de /inventario. Slot inativo fica de fora por padrão —
    ver `listar_slots`, que é a outra porta de entrada e precisa do mesmo
    cuidado.
    """
    stmt = select(SlotInventario).options(selectinload(SlotInventario.modelo))
    if apenas_ativos:
        stmt = stmt.where(SlotInventario.ativo.is_(True))
    if nome:
        nome_escaped = escape_like(nome)
        stmt = stmt.join(ModeloEquipamento).where(
            or_(
                SlotInventario.nome_posicao.ilike(f"%{nome_escaped}%", escape="\\"),
                ModeloEquipamento.nome_generico.ilike(f"%{nome_escaped}%", escape="\\")
            )
        )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def _mapear_instalacoes_ativas(db: AsyncSession, aeronave_id: uuid.UUID) -> dict:
    """Mapa slot_id -> (Instalacao, ItemEquipamento, trigrama) das instalações ativas."""
    stmt = (
        select(Instalacao, ItemEquipamento, Usuario.trigrama)
        .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
        .where(
            Instalacao.aeronave_id == aeronave_id,
            Instalacao.data_remocao.is_(None)
        )
    )
    res = await db.execute(stmt)
    return {row[0].slot_id: row for row in res.all()}


async def _mapear_aeronaves_anteriores(
    db: AsyncSession, item_ids: list[uuid.UUID], aeronave_id: uuid.UUID
) -> dict[uuid.UUID, str]:
    """Mapa item_id -> matrícula da última aeronave em que o item esteve instalado."""
    if not item_ids:
        return {}

    subq = (
        select(
            Instalacao.item_id,
            Aeronave.matricula,
            func.row_number().over(
                partition_by=Instalacao.item_id,
                order_by=[desc(Instalacao.data_remocao), desc(Instalacao.created_at)]
            ).label("rn")
        )
        .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
        .where(
            Instalacao.item_id.in_(item_ids),
            Instalacao.data_remocao.is_not(None),
            Instalacao.aeronave_id != aeronave_id
        )
    ).subquery()

    res = await db.execute(select(subq.c.item_id, subq.c.matricula).where(subq.c.rn == 1))
    return {r.item_id: r.matricula for r in res.all()}


async def _mapear_ultimas_remocoes(
    db: AsyncSession, aeronave_id: uuid.UUID
) -> dict[uuid.UUID, tuple[datetime | None, str | None]]:
    """Retorna, por slot da aeronave, a última remoção registrada.

    Usa window function (row_number) para trazer tudo em uma única query,
    substituindo a consulta por slot vazio que causava N+1.

    Returns:
        Mapa slot_id -> (data_rastreio, trigrama_do_usuario).
    """
    subq = (
        select(
            Instalacao.slot_id.label("slot_id"),
            Instalacao.removido_em.label("removido_em"),
            Instalacao.created_at.label("created_at"),
            Usuario.trigrama.label("trigrama"),
            func.row_number().over(
                partition_by=Instalacao.slot_id,
                order_by=[desc(Instalacao.removido_em), desc(Instalacao.created_at)]
            ).label("rn")
        )
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
        .where(
            Instalacao.aeronave_id == aeronave_id,
            Instalacao.data_remocao.is_not(None)
        )
    ).subquery()

    res = await db.execute(
        select(subq.c.slot_id, subq.c.removido_em, subq.c.created_at, subq.c.trigrama)
        .where(subq.c.rn == 1)
    )
    return {
        r.slot_id: (r.removido_em or r.created_at, r.trigrama)
        for r in res.all()
    }


def _montar_linha_inventario(
    slot: SlotInventario,
    inst_map: dict,
    ant_map: dict[uuid.UUID, str],
    rem_map: dict[uuid.UUID, tuple[datetime | None, str | None]],
) -> InventarioItemOut:
    """Monta a linha de inventário de um slot. Função pura (sem I/O)."""
    row = inst_map.get(slot.id)
    instalacao, item, user_trigrama = row if row else (None, None, None)
    anv_anterior = ant_map.get(item.id) if item else None
    data_rastreio = instalacao.created_at if instalacao else None

    if not instalacao:
        ultima_remocao = rem_map.get(slot.id)
        if ultima_remocao:
            data_rastreio, user_trigrama = ultima_remocao

    return InventarioItemOut(
        slot_id=slot.id,
        modelo_id=slot.modelo_id,
        nome_posicao=slot.nome_posicao,
        sistema=slot.sistema,
        ordem_exibicao=slot.ordem_exibicao,
        part_number=slot.modelo.part_number,
        nome_generico=slot.modelo.nome_generico,
        equipamento_nome=slot.nome_posicao,
        equipamento_id=slot.id,
        item_id=item.id if item else None,
        numero_serie=item.numero_serie if item else None,
        status_item=item.status if item else None,
        instalacao_id=instalacao.id if instalacao else None,
        data_instalacao=instalacao.data_instalacao if instalacao else None,
        data_atualizacao=data_rastreio,
        usuario_trigrama=user_trigrama,
        aeronave_anterior=anv_anterior,
    )


async def ajustar_inventario_item(
    db: AsyncSession,
    dados: AjusteInventarioCreate,
    usuario_id: uuid.UUID | None = None,
) -> AjusteInventarioResponse:
    """Sincroniza o S/N REAL com um SLOT de uma aeronave.

    `dados.slot_id` e `dados.numero_serie_real` já chegam resolvidos/normalizados
    pelo schema. S/N vazio significa "slot vazio" (registra a remoção).

    `usuario_id` é sempre o usuário autenticado da requisição — nunca deve vir
    do payload do cliente (BUG-01, achados_equipamentos.md: a trilha de
    auditoria do inventário era forjável, pois `usuario_id` era um campo
    comum do payload).

    Efeitos colaterais: pode criar o item físico (e seus controles de vencimento)
    e encerrar instalações anteriores — inclusive em outra aeronave, quando
    `forcar_transferencia` é True.
    """
    aeronave_id = dados.aeronave_id
    slot_id = dados.slot_id
    sn_real = dados.numero_serie_real

    slot = await _obter_slot_com_modelo(db, slot_id)
    if not slot:
        return AjusteInventarioResponse(sucesso=False, mensagem="Slot de inventário não encontrado.")

    inst_atual = await _obter_instalacao_ativa_no_slot(db, aeronave_id, slot_id)

    # Caso de remoção (SN vazio)
    if not sn_real:
        if inst_atual:
            _registrar_remocao(inst_atual)
            return AjusteInventarioResponse(sucesso=True, mensagem="Equipamento removido (vazio no inventário).")
        return AjusteInventarioResponse(sucesso=True, mensagem="O slot já está vazio.")

    if inst_atual and inst_atual.item.numero_serie == sn_real:
        return AjusteInventarioResponse(sucesso=True, mensagem="S/N já está sincronizado.")

    item_real = await _obter_ou_criar_item_por_pn(db, slot.modelo_id, sn_real)

    conflito_resp = await _validar_e_resolver_conflitos(
        db, item_real, aeronave_id, slot_id, dados.forcar_transferencia
    )
    if conflito_resp:
        return conflito_resp

    nova_instalacao = _efetivar_troca_no_slot(db, inst_atual, item_real, aeronave_id, slot_id, usuario_id)

    try:
        # SAVEPOINT: rede de segurança contra duas instalações concorrentes
        # no mesmo slot/aeronave (RISCO-05) — o índice único parcial
        # uq_instalacao_ativa_por_slot_aeronave é quem garante a invariante.
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        logger.warning(
            "Conflito de instalação concorrente no slot %s da aeronave %s: %s",
            slot_id, aeronave_id, exc.orig,
        )
        # Descarta o estado em memória da tentativa que falhou: sem isso, o
        # objeto novo (ainda pendente) e a mutação de `inst_atual` (remoção)
        # ficariam presos na sessão e seriam reenviados no commit final da
        # requisição, reproduzindo o mesmo IntegrityError sem tratamento.
        db.expunge(nova_instalacao)
        if inst_atual:
            db.expire(inst_atual)
        return AjusteInventarioResponse(
            sucesso=False,
            mensagem="Este slot já foi alterado por outra operação simultânea. Tente novamente."
        )

    return AjusteInventarioResponse(sucesso=True, mensagem="Inventário ajustado com sucesso.")


# --- Funções Auxiliares (Desacoplamento de Domínio) ---

def _registrar_remocao(instalacao: Instalacao, data_remocao: date | None = None) -> None:
    """Encerra uma instalação, gravando data e timestamp do EVENTO de remoção.

    `removido_em` é dedicado ao evento — `updated_at` é mantido automaticamente
    pelo `onupdate` do model e não serve como histórico.
    """
    instalacao.data_remocao = data_remocao or date.today()
    instalacao.removido_em = func.now()

async def _obter_slot_com_modelo(db: AsyncSession, slot_id: uuid.UUID) -> SlotInventario | None:
    """Carrega um slot com o PN (modelo) já resolvido."""
    res = await db.execute(
        select(SlotInventario).where(SlotInventario.id == slot_id).options(selectinload(SlotInventario.modelo))
    )
    return res.scalar_one_or_none()

async def _obter_instalacao_ativa_no_slot(db: AsyncSession, aeronave_id: uuid.UUID, slot_id: uuid.UUID) -> Instalacao | None:
    """Retorna a instalação sem data de remoção no slot informado, se houver."""
    res = await db.execute(
        select(Instalacao)
        .where(Instalacao.slot_id == slot_id, Instalacao.aeronave_id == aeronave_id, Instalacao.data_remocao.is_(None))
        .options(selectinload(Instalacao.item))
    )
    return res.scalar_one_or_none()

async def _buscar_item_por_sn(db: AsyncSession, modelo_id: uuid.UUID, sn: str) -> ItemEquipamento | None:
    """Busca um item físico pela combinação única (PN, S/N)."""
    res = await db.execute(
        select(ItemEquipamento).where(
            ItemEquipamento.numero_serie == sn,
            ItemEquipamento.modelo_id == modelo_id
        )
    )
    return res.scalar_one_or_none()

async def _obter_ou_criar_item_por_pn(db: AsyncSession, modelo_id: uuid.UUID, sn: str) -> ItemEquipamento:
    """Get-or-create do item físico, com herança de controles na criação.

    Em caso de criação concorrente (violação de uq_item_sn_per_pn), desfaz o
    SAVEPOINT e recupera o registro criado pela outra transação.
    """
    item = await _buscar_item_por_sn(db, modelo_id, sn)
    if item:
        return item

    item = ItemEquipamento(
        id=uuid.uuid4(), modelo_id=modelo_id, numero_serie=sn, status=StatusItem.ATIVO.value
    )
    try:
        async with db.begin_nested():
            db.add(item)
            await db.flush()
    except IntegrityError:
        logger.warning(
            "Criação concorrente do S/N %s (PN %s) detectada; recuperando item existente.",
            sn, modelo_id
        )
        item_concorrente = await _buscar_item_por_sn(db, modelo_id, sn)
        if item_concorrente is None:
            raise
        return item_concorrente

    # Herdar controles do Modelo (regra do domínio de vencimentos)
    await criar_controles_para_item(db, item.id, item.modelo_id)
    return item

async def _validar_e_resolver_conflitos(
    db: AsyncSession,
    item: ItemEquipamento,
    aeronave_id: uuid.UUID,
    slot_id: uuid.UUID,
    forcar_transferencia: bool,
) -> AjusteInventarioResponse | None:
    """Verifica se o item já está instalado em outro lugar.

    Returns:
        Resposta pedindo confirmação, quando há conflito e a transferência não
        foi forçada. `None` quando não há conflito (ou ele já foi resolvido,
        encerrando a instalação anterior).
    """
    res = await db.execute(
        select(Instalacao).where(Instalacao.item_id == item.id, Instalacao.data_remocao.is_(None))
    )
    inst_conflito = res.scalar_one_or_none()

    if inst_conflito and (inst_conflito.aeronave_id != aeronave_id or inst_conflito.slot_id != slot_id):
        if not forcar_transferencia:
            res_acft = await db.execute(select(Aeronave.matricula).where(Aeronave.id == inst_conflito.aeronave_id))
            matricula = res_acft.scalar_one()
            return AjusteInventarioResponse(
                sucesso=False,
                mensagem=f"O item {item.numero_serie} está instalado na aeronave {matricula}.",
                requer_confirmacao=True,
                aeronave_conflito=matricula
            )
        _registrar_remocao(inst_conflito)
    return None

def _efetivar_troca_no_slot(
    db: AsyncSession,
    inst_atual: Instalacao | None,
    item_novo: ItemEquipamento,
    aeronave_id: uuid.UUID,
    slot_id: uuid.UUID,
    usuario_id: uuid.UUID | None,
) -> Instalacao:
    """Encerra a instalação atual do slot (se houver) e registra a nova."""
    hoje = date.today()
    if inst_atual:
        _registrar_remocao(inst_atual, hoje)

    nova_instalacao = Instalacao(
        id=uuid.uuid4(),
        item_id=item_novo.id,
        aeronave_id=aeronave_id,
        slot_id=slot_id,
        usuario_id=usuario_id,
        data_instalacao=hoje
    )
    db.add(nova_instalacao)
    return nova_instalacao


async def instalar_item(
    db: AsyncSession, item_id: uuid.UUID, aeronave_id: uuid.UUID, slot_id: uuid.UUID, data_instalacao: date, usuario_id: uuid.UUID
) -> Instalacao:
    """Instala um item em um slot, encerrando a instalação anterior do item.

    Raises:
        ConflitoNegocioError: já existe uma instalação ativa no slot/aeronave
            de destino (RISCO-05: corrida entre duas chamadas concorrentes).
    """
    stmt_old = select(Instalacao).where(Instalacao.item_id == item_id, Instalacao.data_remocao.is_(None))
    res_old = await db.execute(stmt_old)
    old_inst = res_old.scalar_one_or_none()
    if old_inst:
        _registrar_remocao(old_inst, data_instalacao)

    instalacao = Instalacao(
        id=uuid.uuid4(),
        item_id=item_id,
        aeronave_id=aeronave_id,
        slot_id=slot_id,
        usuario_id=usuario_id,
        data_instalacao=data_instalacao,
        created_at=func.now()
    )
    try:
        # SAVEPOINT: rede de segurança contra duas instalações concorrentes
        # no mesmo slot/aeronave (RISCO-05).
        async with db.begin_nested():
            db.add(instalacao)
            await db.flush()
    except IntegrityError as exc:
        logger.warning(
            "Conflito de instalação concorrente no slot %s da aeronave %s: %s",
            slot_id, aeronave_id, exc.orig,
        )
        raise domain_exc.ConflitoNegocioError(
            "Já existe uma instalação ativa neste slot para esta aeronave."
        ) from exc
    return instalacao

async def remover_item(db: AsyncSession, instalacao_id: uuid.UUID, data_remocao: date, usuario_id: uuid.UUID | None = None) -> Instalacao:
    """Registra a remoção de um item instalado.

    Raises:
        EntidadeNaoEncontradaError: instalação inexistente.
    """
    result = await db.execute(select(Instalacao).where(Instalacao.id == instalacao_id))
    instalacao = result.scalar_one_or_none()
    if not instalacao:
        raise domain_exc.EntidadeNaoEncontradaError("Instalação não encontrada.")

    _registrar_remocao(instalacao, data_remocao)
    if usuario_id:
        instalacao.usuario_id = usuario_id

    await db.flush()
    return instalacao

async def listar_historico_recente(db: AsyncSession, limit: int = 15, offset: int = 0) -> list[dict]:
    """Lista as últimas movimentações (instalações e remoções) do inventário.

    Instalações usam `created_at` como data do evento; remoções usam
    `removido_em` (timestamp dedicado, imune a updates posteriores no registro).
    """
    stmt_ins = (
        select(
            Instalacao.id.label("id"),
            Instalacao.created_at.label("event_at"),
            ItemEquipamento.numero_serie.label("item_sn"),
            Aeronave.matricula.label("aeronave_matricula"),
            SlotInventario.nome_posicao.label("slot_nome"),
            Usuario.trigrama.label("usuario_trigrama"),
            literal("INSTALAÇÃO").label("tipo_acao")
        )
        .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
        .join(SlotInventario, Instalacao.slot_id == SlotInventario.id)
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
    )

    stmt_rem = (
        select(
            Instalacao.id.label("id"),
            Instalacao.removido_em.label("event_at"),
            ItemEquipamento.numero_serie.label("item_sn"),
            Aeronave.matricula.label("aeronave_matricula"),
            SlotInventario.nome_posicao.label("slot_nome"),
            Usuario.trigrama.label("usuario_trigrama"),
            literal("REMOÇÃO").label("tipo_acao")
        )
        .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
        .join(SlotInventario, Instalacao.slot_id == SlotInventario.id)
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
        .where(Instalacao.data_remocao.is_not(None), Instalacao.removido_em.is_not(None))
    )

    query_union = union_all(stmt_ins, stmt_rem).alias("historico_union")
    stmt_final = select(
        query_union.c.id,
        query_union.c.event_at,
        query_union.c.item_sn,
        query_union.c.aeronave_matricula,
        query_union.c.slot_nome,
        query_union.c.usuario_trigrama,
        query_union.c.tipo_acao
    ).order_by(desc(query_union.c.event_at)).limit(limit).offset(offset)

    result = await db.execute(stmt_final)
    rows = result.all()

    return [
        {
            "id": r.id,
            "created_at": r.event_at,
            "item_sn": r.item_sn,
            "aeronave_matricula": r.aeronave_matricula,
            "slot_nome": r.slot_nome,
            "usuario_trigrama": r.usuario_trigrama,
            "tipo_acao": r.tipo_acao
        }
        for r in rows
    ]


# ============================================================
# Slots — CRUD completo (gestão administrativa)
# ============================================================

async def _ocupacao_slot(db: AsyncSession, slot_id: uuid.UUID) -> list[dict]:
    """Aeronaves com instalação vinculada a este slot, ativas e históricas."""
    res = await db.execute(
        select(Aeronave.matricula, Instalacao.data_remocao)
        .join(Instalacao, Instalacao.aeronave_id == Aeronave.id)
        .where(Instalacao.slot_id == slot_id)
    )
    return [{"aeronave": matricula, "ativa": remocao is None} for matricula, remocao in res.all()]


async def atualizar_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    dados: SlotInventarioUpdate,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
) -> SlotInventario:
    """Atualiza um slot.

    Trocar o `modelo_id` (PN esperado) é bloqueado enquanto houver instalação
    ativa: o slot é GLOBAL da frota, então a troca afetaria a leitura de PN de
    todas as aeronaves de uma vez, não de uma isolada.

    Raises:
        EntidadeNaoEncontradaError: slot ou novo `modelo_id` inexistente.
        ConflitoNegocioError: chave natural duplicada, ou troca de PN com
            instalação ativa.
    """
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")

    antes = auditoria_service.snapshot(slot)

    if dados.modelo_id is not None and dados.modelo_id != slot.modelo_id:
        res = await db.execute(
            select(Instalacao.id).where(
                Instalacao.slot_id == slot_id, Instalacao.data_remocao.is_(None)
            )
        )
        if res.first():
            raise domain_exc.ConflitoNegocioError(
                "Não é possível trocar o PN esperado: este slot tem instalação ativa "
                "em ao menos uma aeronave."
            )
        if not await db.get(ModeloEquipamento, dados.modelo_id):
            raise domain_exc.EntidadeNaoEncontradaError(
                f"Equipamento {dados.modelo_id} não encontrado."
            )
        slot.modelo_id = dados.modelo_id

    novo_nome = dados.nome_posicao if dados.nome_posicao is not None else slot.nome_posicao
    novo_sistema = dados.sistema if dados.sistema is not None else slot.sistema
    if (novo_nome, novo_sistema) != (slot.nome_posicao, slot.sistema):
        if await _slot_duplicado(db, novo_nome, novo_sistema, excluir_id=slot_id):
            raise domain_exc.ConflitoNegocioError(
                "Já existe um slot com este nome nesta localização."
            )

    for campo in ("nome_posicao", "sistema", "posicao_xlsx", "descricao", "ordem_exibicao"):
        valor = getattr(dados, campo)
        if valor is not None:
            setattr(slot, campo, valor)

    await db.flush()

    anteriores, novos = auditoria_service.diff_campos(antes, auditoria_service.snapshot(slot))
    if novos:
        await auditoria_service.registrar(
            db,
            entidade=EntidadeAuditada.SLOT,
            entidade_id=slot.id,
            acao=AcaoAuditoria.UPDATE,
            usuario_id=usuario_id,
            ip_origem=ip_origem,
            anteriores=anteriores,
            novos=novos,
        )
    return slot


async def remover_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    justificativa: str,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
) -> None:
    """Exclui fisicamente um slot sem nenhuma instalação vinculada.

    O critério é mais rígido que o de item (que só barra instalação ativa):
    apagar um slot com histórico levaria junto a rastreabilidade de toda a
    frota, não de uma linha isolada.

    Raises:
        EntidadeNaoEncontradaError: slot inexistente.
        ConflitoNegocioError: existe instalação, ativa ou histórica.
    """
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")

    ocupacao = await _ocupacao_slot(db, slot_id)
    if ocupacao:
        raise domain_exc.ConflitoNegocioError(
            f"Não é possível excluir: {len(ocupacao)} instalação(ões) vinculada(s) a "
            "este slot. Considere inativar o slot."
        )

    antes = auditoria_service.snapshot(slot)
    await db.delete(slot)
    await db.flush()
    await auditoria_service.registrar(
        db,
        entidade=EntidadeAuditada.SLOT,
        entidade_id=slot_id,
        acao=AcaoAuditoria.DELETE,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        anteriores=antes,
        justificativa=justificativa,
    )


async def _alternar_ativo_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    ativo: bool,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
) -> SlotInventario:
    """Liga/desliga um slot sem exigir ausência de instalações."""
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")
    if slot.ativo == ativo:
        return slot  # idempotente — não registra auditoria de não-mudança

    anterior = slot.ativo
    slot.ativo = ativo
    await db.flush()
    await auditoria_service.registrar(
        db,
        entidade=EntidadeAuditada.SLOT,
        entidade_id=slot_id,
        acao=AcaoAuditoria.UPDATE,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        anteriores={"ativo": anterior},
        novos={"ativo": ativo},
    )
    return slot


async def inativar_slot(
    db: AsyncSession, slot_id: uuid.UUID, usuario_id: uuid.UUID | None, ip_origem: str | None = None
) -> SlotInventario:
    """Desliga o slot preservando todo o histórico de instalações."""
    return await _alternar_ativo_slot(db, slot_id, False, usuario_id, ip_origem)


async def reativar_slot(
    db: AsyncSession, slot_id: uuid.UUID, usuario_id: uuid.UUID | None, ip_origem: str | None = None
) -> SlotInventario:
    """Contrapartida obrigatória de `inativar_slot`.

    Sem isto, um slot inativado sumiria das listagens e ficaria inacessível
    pela aplicação — inativar viraria uma operação sem volta.
    """
    return await _alternar_ativo_slot(db, slot_id, True, usuario_id, ip_origem)


# ============================================================
# Itens de Equipamento — CRUD completo (gestão administrativa)
# ============================================================

async def atualizar_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    dados: ItemEquipamentoUpdate,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
) -> ItemEquipamento:
    """Corrige S/N ou status de um item físico.

    Raises:
        EntidadeNaoEncontradaError: item inexistente.
        ConflitoNegocioError: novo S/N já usado por outro item do mesmo PN.
    """
    item = await db.get(ItemEquipamento, item_id)
    if not item:
        raise domain_exc.EntidadeNaoEncontradaError("Item não encontrado.")

    antes = auditoria_service.snapshot(item, ["numero_serie", "status"])

    if dados.numero_serie is not None and dados.numero_serie != item.numero_serie:
        if await _buscar_item_por_sn(db, item.modelo_id, dados.numero_serie):
            raise domain_exc.ConflitoNegocioError(
                f"S/N '{dados.numero_serie}' já cadastrado para este P/N."
            )
        item.numero_serie = dados.numero_serie
    if dados.status is not None:
        item.status = dados.status.value

    await db.flush()

    depois = auditoria_service.snapshot(item, ["numero_serie", "status"])
    anteriores, novos = auditoria_service.diff_campos(antes, depois)
    if novos:
        await auditoria_service.registrar(
            db,
            entidade=EntidadeAuditada.ITEM,
            entidade_id=item.id,
            acao=AcaoAuditoria.UPDATE,
            usuario_id=usuario_id,
            ip_origem=ip_origem,
            anteriores=anteriores,
            novos=novos,
        )
    return item


async def excluir_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    justificativa: str,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
) -> None:
    """Exclui fisicamente um item sem nenhum vínculo.

    Nome deliberadamente distinto de `remover_item` (que encerra a instalação
    ativa de um item, fluxo operacional usado por PATCH /instalacoes/{id}/remover).
    Reaproveitar aquele nome sobrescreveria o fluxo de desinstalação.

    Raises:
        EntidadeNaoEncontradaError: item inexistente.
        ConflitoNegocioError: existe instalação OU controle de vencimento
            vinculado ao item.
    """
    item = await db.get(ItemEquipamento, item_id)
    if not item:
        raise domain_exc.EntidadeNaoEncontradaError("Item não encontrado.")

    res = await db.execute(select(Instalacao.id).where(Instalacao.item_id == item_id))
    if res.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: este item tem instalação vinculada. "
            "Considere marcar o status como REMOVIDO."
        )

    # ControleVencimento.item_id é FK sem ondelete — sem esta checagem o
    # db.delete() estoura IntegrityError (500) em vez de devolver 409 com
    # explicação. E como `criar_item_com_heranca` cria controles herdados para
    # TODO item novo, este é o caminho comum, não a exceção.
    res_controles = await db.execute(
        select(ControleVencimento.id).where(ControleVencimento.item_id == item_id)
    )
    if res_controles.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: este item tem controles de vencimento (TBV/RBA) "
            "vinculados. Considere marcar o status como REMOVIDO."
        )

    antes = auditoria_service.snapshot(item, ["numero_serie", "modelo_id", "status"])
    await db.delete(item)
    await db.flush()
    await auditoria_service.registrar(
        db,
        entidade=EntidadeAuditada.ITEM,
        entidade_id=item_id,
        acao=AcaoAuditoria.DELETE,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        anteriores=antes,
        justificativa=justificativa,
    )
