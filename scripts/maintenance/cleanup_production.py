"""
scripts/maintenance/cleanup_production.py
Script para remover dados de seed injetados acidentalmente em produção.
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import delete, select

# Ajustar PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.bootstrap.database import get_session_factory
from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario
from app.modules.calendario.models import EventType
from app.modules.inspecoes.models import SistemaATA

# Listas baseadas nos arquivos de seed
FROTA_PARA_REMOVER = [
    "5902", "5905", "5906", "5912", "5914", "5915", "5916", "5919", "5937", "5941",
    "5945", "5946", "5947", "5948", "5949", "5952", "5954", "5955", "5956", "5957",
    "5958", "5962",
]

async def cleanup():
    print("🧹 Iniciando limpeza de dados de seed em produção...")
    AsyncSessionLocal = get_session_factory()
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Remover Aeronaves
            print(f"🗑️ Removendo aeronaves da frota padrão...")
            stmt = delete(Aeronave).where(Aeronave.matricula.in_(FROTA_PARA_REMOVER))
            result = await session.execute(stmt)
            print(f"   Done: {result.rowcount} aeronaves removidas.")

            # 2. Remover Slots e Modelos (Catálogo)
            # Como slots dependem de modelos, removemos slots primeiro
            print(f"🗑️ Removendo slots e catálogo de equipamentos padrão...")
            # Aqui limpamos slots que não possuem registros vinculados (operação segura)
            # Para simplificar, vamos remover apenas os que foram criados pelos seeds 
            # (Identificados pelos PNs do seed_equipamentos)
            from scripts.seed.seed_equipamentos import EQUIPAMENTOS_FICHA
            pns_seed = [item["pn"] for item in EQUIPAMENTOS_FICHA]
            
            # Buscar IDs dos modelos para limpar slots vinculados
            res_mod = await session.execute(select(ModeloEquipamento.id).where(ModeloEquipamento.part_number.in_(pns_seed)))
            model_ids = res_mod.scalars().all()
            
            if model_ids:
                stmt_slots = delete(SlotInventario).where(SlotInventario.modelo_id.in_(model_ids))
                res_slots = await session.execute(stmt_slots)
                print(f"   Done: {res_slots.rowcount} slots de inventário removidos.")
                
                stmt_models = delete(ModeloEquipamento).where(ModeloEquipamento.id.in_(model_ids))
                res_models = await session.execute(stmt_models)
                print(f"   Done: {res_models.rowcount} modelos de equipamento removidos.")

            # 3. Remover Sistemas ATA
            print(f"🗑️ Removendo Sistemas ATA...")
            from scripts.seed.seed_sistemas_ata import ATA_DATA
            ata_codes = [item["codigo"] for item in ATA_DATA]
            stmt_ata = delete(SistemaATA).where(SistemaATA.codigo.in_(ata_codes))
            res_ata = await session.execute(stmt_ata)
            print(f"   Done: {res_ata.rowcount} sistemas ATA removidos.")

            # 4. Remover Tipos de Eventos do Calendário
            print(f"🗑️ Removendo tipos de eventos do calendário...")
            from scripts.seed.seed_calendario import BASE_EVENT_TYPES
            event_names = [item["name"] for item in BASE_EVENT_TYPES]
            stmt_events = delete(EventType).where(EventType.name.in_(event_names))
            res_events = await session.execute(stmt_events)
            print(f"   Done: {res_events.rowcount} tipos de eventos removidos.")

            await session.commit()
            print("\n✅ Limpeza concluída com sucesso!")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Erro durante a limpeza: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(cleanup())
