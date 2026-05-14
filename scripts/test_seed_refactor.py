"""
Test script for the new seed isolation refactor.
It creates an isolated session, clears the target tables (slots and modelos),
and runs the two new seed files sequentially to verify success.
"""
import asyncio
import sys
import os
from sqlalchemy import text

# Add root to sys.path
sys.path.append(os.getcwd())

import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.panes.models
import app.modules.inspecoes.models
import app.modules.vencimentos.models
import app.modules.efetivo.models

from app.bootstrap.database import get_session_factory
from scripts.seed import seed_modelos, seed_slots

async def main():
    print("🔄 Iniciando teste isolado de refatoração de seeds...")
    AsyncSessionLocal = get_session_factory()
    
    async with AsyncSessionLocal() as session:
        print("🗑️ Limpando tabelas de modelos e slots temporariamente para teste...")
        await session.execute(text("PRAGMA foreign_keys=OFF"))
        await session.execute(text("DELETE FROM slots_inventario"))
        await session.execute(text("DELETE FROM modelos_equipamento"))
        await session.execute(text("PRAGMA foreign_keys=ON"))
        await session.commit()
        
        print("▶️ Rodando seed_modelos.py...")
        try:
            await seed_modelos.run(session)
            print("✔️ seed_modelos funcionou.")
        except Exception as e:
            print(f"❌ Falha em seed_modelos: {e}")
            return
            
        print("▶️ Rodando seed_slots.py...")
        try:
            await seed_slots.run(session)
            print("✔️ seed_slots funcionou.")
        except Exception as e:
            print(f"❌ Falha em seed_slots: {e}")
            return
            
    print("✅ Teste concluído com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
