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
        query = query.where(Aeronave.status != StatusAeronave.INATIVA.value)
    result = await db.execute(query.order_by(Aeronave.matricula).offset(skip).limit(limit))
    return list(result.scalars().all())


async def alternar_status_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> Aeronave:
    """Alterna entre OPERACIONAL e INATIVA."""
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    
    if aeronave.status == StatusAeronave.INATIVA.value:
        aeronave.status = StatusAeronave.OPERACIONAL.value
    else:
        aeronave.status = StatusAeronave.INATIVA.value
        
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
        if aeronave.status == StatusAeronave.INATIVA.value:
            raise ValueError("Aeronave inativa só pode ser reativada pela ação de reativar.")
        if novo_status == StatusAeronave.INATIVA:
            raise ValueError("Use a ação de desativar para tornar a aeronave inativa.")

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
    aeronave.status = StatusAeronave.INATIVA.value
    await db.flush()


async def reativar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> None:
    """Restaura uma aeronave inativa para o status operacional."""
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    aeronave.status = StatusAeronave.OPERACIONAL.value
    await db.flush()
