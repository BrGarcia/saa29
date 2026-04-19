"""
scripts/seed_equipamentos.py
Popula o banco com a nova estrutura: ModeloEquipamento (PN) e SlotInventario (Posição).
"""
import asyncio
import uuid
from datetime import date
from sqlalchemy import select
from app.database import get_session_factory

# Importar modelos para garantir registro no SQLAlchemy
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

from app.aeronaves.models import Aeronave
from app.equipamentos.models import ModeloEquipamento, SlotInventario, ItemEquipamento, Instalacao, StatusItem

EQUIPAMENTOS_FICHA = [
    # COMP. ELETRONICO
    {"posicao": "ADF", "nome": "ADF RECEIVER", "pn": "622-7382-101", "sistema": "COMP. ELETRONICO"},
    {"posicao": "DME", "nome": "DME RECEIVER", "pn": "622-7309-101", "sistema": "COMP. ELETRONICO"},
    {"posicao": "TDR", "nome": "TRANSPONDER", "pn": "622-9352-004", "sistema": "COMP. ELETRONICO"},
    {"posicao": "STORMSCOPE", "nome": "STORMSCOPE", "pn": "78-8060-6086-5", "sistema": "COMP. ELETRONICO"},
    {"posicao": "EGIR", "nome": "EGIR", "pn": "34200802-80RB", "sistema": "COMP. ELETRONICO"},
    {"posicao": "VOR", "nome": "VOR RECEIVER", "pn": "622-7194-201", "sistema": "COMP. ELETRONICO"},
    {"posicao": "MDP1", "nome": "MULTI-DISPLAY PROCESSOR", "pn": "MA902B-02", "sistema": "COMP. ELETRONICO"},
    {"posicao": "MDP2", "nome": "MULTI-DISPLAY PROCESSOR", "pn": "MA902B-02", "sistema": "COMP. ELETRONICO"},
    {"posicao": "ARTU", "nome": "ARTU", "pn": "251-118-012-012", "sistema": "COMP. ELETRONICO"},
    {"posicao": "AFDC", "nome": "AFDC", "pn": "449100-02-01", "sistema": "COMP. ELETRONICO"},
    {"posicao": "VUHF1", "nome": "VUHF RADIO", "pn": "6110.3001.12", "sistema": "COMP. ELETRONICO"},
    {"posicao": "VUHF2", "nome": "VUHF RADIO", "pn": "6106.7006.12", "sistema": "COMP. ELETRONICO"},
    {"posicao": "VUHF2 BAT", "nome": "BATTERY", "pn": "0565.1687.00", "sistema": "COMP. ELETRONICO"},
    
    # POSTO DIANTEIRO (1P)
    {"posicao": "CMFD1", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "1P"},
    {"posicao": "CMFD2", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "1P"},
    {"posicao": "UFCP", "nome": "UFCP", "pn": "4456-1000-02", "sistema": "1P"},
    {"posicao": "GPS", "nome": "GPS RECEIVER", "pn": "066-04031-1622", "sistema": "1P"},
    {"posicao": "DVR", "nome": "DVR", "pn": "MB211E-03", "sistema": "1P"},

    # POSTO TRASEIRO (2P)
    {"posicao": "CMFD3", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "2P"},
    {"posicao": "CMFD4", "nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01", "sistema": "2P"},
]

async def seed():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Garantir aeronave 5916
        res_acft = await session.execute(select(Aeronave).where(Aeronave.matricula == "5916"))
        aeronave = res_acft.scalar_one_or_none()
        if not aeronave:
            aeronave = Aeronave(id=uuid.uuid4(), matricula="5916", serial_number="SN-5916", modelo="A-29", status="OPERACIONAL")
            session.add(aeronave)
            await session.flush()

        for data in EQUIPAMENTOS_FICHA:
            # 2. Criar Modelo (PN) se não existe
            res_mod = await session.execute(select(ModeloEquipamento).where(ModeloEquipamento.part_number == data["pn"]))
            modelo = res_mod.scalar_one_or_none()
            if not modelo:
                print(f"📦 Criando Modelo PN: {data['pn']} ({data['nome']})")
                modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=data["pn"], nome_generico=data["nome"])
                session.add(modelo)
                await session.flush()

            # 3. Criar Slot (Posição) se não existe
            res_slot = await session.execute(select(SlotInventario).where(SlotInventario.nome_posicao == data["posicao"]))
            slot = res_slot.scalar_one_or_none()
            if not slot:
                print(f"📍 Criando Slot: {data['posicao']}")
                slot = SlotInventario(id=uuid.uuid4(), nome_posicao=data["posicao"], sistema=data["sistema"], modelo_id=modelo.id)
                session.add(slot)
                await session.flush()

            # 4. Instalar um item físico na 5900 para teste
            sn = f"SN-{data['posicao']}-{str(uuid.uuid4())[:4].upper()}"
            item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=sn, status=StatusItem.ATIVO)
            session.add(item)
            await session.flush()

            instalacao = Instalacao(id=uuid.uuid4(), item_id=item.id, aeronave_id=aeronave.id, slot_id=slot.id, data_instalacao=date.today())
            session.add(instalacao)

        await session.commit()
        print("\n🚀 Seed estrutural concluído!")

if __name__ == "__main__":
    asyncio.run(seed())
