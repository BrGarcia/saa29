"""
scripts/seed/seed_slots.py
Popula os Slots de Inventário dependendo do catálogo de Modelos (PNs).
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario

SLOTS = [
    # CEI - COMPARTIMENTO ELETRONICO INFERIOR
    {"slot": "ADF", "pn": "622-7382-101", "loc": "CEI", "pos": "TEC"},
    {"slot": "DME", "pn": "622-7309-101", "loc": "CEI", "pos": "TEC"},
    {"slot": "TDR", "pn": "622-9352-004", "loc": "CEI", "pos": "TEC"},
    {"slot": "STORMSCOPE", "pn": "78-8060-6086-5", "loc": "CEI", "pos": "CEL"},
    {"slot": "EGIR", "pn": "34200802-80RB", "loc": "CEI", "pos": "FC"},
    {"slot": "VOR", "pn": "622-7194-201", "loc": "CEI", "pos": "TEC"},
    {"slot": "MDP1", "pn": "MA902B-01", "loc": "CEI", "pos": "EL1"},
    {"slot": "MDP2", "pn": "MA902B-01", "loc": "CEI", "pos": "EL2"},
    {"slot": "ARTU", "pn": "251-118-012-012", "loc": "CEI", "pos": "CEL"},
    {"slot": "AFDC", "pn": "449100-02-01", "loc": "CEI", "pos": "TEC"},
    {"slot": "VUHF1", "pn": "6110.3001.12", "loc": "CEI", "pos": "CEL"},
    {"slot": "VUHF2", "pn": "6106.7006.12", "loc": "CEI", "pos": "CEL"},

    # 1P - COMPARIMENTO DO 1P
    {"slot": "AMPMIC-1P", "pn": "263-000", "loc": "1P", "pos": "CAD"},
    {"slot": "PDU", "pn": "4455-1000-01", "loc": "1P", "pos": "P1P"},
    {"slot": "UFCP", "pn": "4456-1000-01", "loc": "1P", "pos": "P1P"},
    {"slot": "CHVC", "pn": "VEC00054", "loc": "1P", "pos": "P1P"},
    {"slot": "CMFD1", "pn": "MB387B-01", "loc": "1P", "pos": "MF1"},
    {"slot": "CMFD2", "pn": "MB387B-01", "loc": "1P", "pos": "MF2"},
    {"slot": "ASP-1P", "pn": "343-001", "loc": "1P", "pos": "P1P"},
    {"slot": "GPS", "pn": "066-04031-1622", "loc": "1P", "pos": "CAD"},
    {"slot": "PA CONTROL", "pn": "449300-02-01", "loc": "1P", "pos": "TC6"},
    {"slot": "PIC/NAV", "pn": "314-04895-401", "loc": "1P", "pos": "P1P"},
    {"slot": "STICKGRIP-1P", "pn": "733-0402", "loc": "1P", "pos": "CAD"},
    {"slot": "DVR", "pn": "MB211E-01", "loc": "1P", "pos": "CAD"},

    # 2P - COMPARTIMENTO DO 2P
    {"slot": "AMPMIC-2P", "pn": "263-000", "loc": "2P", "pos": "CAT"},
    {"slot": "PSU", "pn": "4458-1000-00", "loc": "2P", "pos": "FC"},
    {"slot": "CMFD3", "pn": "MB387B-01", "loc": "2P", "pos": "MF3"},
    {"slot": "CMFD4", "pn": "MB387B-01", "loc": "2P", "pos": "MF4"},
    {"slot": "ASP-2P", "pn": "343-001", "loc": "2P", "pos": "P2P"},
    {"slot": "STICKGRIP-2P", "pn": "733-0402", "loc": "2P", "pos": "CAT"},

    # CES - COMPARTIMENTO ELETRONICO SUPERIOR
    {"slot": "VADR", "pn": "174521-10-01", "loc": "CES", "pos": "FC"},
    {"slot": "ELT", "pn": "453-5000-710", "loc": "CES", "pos": "FC"},
    {"slot": "BEACON", "pn": "DK120", "loc": "CES", "pos": "FC"},
]

async def run(session: AsyncSession):
    print(f"🚀 [Slots] Garantindo mapa físico de {len(SLOTS)} Slots...")
    
    for data in SLOTS:
        # 1. Obter modelo
        res_mod = await session.execute(select(ModeloEquipamento).where(ModeloEquipamento.part_number == data["pn"]))
        modelo = res_mod.scalar_one_or_none()
        if not modelo:
             raise ValueError(f"ModeloEquipamento não encontrado para PN={data['pn']}. Rode seed_modelos primeiro.")
             
        # 2. Garantir Slot
        res_slot = await session.execute(
            select(SlotInventario).where(
                SlotInventario.nome_posicao == data["slot"],
                SlotInventario.sistema == data["loc"]
            )
        )
        slot = res_slot.scalar_one_or_none()
        
        if not slot:
            slot = SlotInventario(
                id=uuid.uuid4(),
                nome_posicao=data["slot"],
                sistema=data["loc"],
                posicao_xlsx=data.get("pos"),
                modelo_id=modelo.id,
            )
            session.add(slot)
            await session.flush()
    
    await session.commit()
    print("✅ Seed de Slots concluído.")
