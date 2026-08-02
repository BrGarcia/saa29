"""
app/aeronaves/service.py
Camada de serviço (regras de negócio) para gestão de aeronaves.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.aeronaves.schemas import AeronaveCreate, AeronaveUpdate
from app.shared.core.enums import StatusAeronave
from app.shared.core import helpers


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
    """Retorna a lista de todas as aeronaves cadastradas."""
    query = select(Aeronave)
    if not incluir_inativas:
        query = query.where(Aeronave.status != StatusAeronave.INATIVA)
    result = await db.execute(query.order_by(Aeronave.matricula).offset(skip).limit(limit))
    aeronaves = list(result.scalars().all())

    # Garantir integridade do status da frota com panes e inspeções abertas
    if aeronaves:
        from app.modules.inspecoes.models import Inspecao
        from app.modules.inspecoes.service import STATUS_ATIVOS
        from app.modules.panes.models import Pane
        from app.shared.core.enums import StatusPane

        q_insp = select(Inspecao.aeronave_id).where(Inspecao.status.in_(STATUS_ATIVOS))
        inspecoes_ativas = set(str(i) for i in (await db.execute(q_insp)).scalars().all())

        q_panes = select(Pane.aeronave_id).where(Pane.status == StatusPane.ABERTA.value, Pane.ativo == True)
        panes_ativas = set(str(p) for p in (await db.execute(q_panes)).scalars().all())

        for a in aeronaves:
            ac_id_str = str(a.id)
            status_base = a.status.value if hasattr(a.status, 'value') else str(a.status)

            if ac_id_str in inspecoes_ativas:
                novo_status = StatusAeronave.INSPECAO
            elif ac_id_str in panes_ativas and status_base not in [StatusAeronave.INSPECAO.value, "INSPEÇÃO", StatusAeronave.INATIVA.value, StatusAeronave.ESTOCADA.value]:
                novo_status = StatusAeronave.INDISPONIVEL
            elif status_base == StatusAeronave.INDISPONIVEL.value and ac_id_str not in panes_ativas and ac_id_str not in inspecoes_ativas:
                novo_status = StatusAeronave.DISPONIVEL
            else:
                novo_status = None

            if novo_status and a.status != novo_status:
                a.status = novo_status
                db.add(a)

        await db.flush()

    return aeronaves


async def alternar_status_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> Aeronave:
    """Alterna entre OPERACIONAL e INATIVA."""
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    
    if aeronave.status == StatusAeronave.INSPECAO:
        raise ValueError("Aeronave está sob inspeção ativa. Cancele ou conclua a inspeção antes de alterar o status para INATIVA.")
        
    if aeronave.status == StatusAeronave.INATIVA:
        aeronave.status = StatusAeronave.DISPONIVEL
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
            raise ValueError("Aeronave está sob inspeção ativa. Cancele ou conclua a inspeção antes de alterar o status para INATIVA.")
        
        aeronave.status = StatusAeronave.INATIVA
        
    await db.flush()
    return aeronave


async def criar_aeronave(
    db: AsyncSession,
    dados: AeronaveCreate,
) -> Aeronave:
    """Cadastra uma nova aeronave no sistema."""
    # Verificar unicidade de matricula
    if await helpers.buscar_aeronave_por_matricula(db, dados.matricula):
        raise ValueError(f"Matrícula '{dados.matricula}' já cadastrada.")

    # Verificar unicidade de serial_number
    res_sn = await db.execute(select(Aeronave).where(Aeronave.serial_number == dados.serial_number))
    if res_sn.scalar_one_or_none():
        raise ValueError(f"Serial number '{dados.serial_number}' já cadastrado.")

    aeronave = Aeronave(**dados.model_dump())
    db.add(aeronave)
    await db.flush()
    return aeronave


async def atualizar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
    dados: AeronaveUpdate,
) -> Aeronave:
    """Atualiza os dados de uma aeronave existente."""
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    
    changes = dados.model_dump(exclude_unset=True)

    if "status" in changes:
        novo_status = changes["status"]
        if novo_status == StatusAeronave.INSPECAO and aeronave.status != StatusAeronave.INSPECAO:
             raise ValueError("Não é possível definir o status como INSPEÇÃO via edição manual. Use o módulo de Inspeções.")
        
        if aeronave.status == StatusAeronave.INSPECAO and novo_status != StatusAeronave.INSPECAO:
             raise ValueError("Aeronave em inspeção ativa. Conclua a inspeção para alterar o status.")

    if "matricula" in changes and changes["matricula"] != aeronave.matricula:
        if await helpers.buscar_aeronave_por_matricula(db, changes["matricula"]):
            raise ValueError(f"Matrícula '{changes['matricula']}' já cadastrada.")

    if "serial_number" in changes and changes["serial_number"] != aeronave.serial_number:
        res_sn = await db.execute(select(Aeronave).where(Aeronave.serial_number == changes["serial_number"]))
        if res_sn.scalar_one_or_none():
            raise ValueError(f"Serial number '{changes['serial_number']}' já cadastrado.")

    for campo, valor in changes.items():
        setattr(aeronave, campo, valor)
    await db.flush()
    return aeronave


async def desativar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> None:
    """Marca uma aeronave como inativa (soft delete operacional)."""
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    aeronave.status = StatusAeronave.INATIVA
    await db.flush()


async def reativar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> None:
    """Restaura uma aeronave inativa para o status operacional."""
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    aeronave.status = StatusAeronave.DISPONIVEL
    await db.flush()
