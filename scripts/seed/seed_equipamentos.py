"""
scripts/seed/seed_equipamentos.py
Popula o catálogo base: ModeloEquipamento (PN) e SlotInventario (Posição).
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario

EQUIPAMENTOS_FICHA = [
    # 1P - POSTO DIANTEIRO
    {"posicao": "AMPMIC 1P", "nome": "AMPLIFICADOR MIC 1P", "pn": "263-000", "sistema": "1P"},
    {"posicao": "PDU", "nome": "PDU", "pn": "4455-1000-01", "sistema": "1P"},
    {"posicao": "UFCP", "nome": "UFCP", "pn": "4456-1000-02", "sistema": "1P"},
    {"posicao": "CHVC", "nome": "CHVC", "pn": "VEC00054", "sistema": "1P"},
    {"posicao": "CMFD1", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "1P"},
    {"posicao": "CMFD2", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "1P"},
    {"posicao": "ASP 1P", "nome": "ASP 1P", "pn": "343-001", "sistema": "1P"},
    {"posicao": "GPS", "nome": "GPS RECEIVER", "pn": "066-04031-1622", "sistema": "1P"},
    {"posicao": "PA CONTROL", "nome": "PA CONTROL", "pn": "449300-02-01", "sistema": "1P"},
    {"posicao": "PIC/NAV", "nome": "PAINEL PIC/NAV", "pn": "314-04895-403", "sistema": "1P"},
    {"posicao": "PUNHO DO MANCHE 1P", "nome": "PUNHO DO MANCHE 1P", "pn": "733-0402", "sistema": "1P"},
    {"posicao": "DVR", "nome": "DVR", "pn": "MB211E-03", "sistema": "1P"},

    # 2P - POSTO TRASEIRO
    {"posicao": "AMPMIC 2P", "nome": "AMPLIFICADOR MIC 2P", "pn": "263-000", "sistema": "2P"},
    {"posicao": "PSU", "nome": "PSU", "pn": "4458-1000-00", "sistema": "2P"},
    {"posicao": "CMFD3", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "2P"},
    {"posicao": "CMFD4", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "2P"},
    {"posicao": "ASP 2P", "nome": "ASP 2P", "pn": "343-001", "sistema": "2P"},
    {"posicao": "PUNHO DO MANCHE 2P", "nome": "PUNHO DO MANCHE 2P", "pn": "733-0402", "sistema": "2P"},

    # CEI - COMPARTIMENTO ELETRÔNICO INFERIOR
    {"posicao": "ADF", "nome": "ADF RECEIVER", "pn": "622-7382-101", "sistema": "CEI"},
    {"posicao": "DME", "nome": "DME RECEIVER", "pn": "622-7309-101", "sistema": "CEI"},
    {"posicao": "TDR", "nome": "TRANSPONDER", "pn": "622-9352-004", "sistema": "CEI"},
    {"posicao": "STORMSCOPE", "nome": "STORMSCOPE", "pn": "78-8060-6086-5", "sistema": "CEI"},
    {"posicao": "EGIR", "nome": "EGIR", "pn": "34200802-80RB", "sistema": "CEI"},
    {"posicao": "VOR", "nome": "VOR RECEIVER", "pn": "622-7194-201", "sistema": "CEI"},
    {"posicao": "MDP1", "nome": "MULTI-DISPLAY PROCESSOR", "pn": "MA902B-02", "sistema": "CEI"},
    {"posicao": "MDP2", "nome": "MULTI-DISPLAY PROCESSOR", "pn": "MA902B-02", "sistema": "CEI"},
    {"posicao": "ARTU", "nome": "ARTU", "pn": "251-118-012-012", "sistema": "CEI"},
    {"posicao": "AFDC", "nome": "AFDC", "pn": "449100-02-01", "sistema": "CEI"},
    {"posicao": "VUHF1", "nome": "VUHF RADIO", "pn": "6110.3001.12", "sistema": "CEI"},
    {"posicao": "VUHF2", "nome": "VUHF RADIO", "pn": "6106.7006.12", "sistema": "CEI"},

    # CES - COMPARTIMENTO ELETRÔNICO SUPERIOR
    {"posicao": "VADR", "nome": "VADR", "pn": "174521-10-01", "sistema": "CES"},
    {"posicao": "ELT", "nome": "ELT", "pn": "453-5000-710", "sistema": "CES"},
    {"posicao": "BEACON", "nome": "BEACON", "pn": "8888-8888", "sistema": "CES"},
]

async def run(session: AsyncSession):
    print(f"🚀 [Equipamentos] Garantindo catálogo de {len(EQUIPAMENTOS_FICHA)} PNs e Slots...")
    
    for data in EQUIPAMENTOS_FICHA:
        # Modelo (PN)
        res_mod = await session.execute(select(ModeloEquipamento).where(ModeloEquipamento.part_number == data["pn"]))
        modelo = res_mod.scalar_one_or_none()
        if not modelo:
            modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=data["pn"], nome_generico=data["nome"])
            session.add(modelo)
            await session.flush()

        # Slot
        res_slot = await session.execute(select(SlotInventario).where(SlotInventario.nome_posicao == data["posicao"]))
        slot = res_slot.scalar_one_or_none()
        if not slot:
            slot = SlotInventario(
                id=uuid.uuid4(),
                nome_posicao=data["posicao"],
                sistema=data["sistema"],
                modelo_id=modelo.id,
            )
            session.add(slot)
            await session.flush()
    
    await session.flush()
