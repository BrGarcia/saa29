"""
app/aeronaves/service.py
Camada de serviço para gestão de aeronaves.
"""

import uuid

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.aeronaves.models import Aeronave
from app.aeronaves.schemas import AeronaveCreate, AeronaveUpdate
from app.core.enums import StatusAeronave

async def listar_aeronaves(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    incluir_inativas: bool = False,
) -> list[Aeronave]:
    """
    Retorna a lista de todas as aeronaves cadastradas com paginação.

    Returns:
        Lista de objetos Aeronave.
    """
    query = select(Aeronave)
    if not incluir_inativas:
        query = query.where(Aeronave.status != StatusAeronave.INATIVA.value)
    result = await db.execute(
        query.order_by(Aeronave.matricula).offset(skip).limit(limit)
    )
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
    changes = dados.model_dump(exclude_unset=True)

    if "status" in changes:
        novo_status = changes["status"]
        if aeronave.status == StatusAeronave.INATIVA.value:
            raise ValueError("Aeronave inativa só pode ser reativada pela ação de reativar.")
        if novo_status == StatusAeronave.INATIVA:
            raise ValueError("Use a ação de desativar para tornar a aeronave inativa.")

    if "matricula" in changes and changes["matricula"] != aeronave.matricula:
        result = await db.execute(
            select(Aeronave).where(Aeronave.matricula == changes["matricula"])
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Matrícula '{changes['matricula']}' já cadastrada.")

    if "serial_number" in changes and changes["serial_number"] != aeronave.serial_number:
        result = await db.execute(
            select(Aeronave).where(Aeronave.serial_number == changes["serial_number"])
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Serial number '{changes['serial_number']}' já cadastrado.")

    for campo, valor in changes.items():
        setattr(aeronave, campo, valor)
    await db.flush()
    return aeronave


async def alternar_status_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
) -> Aeronave:
    """
    Alterna o estado administrativo entre ativa e inativa.
    """
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    aeronave.status = (
        StatusAeronave.OPERACIONAL.value
        if aeronave.status == StatusAeronave.INATIVA.value
        else StatusAeronave.INATIVA.value
    )
    await db.flush()
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

    # Verificar se existem panes vinculadas, distinguindo ativas de inativas
    from app.panes.models import Pane
    res_panes = await db.execute(
        select(
            func.count(Pane.id).label("total"),
            func.sum(case((Pane.ativo == True, 1), else_=0)).label("ativas"),  # noqa: E712
            func.sum(case((Pane.ativo == False, 1), else_=0)).label("inativas"),  # noqa: E712
        ).where(Pane.aeronave_id == aeronave_id)
    )
    total_panes, panes_ativas, panes_inativas = res_panes.one()
    total_panes = int(total_panes or 0)
    panes_ativas = int(panes_ativas or 0)
    panes_inativas = int(panes_inativas or 0)
    if total_panes:
        if panes_ativas and panes_inativas:
            raise ValueError(
                f"Não é possível remover: existem {panes_ativas} pane(s) ativa(s) e "
                f"{panes_inativas} pane(s) inativa(s)/excluída(s) vinculadas a esta aeronave."
            )
        if panes_ativas:
            raise ValueError(
                f"Não é possível remover: existem {panes_ativas} pane(s) ativa(s) vinculadas a esta aeronave."
            )
        raise ValueError(
            f"Não é possível remover: existem {panes_inativas} pane(s) inativa(s)/excluída(s) vinculadas a esta aeronave."
        )

    # Verificar se existem instalações vinculadas
    from app.equipamentos.models import Instalacao
    res_inst = await db.execute(select(Instalacao).where(Instalacao.aeronave_id == aeronave_id).limit(1))
    if res_inst.scalar_one_or_none():
        raise ValueError("Não é possível remover: existem equipamentos instalados ou com histórico nesta aeronave.")

    await db.delete(aeronave)
