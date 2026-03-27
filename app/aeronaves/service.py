"""
app/aeronaves/service.py
Camada de serviço para gestão de aeronaves.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aeronaves.models import Aeronave
from app.aeronaves.schemas import AeronaveCreate, AeronaveUpdate


async def listar_aeronaves(db: AsyncSession) -> list[Aeronave]:
    """
    Retorna a lista de todas as aeronaves cadastradas.

    Returns:
        Lista de objetos Aeronave ordenada por matrícula.
    """
    result = await db.execute(select(Aeronave).order_by(Aeronave.matricula))
    return list(result.scalars().all())


async def criar_aeronave(
    db: AsyncSession,
    dados: AeronaveCreate,
) -> Aeronave:
    """
    Cadastra uma nova aeronave no sistema.

    Args:
        db: sessão de banco de dados.
        dados: schema com os dados da aeronave.

    Returns:
        Objeto Aeronave recém-criado.

    Raises:
        ValueError: se matrícula ou serial_number já existirem.
    """
    # Verificar unicidade de matricula
    result = await db.execute(
        select(Aeronave).where(Aeronave.matricula == dados.matricula)
    )
    if result.scalar_one_or_none():
        raise ValueError(f"Matrícula '{dados.matricula}' já cadastrada.")

    # Verificar unicidade de serial_number
    result = await db.execute(
        select(Aeronave).where(Aeronave.serial_number == dados.serial_number)
    )
    if result.scalar_one_or_none():
        raise ValueError(f"Serial number '{dados.serial_number}' já cadastrado.")

    aeronave = Aeronave(**dados.model_dump())
    db.add(aeronave)
    await db.flush()
    return aeronave


async def buscar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> Aeronave | None:
    """
    Busca uma aeronave pelo ID.

    Returns:
        Objeto Aeronave ou None se não encontrado.
    """
    result = await db.execute(
        select(Aeronave).where(Aeronave.id == aeronave_id)
    )
    return result.scalar_one_or_none()


async def atualizar_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
    dados: AeronaveUpdate,
) -> Aeronave:
    """
    Atualiza parcialmente os dados de uma aeronave.

    Raises:
        ValueError: se a aeronave não for encontrada.
    """
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(aeronave, campo, valor)
    await db.flush()
    return aeronave


async def remover_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> None:
    """
    Remove uma aeronave do sistema.

    Raises:
        ValueError: se a aeronave não for encontrada ou possuir panes abertas.
    """
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    await db.delete(aeronave)
