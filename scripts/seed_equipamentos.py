"""
scripts/seed_equipamentos.py
Popula o banco de dados com equipamentos e itens baseados na ficha de inventário.
Alvo: Aeronave 5900 (Teste de Inventário)
Executar: python -m scripts.seed_equipamentos
"""
import asyncio
import uuid
from datetime import date
from sqlalchemy import select
from app.database import get_session_factory

# Importar TODOS os modelos para resolver referências do SQLAlchemy
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

from app.aeronaves.models import Aeronave
from app.equipamentos.models import Equipamento, ItemEquipamento, Instalacao, StatusItem

EQUIPAMENTOS_FICHA = [
    # COMP. ELETRONICO
    {"nome": "ADF", "pn": "622-7382-101", "sistema": "COMP. ELETRONICO"},
    {"nome": "DME", "pn": "622-7309-101", "sistema": "COMP. ELETRONICO"},
    {"nome": "TDR", "pn": "622-9352-004", "sistema": "COMP. ELETRONICO"},
    {"nome": "STORMSCOPE", "pn": "78-8060-6086-5", "sistema": "COMP. ELETRONICO"},
    {"nome": "EGIR", "pn": "34200802-80RB", "sistema": "COMP. ELETRONICO"},
    {"nome": "VOR", "pn": "622-7194-201", "sistema": "COMP. ELETRONICO"},
    {"nome": "MDP1", "pn": "MA902B-02", "sistema": "COMP. ELETRONICO"},
    {"nome": "MDP2", "pn": "MA902B-02", "sistema": "COMP. ELETRONICO"},
    {"nome": "ARTU", "pn": "251-118-012-012", "sistema": "COMP. ELETRONICO"},
    {"nome": "AFDC", "pn": "449100-02-01", "sistema": "COMP. ELETRONICO"},
    {"nome": "VUHF1", "pn": "6110.3001.12", "sistema": "COMP. ELETRONICO"},
    {"nome": "VUHF2", "pn": "6106.7006.12", "sistema": "COMP. ELETRONICO"},
    {"nome": "VUHF2 BAT", "pn": "0565.1687.00", "sistema": "COMP. ELETRONICO"},
    
    # POSTO DIANTEIRO (1P)
    {"nome": "AMPLIF. MIC 1P", "pn": "263-000", "sistema": "1P"},
    {"nome": "PDU", "pn": "4455-1000-01", "sistema": "1P"},
    {"nome": "UFCP", "pn": "4456-1000-02", "sistema": "1P"},
    {"nome": "CHVC", "pn": "VEC00054", "sistema": "1P"},
    {"nome": "CMFD1", "pn": "MB387B-01", "sistema": "1P"},
    {"nome": "CMFD2", "pn": "MB387B-01", "sistema": "1P"},
    {"nome": "ASP 1P", "pn": "343-001", "sistema": "1P"},
    {"nome": "GPS", "pn": "066-04031-1622", "sistema": "1P"},
    {"nome": "PA CONTROL", "pn": "449300-02-01", "sistema": "1P"},
    {"nome": "PAINEL PIC/NAV", "pn": "314-04895-403", "sistema": "1P"},
    {"nome": "PUNHO MANCHE 1P", "pn": "733-0402", "sistema": "1P"},
    {"nome": "DVR", "pn": "MB211E-03", "sistema": "1P"},

    # POSTO TRASEIRO (2P)
    {"nome": "AMPLIF. MIC 2P", "pn": "263-000", "sistema": "2P"},
    {"nome": "PSU", "pn": "4458-1000-00", "sistema": "2P"},
    {"nome": "CMFD3", "pn": "MB387B-01", "sistema": "2P"},
    {"nome": "CMFD4", "pn": "MB387B-01", "sistema": "2P"},
    {"nome": "ASP 2P", "pn": "343-001", "sistema": "2P"},
    {"nome": "PUNHO MANCHE 2P", "pn": "733-0402", "sistema": "2P"},

    # COMP. ELT/OBOGS
    {"nome": "VADR", "pn": "174521-10-01", "sistema": "COMP. ELT/OBOGS"},
    {"nome": "ELT", "pn": "453-5000-710", "sistema": "COMP. ELT/OBOGS"},
]

async def seed_equipamentos():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Garantir que a aeronave 5900 existe
        res_acft = await session.execute(select(Aeronave).where(Aeronave.matricula == "5900"))
        aeronave = res_acft.scalar_one_or_none()
        
        if not aeronave:
            print("✈️ Criando aeronave de teste 5900...")
            aeronave = Aeronave(
                id=uuid.uuid4(),
                matricula="5900",
                serial_number="SN-A29-TEST",
                modelo="A-29",
                status="OPERACIONAL"
            )
            session.add(aeronave)
            await session.flush()
        else:
            print("✅ Aeronave 5900 já existe.")

        # 2. Criar equipamentos e itens
        for eq_data in EQUIPAMENTOS_FICHA:
            # Verificar se equipamento (PN) já existe
            res_eq = await session.execute(
                select(Equipamento).where(Equipamento.part_number == eq_data["pn"], Equipamento.nome == eq_data["nome"])
            )
            equipamento = res_eq.scalar_one_or_none()
            
            if not equipamento:
                print(f"📦 Criando tipo: {eq_data['nome']} (PN: {eq_data['pn']})")
                equipamento = Equipamento(
                    id=uuid.uuid4(),
                    nome=eq_data["nome"],
                    part_number=eq_data["pn"],
                    sistema=eq_data["sistema"],
                    descricao=f"Equipamento {eq_data['nome']} da ficha de inventário"
                )
                session.add(equipamento)
                await session.flush()

            # Verificar se já existe item instalado desta aeronave para este equipamento
            res_inst = await session.execute(
                select(Instalacao)
                .join(ItemEquipamento)
                .where(
                    Instalacao.aeronave_id == aeronave.id,
                    ItemEquipamento.equipamento_id == equipamento.id,
                    Instalacao.data_remocao == None
                )
            )
            inst_ativa = res_inst.scalar_one_or_none()

            if not inst_ativa:
                # Criar um item físico (Serial Number aleatório para o seed)
                sn = f"SN-{eq_data['nome']}-{str(uuid.uuid4())[:8].upper()}"
                print(f"  🔧 Instalando item {sn} na 5900...")
                
                item = ItemEquipamento(
                    id=uuid.uuid4(),
                    equipamento_id=equipamento.id,
                    numero_serie=sn,
                    status=StatusItem.ATIVO
                )
                session.add(item)
                await session.flush()

                # Registrar instalação
                instalacao = Instalacao(
                    id=uuid.uuid4(),
                    item_id=item.id,
                    aeronave_id=aeronave.id,
                    data_instalacao=date.today()
                )
                session.add(instalacao)
        
        await session.commit()
        print("\n🚀 Seed de inventário concluído com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed_equipamentos())
