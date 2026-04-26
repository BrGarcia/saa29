"""
scripts/seed/seed_auth.py
Garante a existência dos usuários base (Admin e Teste).
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.service import garantir_usuarios_essenciais

async def run(session: AsyncSession):
    print("🚀 [Auth] Garantindo usuários essenciais...")
    await garantir_usuarios_essenciais(session)
    await session.flush()
