"""
scripts/seed/seed_modelos.py
Popula o catálogo base: ModeloEquipamento (PN).
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.equipamentos.models import ModeloEquipamento

MODELOS = [
    {"pn": "622-7382-101", "equipamento": "ADF"},
    {"pn": "622-7309-101", "equipamento": "DME"},
    {"pn": "622-9352-004", "equipamento": "TDR"},
    {"pn": "78-8060-6086-5", "equipamento": "STORMSCOPE"},
    {"pn": "34200802-80RB", "equipamento": "EGIR"},
    {"pn": "622-7194-201", "equipamento": "VOR"},
    {"pn": "MA902B-01", "equipamento": "MDP"},
    {"pn": "251-118-012-012", "equipamento": "ARTU"},
    {"pn": "449100-02-01", "equipamento": "AFDC"},
    {"pn": "6110.3001.12", "equipamento": "VUHF-1"},
    {"pn": "6106.7006.12", "equipamento": "VUHF-2"},
    {"pn": "263-000", "equipamento": "AMPMIC"},
    {"pn": "4455-1000-01", "equipamento": "PDU"},
    {"pn": "4456-1000-01", "equipamento": "UFCP"},
    {"pn": "VEC00054", "equipamento": "CHVC"},
    {"pn": "MB387B-01", "equipamento": "CMFD"},
    {"pn": "343-001", "equipamento": "ASP"},
    {"pn": "066-04031-1622", "equipamento": "GPS STAND-ALONE"},
    {"pn": "449300-02-01", "equipamento": "PA CONTROL"},
    {"pn": "314-04895-401", "equipamento": "PIC/NAV"},
    {"pn": "733-0402", "equipamento": "STICKGRIP"},
    {"pn": "MB211E-01", "equipamento": "DVR"},
    {"pn": "4458-1000-00", "equipamento": "PSU"},
    {"pn": "174521-10-01", "equipamento": "VADR"},
    {"pn": "453-5000-710", "equipamento": "ELT"},
    {"pn": "DK120", "equipamento": "BEACON"},
]

async def run(session: AsyncSession):
    print(f"🚀 [Modelos] Garantindo catálogo de {len(MODELOS)} PNs únicos...")
    
    for data in MODELOS:
        res_mod = await session.execute(select(ModeloEquipamento).where(ModeloEquipamento.part_number == data["pn"]))
        modelo = res_mod.scalar_one_or_none()
        if not modelo:
            modelo = ModeloEquipamento(
                id=uuid.uuid4(), 
                part_number=data["pn"], 
                nome_generico=data["equipamento"]
            )
            session.add(modelo)
            await session.flush()
    
    await session.commit()
    print("✅ Seed de Modelos (PNs) concluído.")
