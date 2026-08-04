"""
app/aeronaves/service.py
Camada de serviço (regras de negócio) para gestão de aeronaves.
"""

import logging
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.aeronaves.schemas import AeronaveCreate, AeronaveUpdate
from app.shared.core.enums import StatusAeronave
from app.shared.core import exceptions as domain_exc
from app.shared.core import helpers

logger = logging.getLogger(__name__)


async def buscar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> Aeronave | None:
    """Busca uma aeronave pelo seu ID único."""
    result = await db.execute(select(Aeronave).where(Aeronave.id == aeronave_id))
    return result.scalar_one_or_none()


async def listar_aeronaves(
    db: AsyncSession,
    incluir_inativas: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> list[Aeronave]:
    """Retorna a lista de todas as aeronaves cadastradas.

    Apenas leitura (RISCO-03, docs/backlog/revisor/achados_aeronaves.md):
    antes, esta função também gravava no banco para "corrigir" o status de
    aeronaves com pane/inspeção órfã — efeito colateral inesperado num
    endpoint GET, e reimplementação incompleta (BUG-02) da regra canônica em
    `panes.service.sincronizar_status_aeronave`, já chamada em todos os
    pontos reais de mutação (abrir/concluir pane e inspeção).
    """
    query = select(Aeronave)
    if not incluir_inativas:
        query = query.where(Aeronave.status != StatusAeronave.INATIVA)
    result = await db.execute(query.order_by(Aeronave.matricula).offset(skip).limit(limit))
    return list(result.scalars().all())


async def alternar_status_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> Aeronave:
    """Alterna entre o status operacional atual e INATIVA.

    RISCO-05 (achados_aeronaves.md): ao inativar, o status atual é salvo em
    `status_anterior_inativacao` e restaurado ao reativar — antes, reativar
    sempre gravava DISPONIVEL, perdendo permanentemente um status como
    ESTOCADA.

    Raises:
        EntidadeNaoEncontradaError: aeronave inexistente.
        ConflitoNegocioError: aeronave sob inspeção ativa.
    """
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave não encontrada.")

    if aeronave.status == StatusAeronave.INSPECAO:
        raise domain_exc.ConflitoNegocioError(
            "Aeronave está sob inspeção ativa. Cancele ou conclua a inspeção antes de alterar o status para INATIVA."
        )

    if aeronave.status == StatusAeronave.INATIVA:
        aeronave.status = aeronave.status_anterior_inativacao or StatusAeronave.DISPONIVEL
        aeronave.status_anterior_inativacao = None
    else:
        # Antes de inativar, consultar se a aeronave possui alguma inspeção ativa (ABERTA ou EM_ANDAMENTO)
        from app.modules.inspecoes.models import Inspecao
        from app.modules.inspecoes.service import STATUS_ATIVOS
        query_ativa = select(Inspecao).where(
            Inspecao.aeronave_id == aeronave_id,
            Inspecao.status.in_(STATUS_ATIVOS)
        )
        res_ativa = await db.execute(query_ativa)
        if res_ativa.scalars().first():
            raise domain_exc.ConflitoNegocioError(
                "Aeronave está sob inspeção ativa. Cancele ou conclua a inspeção antes de alterar o status para INATIVA."
            )

        aeronave.status_anterior_inativacao = aeronave.status
        aeronave.status = StatusAeronave.INATIVA

    await db.flush()
    return aeronave


async def criar_aeronave(
    db: AsyncSession,
    dados: AeronaveCreate,
) -> Aeronave:
    """Cadastra uma nova aeronave no sistema.

    Raises:
        ConflitoNegocioError: matrícula ou serial number já cadastrados
            (checagem prévia ou violação de UNIQUE por criação concorrente);
            status INSPEÇÃO informado na criação (BUG-01 — a única fonte
            legítima desse status é o módulo de inspeções, mesma guarda já
            aplicada em `atualizar_aeronave`).
    """
    if dados.status == StatusAeronave.INSPECAO:
        raise domain_exc.ConflitoNegocioError(
            "Não é possível cadastrar uma aeronave já em INSPEÇÃO. Use o módulo de Inspeções."
        )

    # Verificar unicidade de matricula
    if await helpers.buscar_aeronave_por_matricula(db, dados.matricula):
        raise domain_exc.ConflitoNegocioError(f"Matrícula '{dados.matricula}' já cadastrada.")

    # Verificar unicidade de serial_number
    res_sn = await db.execute(select(Aeronave).where(Aeronave.serial_number == dados.serial_number))
    if res_sn.scalar_one_or_none():
        raise domain_exc.ConflitoNegocioError(f"Serial number '{dados.serial_number}' já cadastrado.")

    aeronave = Aeronave(**dados.model_dump())
    try:
        # SAVEPOINT: em caso de criação concorrente com a mesma matrícula/serial,
        # desfaz apenas este insert e mantém a transação da requisição utilizável.
        async with db.begin_nested():
            db.add(aeronave)
            await db.flush()
    except IntegrityError as exc:
        logger.warning(
            "Conflito de UNIQUE ao criar aeronave (matricula=%s, serial=%s): %s",
            dados.matricula, dados.serial_number, exc.orig,
        )
        raise domain_exc.ConflitoNegocioError(
            f"Matrícula '{dados.matricula}' ou serial number '{dados.serial_number}' já cadastrados."
        ) from exc
    return aeronave


async def atualizar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
    dados: AeronaveUpdate,
) -> Aeronave:
    """Atualiza os dados de uma aeronave existente.

    Raises:
        EntidadeNaoEncontradaError: aeronave inexistente.
        ConflitoNegocioError: transição de status inválida envolvendo
            INSPEÇÃO; matrícula/serial number já usados por outra aeronave
            (checagem prévia ou violação de UNIQUE por atualização concorrente).
    """
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave não encontrada.")

    changes = dados.model_dump(exclude_unset=True)

    if "status" in changes:
        novo_status = changes["status"]
        if novo_status == StatusAeronave.INSPECAO and aeronave.status != StatusAeronave.INSPECAO:
            raise domain_exc.ConflitoNegocioError(
                "Não é possível definir o status como INSPEÇÃO via edição manual. Use o módulo de Inspeções."
            )

        if aeronave.status == StatusAeronave.INSPECAO and novo_status != StatusAeronave.INSPECAO:
            raise domain_exc.ConflitoNegocioError(
                "Aeronave em inspeção ativa. Conclua a inspeção para alterar o status."
            )

    if "matricula" in changes and changes["matricula"] != aeronave.matricula:
        if await helpers.buscar_aeronave_por_matricula(db, changes["matricula"]):
            raise domain_exc.ConflitoNegocioError(f"Matrícula '{changes['matricula']}' já cadastrada.")

    if "serial_number" in changes and changes["serial_number"] != aeronave.serial_number:
        res_sn = await db.execute(select(Aeronave).where(Aeronave.serial_number == changes["serial_number"]))
        if res_sn.scalar_one_or_none():
            raise domain_exc.ConflitoNegocioError(f"Serial number '{changes['serial_number']}' já cadastrado.")

    for campo, valor in changes.items():
        setattr(aeronave, campo, valor)

    try:
        # SAVEPOINT: mesma rede de segurança de criar_aeronave, para o caso de
        # duas requisições concorrentes trocarem matrícula/serial para o
        # mesmo valor.
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao atualizar aeronave %s: %s", aeronave_id, exc.orig)
        raise domain_exc.ConflitoNegocioError(
            "Matrícula ou serial number já cadastrados para outra aeronave."
        ) from exc
    return aeronave
