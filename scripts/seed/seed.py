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
    seed_panes,
    seed_tarefas,
    seed_inspecoes,
    seed_sistemas_ata,
    seed_calendario,
)

async def main():
    print("🌟 Iniciando Carga de Dados (Seed)...")
    
    from app.bootstrap.config import get_settings
    settings = get_settings()
    app_env = os.getenv("APP_ENV", "development").lower()
    
    AsyncSessionLocal = get_session_factory()
    
    async with AsyncSessionLocal() as session:
        try:
            # --- GRUPO 1: ESTRUTURA ESSENCIAL (Sempre carrega em qualquer ambiente) ---
            print("🚀 [Infra] Garantindo estrutura essencial (Admin, Frota, Slots, ATA)...")
            
            # 1. Auth (Admin sempre)
            await seed_auth.run(session)

            # 2. Aeronaves (Frota)
            await seed_aeronaves.run(session)
            
            # 3. Equipamentos (Catálogo/PNs/Slots)
            await seed_equipamentos.run(session)

            # 4. Sistemas ATA
            await seed_sistemas_ata.run(session)

            # 5. Calendario (Tipos base)
            await seed_calendario.run(session)

            # --- GRUPO 2: DADOS DE TESTE / MOCK (Bloqueado em Produção) ---
            if app_env != "production" or settings.enable_dev_seeds:
                print("🧪 [Mock] Modo Desenvolvimento: Carregando dados de teste...")
                
                # 6. Inventário (Instalação física de Itens)
                await seed_inventario.run(session)
                
                # 7. Vencimentos (Regras/Periodicidades)
                await seed_vencimentos.run(session)
                
                # 8. Panes (Dados aleatórios para dashboard)
                await seed_panes.run(session)
                
                # 9. Tarefas (Catálogo de tarefas e templates)
                await seed_tarefas.run(session)

                # 10. Inspeções (Instâncias de inspeção)
                await seed_inspecoes.run(session)
            else:
                print("🛡️ [Segurança] Modo Produção: Dados de teste bloqueados.")
            
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
