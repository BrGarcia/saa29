"""
scripts/seed/seed_equipamentos.py
Popula o catálogo base: ModeloEquipamento (PN) e SlotInventario (Posição).
Baseado em docs/legacy/inventario.md
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario

EQUIPAMENTOS_FICHA = [
    # CEI - COMPARTIMENTO ELETRONICO INFERIOR
    {"slot": "ADF", "equipamento": "ADF", "pn": "622-7382-101", "loc": "CEI"},
    {"slot": "DME", "equipamento": "DME", "pn": "622-7309-101", "loc": "CEI"},
    {"slot": "TDR", "equipamento": "TDR", "pn": "622-9352-004", "loc": "CEI"},
    {"slot": "STORMSCOPE", "equipamento": "STORMSCOPE", "pn": "78-8060-6086-5", "loc": "CEI"},
    {"slot": "EGIR", "equipamento": "EGIR", "pn": "34200802-80RB", "loc": "CEI"},
    {"slot": "VOR", "equipamento": "VOR", "pn": "622-7194-201", "loc": "CEI"},
    {"slot": "MDP1", "equipamento": "MDP", "pn": "MA902B-02", "loc": "CEI"},
    {"slot": "MDP2", "equipamento": "MDP", "pn": "MA902B-02", "loc": "CEI"},
    {"slot": "ARTU", "equipamento": "ARTU", "pn": "251-118-012-012", "loc": "CEI"},
    {"slot": "AFDC", "equipamento": "AFDC", "pn": "449100-02-01", "loc": "CEI"},
    {"slot": "VUHF1", "equipamento": "VUHF-1", "pn": "6110.3001.12", "loc": "CEI"},
    {"slot": "VUHF2", "equipamento": "VUHF-2", "pn": "6106.7006.12", "loc": "CEI"},

    # 1P - COMPARIMENTO DO 1P
    {"slot": "AMPMIC-1P", "equipamento": "AMPMIC", "pn": "263-000", "loc": "1P"},
    {"slot": "PDU", "equipamento": "PDU", "pn": "4455-1000-01", "loc": "1P"},
    {"slot": "UFCP", "equipamento": "UFCP", "pn": "4456-1000-02", "loc": "1P"},
    {"slot": "CHVC", "equipamento": "CHVC", "pn": "VEC00054", "loc": "1P"},
    {"slot": "CMFD1", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "1P"},
    {"slot": "CMFD2", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "1P"},
    {"slot": "ASP-1P", "equipamento": "ASP", "pn": "343-001", "loc": "1P"},
    {"slot": "GPS", "equipamento": "GPS STAND-ALONE", "pn": "066-04031-1622", "loc": "1P"},
    {"slot": "PA CONTROL", "equipamento": "PA CONTROL", "pn": "449300-02-01", "loc": "1P"},
    {"slot": "PIC/NAV", "equipamento": "PIC/NAV", "pn": "314-04895-403", "loc": "1P"},
    {"slot": "STICKGRIP-1P", "equipamento": "STICKGRIP", "pn": "733-0402", "loc": "1P"},
    {"slot": "DVR", "equipamento": "DVR", "pn": "MB211E-03", "loc": "1P"},

    # 2P - COMPARTIMENTO DO 2P
    {"slot": "AMPMIC-2P", "equipamento": "AMPMIC", "pn": "263-000", "loc": "2P"},
    {"slot": "PSU", "equipamento": "PSU", "pn": "4458-1000-00", "loc": "2P"},
    {"slot": "CMFD3", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "2P"},
    {"slot": "CMFD4", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "2P"},
    {"slot": "ASP-2P", "equipamento": "ASP", "pn": "343-001", "loc": "2P"},
    {"slot": "STICKGRIP-2P", "equipamento": "STICKGRIP", "pn": "733-0402", "loc": "2P"},

    # CES - COMPARIMENTO ELETRONICO SUPERIOR
    {"slot": "VADR", "equipamento": "VADR", "pn": "174521-10-01", "loc": "CES"},
    {"slot": "ELT", "equipamento": "ELT", "pn": "453-5000-710", "loc": "CES"},
    {"slot": "BEACON", "equipamento": "BEACON", "pn": "DK120", "loc": "CES"},
]

async def run(session: AsyncSession):
    print(f"🚀 [Equipamentos] Garantindo catálogo de {len(EQUIPAMENTOS_FICHA)} PNs e Slots...")
    
    for data in EQUIPAMENTOS_FICHA:
        # 1. Garantir Modelo (PN)
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
        
        # 2. Garantir Slot (Identificado por Loc + Slot para evitar colisões futuras)
        # Nota: Usamos o campo 'sistema' do modelo para armazenar a Localização ('loc')
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
                modelo_id=modelo.id,
            )
            session.add(slot)
            await session.flush()
    
    await session.commit()
    print("✅ Seed de equipamentos e slots concluído.")
