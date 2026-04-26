"""
app/modules/efetivo/service.py
Camada de serviço para a gestão de disponibilidade de pessoal.
"""

import uuid
from datetime import date
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.efetivo.models import Indisponibilidade
from app.modules.efetivo.schemas import IndisponibilidadeCreate

async def registrar_indisponibilidade(db: AsyncSession, dados: IndisponibilidadeCreate) -> Indisponibilidade:
    # Verifica se a data fim é maior que a data inicio
    if dados.data_fim < dados.data_inicio:
        raise ValueError("A data de término não pode ser anterior à data de início.")

    # Verifica sobreposição de datas para o mesmo usuário
    stmt = select(Indisponibilidade).where(
        and_(
            Indisponibilidade.usuario_id == dados.usuario_id,
            Indisponibilidade.data_inicio <= dados.data_fim,
            Indisponibilidade.data_fim >= dados.data_inicio
        )
    )
    result = await db.execute(stmt)
    conflito = result.scalars().first()
    if conflito:
        raise ValueError("Já existe uma indisponibilidade registrada para este usuário no período informado.")

    indisp = Indisponibilidade(**dados.model_dump())
    db.add(indisp)
    await db.commit()
    await db.refresh(indisp)
    return indisp

async def listar_indisponibilidades_ativas(db: AsyncSession, data_ref: date | None = None) -> list[Indisponibilidade]:
    if not data_ref:
        data_ref = date.today()
    stmt = select(Indisponibilidade).where(
        and_(
            Indisponibilidade.data_inicio <= data_ref,
            Indisponibilidade.data_fim >= data_ref
        )
    ).options(selectinload(Indisponibilidade.usuario))
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def listar_indisponibilidades_por_usuario(db: AsyncSession, usuario_id: uuid.UUID) -> list[Indisponibilidade]:
    stmt = select(Indisponibilidade).where(
        Indisponibilidade.usuario_id == usuario_id
    ).order_by(Indisponibilidade.data_inicio.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def remover_indisponibilidade(db: AsyncSession, indisp_id: uuid.UUID) -> bool:
    indisp = await db.get(Indisponibilidade, indisp_id)
    if indisp:
        await db.delete(indisp)
        await db.commit()
        return True
    return False
