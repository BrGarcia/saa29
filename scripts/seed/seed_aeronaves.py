"""
scripts/seed/seed_aeronaves.py
Popula a frota padrão de A-29.
"""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.aeronaves.models import Aeronave

FROTA_PADRAO = {
    "5902": "31400003",
    "5905": "31400008",
    "5906": "31400001",
    "5912": "31400016",
    "5914": "31400018",
    "5915": "31400019",
    "5916": "31400020",
    "5919": "31400023",
    "5937": "31400042",
    "5941": "31400048",
    "5945": "31400060",
    "5946": "31400069",
    "5947": "31400074",
    "5948": "31400079",
    "5949": "31400084",
    "5952": "31400106",
    "5954": "31400169",
    "5955": "31400113",
    "5956": "31400115",
    "5957": "31400116",
    "5958": "31400117",
    "5962": "31400121",
}

async def run(session: AsyncSession):
    print(f"🚀 [Aeronaves] Verificando frota de {len(FROTA_PADRAO)} aeronaves...")
    for matricula, serial in FROTA_PADRAO.items():
        res = await session.execute(select(Aeronave).where(Aeronave.matricula == matricula))
        if not res.scalar_one_or_none():
            acft = Aeronave(
                matricula=matricula,
                serial_number=serial,
                modelo="A-29",
                status="DISPONIVEL",
                horas_voo_total=0.0,
                data_inicio_operacao=date(2020, 1, 1)
            )
            session.add(acft)
            print(f"   + Aeronave {matricula} adicionada (S/N: {serial}).")
    await session.flush()
