"""
scripts/seed/seed.py
Orquestrador Principal de Carga de Dados.
Uso: python scripts/seed/seed.py
"""
import asyncio
import sys
import os
from pathlib import Path

# Ajustar PYTHONPATH para encontrar o módulo 'app'
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.bootstrap.database import get_session_factory, Base

# Importar os seeds individuais
from scripts.seed import (
    seed_auth,
    seed_aeronaves,
    seed_equipamentos,
    seed_vencimentos,
    seed_inventario,
    seed_panes
)

async def main():
    print("🌟 Iniciando Carga de Dados (Seed)...")
    
    AsyncSessionLocal = get_session_factory()
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Auth (Usuários base)
            await seed_auth.run(session)
            
            # 2. Aeronaves (Frota)
            await seed_aeronaves.run(session)
            
            # 3. Equipamentos (Catálogo/PNs/Slots)
            await seed_equipamentos.run(session)
            
            # 4. Inventário (Instalação física de Itens)
            await seed_inventario.run(session)
            
            # 5. Vencimentos (Regras/Periodicidades)
            await seed_vencimentos.run(session)
            
            # 6. Panes (Dados aleatórios para dashboard)
            await seed_panes.run(session)
            
            await session.commit()
            print("\n✅ Seed concluído com sucesso!")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Erro durante o seed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
