import asyncio
import os
import sys
import uuid
from pathlib import Path
from datetime import date, datetime

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Carregar variáveis do .env
load_dotenv()

from sqlalchemy import select
from app.bootstrap.database import get_session_factory, get_engine, Base
from app.modules.auth.service import garantir_usuarios_essenciais
from app.modules.aeronaves.models import Aeronave
from app.modules.panes.models import Pane
from app.modules.equipamentos.models import (
    ModeloEquipamento, SlotInventario, TipoControle, 
    EquipamentoControle, ItemEquipamento, Instalacao,
    ControleVencimento, ProrrogacaoVencimento
)
from app.shared.core.enums import StatusVencimento, StatusItem, StatusAeronave, OrigemControle

async def reset_db():
    print("Resetando banco de dados...")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Tabelas recriadas.")

async def seed():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Usuários (Admin e Teste)
        print("Povoando usuários essenciais...")
        await garantir_usuarios_essenciais(session)
        await session.flush()

        # 2. Tipos de Controle
        print("Criando tipos de controle...")
        tipos = {
            "CRI": TipoControle(nome="CRI", descricao="Inspeção Crítica do Equipamento"),
            "TLV": TipoControle(nome="TLV", descricao="Tempo de Limite de Vida"),
            "TBO": TipoControle(nome="TBO", descricao="Time Between Overhaul")
        }
        for t in tipos.values(): session.add(t)

        # 3. Modelos (PNs)
        print("Criando catálogo de PNs...")
        modelos_data = [
            {"nome": "MULTI-DISPLAY PROCESSOR", "pn": "MA902B-02"},
            {"nome": "EGIR", "pn": "34200802-80RB"},
            {"nome": "VADR", "pn": "174521-10-01"},
            {"nome": "ELT", "pn": "453-5000-710"},
            {"nome": "ADF RECEIVER", "pn": "622-7382-101"},
            {"nome": "DME RECEIVER", "pn": "622-7309-101"},
            {"nome": "TRANSPONDER", "pn": "622-9352-004"},
            {"nome": "VUHF RADIO", "pn": "6110.3001.12"},
            {"nome": "COLOR MULTI-FUNCTION DISPLAY", "pn": "MB387B-01"},
            {"nome": "BEACON", "pn": "8888-8888"}
        ]
        modelos = {}
        for m in modelos_data:
            mod = ModeloEquipamento(nome_generico=m["nome"], part_number=m["pn"])
            session.add(mod)
            modelos[m["pn"]] = mod
        
        await session.flush()

        # 4. Regras de Controle
        print("Criando regras de manutenção...")
        regras_data = [
            ("34200802-80RB", "TBO", 48),
            ("174521-10-01", "TLV", 60),
            ("174521-10-01", "CRI", 24),
            ("453-5000-710", "CRI", 12),
            ("MA902B-02", "CRI", 36)
        ]
        for pn, tipo, meses in regras_data:
            regra = EquipamentoControle(
                modelo_id=modelos[pn].id,
                tipo_controle_id=tipos[tipo].id,
                periodicidade_meses=meses
            )
            session.add(regra)

        # 5. Slots (Estrutura da Aeronave)
        print("Criando slots de inventário...")
        slots_data = [
            ("MDP1", "CEI", "MA902B-02"),
            ("MDP2", "CEI", "MA902B-02"),
            ("EGIR", "CEI", "34200802-80RB"),
            ("VADR", "CES", "174521-10-01"),
            ("ELT", "CES", "453-5000-710"),
            ("ADF", "CEI", "622-7382-101"),
            ("DME", "CEI", "622-7309-101"),
            ("TDR", "CEI", "622-9352-004"),
            ("VUHF1", "CEI", "6110.3001.12"),
            ("CMFD1", "1P", "MB387B-01"),
            ("CMFD2", "1P", "MB387B-01"),
            ("BEACON", "CES", "8888-8888")
        ]
        for pos, sis, pn in slots_data:
            slot = SlotInventario(
                nome_posicao=pos,
                sistema=sis,
                modelo_id=modelos[pn].id
            )
            session.add(slot)

        # 6. Aeronaves (Frota)
        print("Criando frota...")
        matriculas = [
            "5900", "5902", "5905", "5906", "5912", "5914", "5915", "5916", "5919", 
            "5937", "5941", "5945", "5946", "5947", "5949", "5952", "5954", "5955", 
            "5956", "5957", "5958", "5962"
        ]
        for mat in matriculas:
            acft = Aeronave(
                matricula=mat,
                serial_number=f"SN-{mat}",
                modelo="A-29",
                status=StatusAeronave.OPERACIONAL.value
            )
            session.add(acft)

        await session.commit()
        
        # 7. Itens e Instalações (Amostra para testes)
        print("Criando itens físicos e instalações de teste...")
        async with AsyncSessionLocal() as session:
            # Pegar 5900
            res = await session.execute(select(Aeronave).where(Aeronave.matricula == "5900"))
            acft_5900 = res.scalar_one()
            
            # Pegar Slots
            res_slots = await session.execute(select(SlotInventario))
            slots_list = res_slots.scalars().all()
            
            # Instalar alguns itens na 5900
            for slot in slots_list[:5]: # Instalar nos primeiros 5 slots
                # Criar Item
                item = ItemEquipamento(
                    modelo_id=slot.modelo_id,
                    numero_serie=f"SN-{slot.nome_posicao}-TEST",
                    status=StatusItem.ATIVO.value
                )
                session.add(item)
                await session.flush()
                
                # Instalar
                inst = Instalacao(
                    item_id=item.id,
                    aeronave_id=acft_5900.id,
                    slot_id=slot.id,
                    data_instalacao=date.today()
                )
                session.add(inst)
                
                # Criar Controles de Vencimento herdando do modelo
                res_reg = await session.execute(
                    select(EquipamentoControle).where(EquipamentoControle.modelo_id == slot.modelo_id)
                )
                regras = res_reg.scalars().all()
                for regra in regras:
                    venc = ControleVencimento(
                        item_id=item.id,
                        tipo_controle_id=regra.tipo_controle_id,
                        status=StatusVencimento.PENDENTE.value # Novo padrão
                    )
                    session.add(venc)

            await session.commit()
        
        print("Seed completo finalizado com sucesso!")

if __name__ == "__main__":
    asyncio.run(reset_db())
    asyncio.run(seed())
