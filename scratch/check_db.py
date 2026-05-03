import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from app.bootstrap.database import get_session_factory
from app.modules.inspecoes.models import TipoInspecao, Inspecao

async def check():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # Check types
        res = await session.execute(select(TipoInspecao))
        tipos = res.scalars().all()
        print(f"Tipos encontrados ({len(tipos)}):")
        for t in tipos:
            print(f" - {t.codigo}: {t.nome}")
        
        # Check active inspections
        res_ins = await session.execute(select(Inspecao))
        inspecoes = res_ins.scalars().all()
        print(f"\nInspeções ativas ({len(inspecoes)}):")
        for ins in inspecoes:
            print(f" - ID {ins.id} na aeronave {ins.aeronave_id}")

if __name__ == "__main__":
    asyncio.run(check())
