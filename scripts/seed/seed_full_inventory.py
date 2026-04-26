import asyncio
import os
import sys
import uuid
from pathlib import Path
from datetime import date, datetime, timedelta
import random

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Carregar variáveis do .env
load_dotenv()

from sqlalchemy import select, delete
from app.bootstrap.database import get_session_factory, Base
from app.modules.auth.models import Usuario
from app.modules.aeronaves.models import Aeronave
from app.modules.panes.models import Pane
from app.modules.equipamentos.models import (
    ModeloEquipamento, SlotInventario, TipoControle, 
    EquipamentoControle, ItemEquipamento, Instalacao,
    ControleVencimento
)
from app.shared.core.enums import StatusVencimento, StatusItem, StatusAeronave

async def seed_full_inventory():
    print("Iniciando povoamento completo de inventário...")
    AsyncSessionLocal = get_session_factory()
    
    async with AsyncSessionLocal() as session:
        # 1. Buscar dados base
        res_acft = await session.execute(select(Aeronave))
        aeronaves = res_acft.scalars().all()
        
        res_slots = await session.execute(select(SlotInventario))
        slots = res_slots.scalars().all()
        
        res_regras = await session.execute(select(EquipamentoControle))
        regras = res_regras.scalars().all()
        
        # Agrupar regras por modelo_id para facilitar
        regras_por_modelo = {}
        for r in regras:
            if r.modelo_id not in regras_por_modelo:
                regras_por_modelo[r.modelo_id] = []
            regras_por_modelo[r.modelo_id].append(r)

        print(f"Encontradas {len(aeronaves)} aeronaves e {len(slots)} slots.")
        
        # 2. Limpar instalações e itens existentes para evitar conflitos
        print("Limpando dados antigos de instalações e itens...")
        await session.execute(delete(Instalacao))
        await session.execute(delete(ControleVencimento))
        await session.execute(delete(ItemEquipamento))
        await session.commit()

        # 3. Povoar cada aeronave
        for acft in aeronaves:
            print(f"Processando aeronave {acft.matricula}...")
            
            # (Removida verificação de existência para garantir re-povoamento completo)

            for slot in slots:
                # Criar Item Físico
                # Serial number composto: [Matricula]-[Posicao]-[Random]
                sn = f"{acft.matricula}-{slot.nome_posicao}-{random.randint(1000, 9999)}"
                
                item = ItemEquipamento(
                    modelo_id=slot.modelo_id,
                    numero_serie=sn,
                    status=StatusItem.ATIVO.value
                )
                session.add(item)
                await session.flush() # Para pegar o ID do item
                
                # Criar Instalação
                inst = Instalacao(
                    item_id=item.id,
                    aeronave_id=acft.id,
                    slot_id=slot.id,
                    data_instalacao=date.today() - timedelta(days=random.randint(1, 365))
                )
                session.add(inst)
                
                # Criar Controles de Vencimento baseados nas regras do modelo
                regras_modelo = regras_por_modelo.get(slot.modelo_id, [])
                for regra in regras_modelo:
                    # Calcular uma data de última execução aleatória no passado
                    dias_atras = random.randint(0, 500)
                    data_exec = date.today() - timedelta(days=dias_atras)
                    
                    # Calcular data de vencimento
                    data_venc = data_exec + timedelta(days=regra.periodicidade_meses * 30)
                    
                    # Status baseado na data de vencimento
                    status_venc = StatusVencimento.PENDENTE.value
                    if data_venc < date.today():
                        status_venc = StatusVencimento.VENCIDO.value
                    elif data_venc < date.today() + timedelta(days=30):
                        status_venc = StatusVencimento.PROXIMO.value
                    
                    venc = ControleVencimento(
                        item_id=item.id,
                        tipo_controle_id=regra.tipo_controle_id,
                        data_ultima_exec=data_exec,
                        data_vencimento=data_venc,
                        status=status_venc
                    )
                    session.add(venc)
            
            # Commit por aeronave para não pesar a transação
            await session.commit()
            print(f"Inventário da {acft.matricula} concluído.")

    print("Povoamento completo finalizado com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed_full_inventory())
