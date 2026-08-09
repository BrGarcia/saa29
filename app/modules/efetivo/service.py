"""
app/modules/efetivo/service.py
Camada de serviço para a gestão de disponibilidade de pessoal.
"""

import uuid
from datetime import date
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Usuario
from app.modules.efetivo.models import Indisponibilidade
from app.modules.efetivo.schemas import IndisponibilidadeCreate, IndisponibilidadeOut
from app.shared.core.enums import TipoIndisponibilidade


def _to_out(indisp: Indisponibilidade) -> IndisponibilidadeOut:
    """Serializa para saída pública, ocultando a observação de indisponibilidades
    do tipo PARTICULAR — para qualquer solicitante, dono ou não."""
    observacao = None if indisp.tipo == TipoIndisponibilidade.PARTICULAR.value else indisp.observacao
    return IndisponibilidadeOut(
        id=indisp.id,
        usuario_id=indisp.usuario_id,
        tipo=indisp.tipo,
        data_inicio=indisp.data_inicio,
        data_fim=indisp.data_fim,
        observacao=observacao,
        created_at=indisp.created_at,
    )


async def registrar_indisponibilidade(db: AsyncSession, dados: IndisponibilidadeCreate) -> IndisponibilidadeOut:
    # Verifica se a data fim é maior que a data inicio
    if dados.data_fim < dados.data_inicio:
        raise ValueError("A data de término não pode ser anterior à data de início.")

    usuario = await db.get(Usuario, dados.usuario_id)
    if usuario is None:
        raise ValueError("Usuário não encontrado.")

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
    await db.flush()
    return _to_out(indisp)

async def listar_indisponibilidades_ativas(db: AsyncSession, data_ref: date | None = None) -> list[IndisponibilidadeOut]:
    if not data_ref:
        data_ref = date.today()
    stmt = select(Indisponibilidade).where(
        and_(
            Indisponibilidade.data_inicio <= data_ref,
            Indisponibilidade.data_fim >= data_ref
        )
    )
    result = await db.execute(stmt)
    return [_to_out(i) for i in result.scalars().all()]

async def listar_indisponibilidades_por_usuario(db: AsyncSession, usuario_id: uuid.UUID) -> list[IndisponibilidadeOut]:
    stmt = select(Indisponibilidade).where(
        Indisponibilidade.usuario_id == usuario_id
    ).order_by(Indisponibilidade.data_inicio.desc())
    result = await db.execute(stmt)
    return [_to_out(i) for i in result.scalars().all()]

async def remover_indisponibilidade(db: AsyncSession, indisp_id: uuid.UUID) -> bool:
    indisp = await db.get(Indisponibilidade, indisp_id)
    if indisp:
        await db.delete(indisp)
        await db.flush()
        return True
    return False
