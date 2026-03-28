"""
app/aeronaves/service.py
Camada de serviço para gestão de aeronaves.
"""

import uuid
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aeronaves.models import Aeronave
from app.aeronaves.schemas import AeronaveCreate, AeronaveUpdate


_AERONAVES_CACHE: list[Aeronave] = []
_AERONAVES_CACHE_TIME: float = 0.0
_CACHE_TTL = 300  # 5 minutos

def _invalidar_cache():
    global _AERONAVES_CACHE_TIME
    _AERONAVES_CACHE_TIME = 0.0


async def listar_aeronaves(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Aeronave]:
    """
    Retorna a lista de todas as aeronaves cadastradas com paginação e cache (5 min TTL).

    Returns:
        Lista de objetos Aeronave.
    """
    global _AERONAVES_CACHE, _AERONAVES_CACHE_TIME
    agora = time.time()
    
    if _AERONAVES_CACHE and (agora - _AERONAVES_CACHE_TIME < _CACHE_TTL):
        return _AERONAVES_CACHE[skip : skip + limit]

    result = await db.execute(select(Aeronave).order_by(Aeronave.matricula))
    todas = list(result.scalars().all())
    
    _AERONAVES_CACHE = todas
    _AERONAVES_CACHE_TIME = agora
    
    return todas[skip : skip + limit]


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
    _invalidar_cache()
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
    _invalidar_cache()
    return aeronave


async def remover_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> None:
    """
    Remove uma aeronave do sistema.

    Raises:
        ValueError: se a aeronave não for encontrada ou possuir panes ou instalações vinculadas.
    """
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")

    # Verificar se existem panes vinculadas
    from app.panes.models import Pane
    res_panes = await db.execute(select(Pane).where(Pane.aeronave_id == aeronave_id).limit(1))
    if res_panes.scalar_one_or_none():
        raise ValueError("Não é possível remover: existem panes registradas para esta aeronave.")

    # Verificar se existem instalações vinculadas
    from app.equipamentos.models import Instalacao
    res_inst = await db.execute(select(Instalacao).where(Instalacao.aeronave_id == aeronave_id).limit(1))
    if res_inst.scalar_one_or_none():
        raise ValueError("Não é possível remover: existem equipamentos instalados ou com histórico nesta aeronave.")

    await db.delete(aeronave)
    _invalidar_cache()
