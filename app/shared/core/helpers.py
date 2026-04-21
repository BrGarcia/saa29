"""
app/core/helpers.py
Funções utilitárias e helpers de busca para reduzir duplicação de código (DRY).
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import Usuario
from app.aeronaves.models import Aeronave

async def buscar_aeronave_por_matricula(db: AsyncSession, matricula: str) -> Aeronave | None:
    """Busca uma aeronave pela matrícula."""
    result = await db.execute(select(Aeronave).where(Aeronave.matricula == matricula))
    return result.scalar_one_or_none()

async def buscar_usuario_por_id(db: AsyncSession, usuario_id: uuid.UUID) -> Usuario | None:
    """Busca um usuário pelo ID."""
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    return result.scalar_one_or_none()

async def buscar_usuario_por_username(db: AsyncSession, username: str) -> Usuario | None:
    """Busca um usuário pelo username (case-insensitive)."""
    from sqlalchemy import func
    result = await db.execute(
        select(Usuario).where(func.lower(Usuario.username) == username.lower())
    )
    return result.scalar_one_or_none()
