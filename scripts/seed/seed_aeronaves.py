"""
scripts/seed/seed_aeronaves.py
Popula a frota padrão de A-29.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.aeronaves.models import Aeronave

FROTA_PADRAO = [
    "5902", "5905", "5906", "5912", "5914", "5915", "5916", "5919", "5937", "5941", "5945",
    "5946", "5947", "5949", "5952", "5954", "5955", "5956", "5957", "5958", "5962",
]

async def run(session: AsyncSession):
    print(f"🚀 [Aeronaves] Verificando frota de {len(FROTA_PADRAO)} aeronaves...")
    for matricula in FROTA_PADRAO:
        res = await session.execute(select(Aeronave).where(Aeronave.matricula == matricula))
        if not res.scalar_one_or_none():
            acft = Aeronave(
                matricula=matricula,
                serial_number=f"SN-{matricula}",
                modelo="A-29",
                status="OPERACIONAL"
            )
            session.add(acft)
            print(f"   + Aeronave {matricula} adicionada.")
    await session.flush()
