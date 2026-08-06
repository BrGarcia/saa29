"""
scripts/maintenance/cleanup_production.py
Script para remover dados de seed injetados acidentalmente em produção.
"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import delete

# Ajustar PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.bootstrap.database import get_session_factory

# Listas baseadas nos arquivos de seed
FROTA_PARA_REMOVER = [
    "5902", "5905", "5906", "5912", "5914", "5915", "5916", "5919", "5937", "5941",
    "5945", "5946", "5947", "5948", "5949", "5952", "5954", "5955", "5956", "5957",
    "5958", "5962",
]

async def cleanup():
    print("🧹 Iniciando limpeza de dados de MOCK (Teste) em produção...")
    print("⚠️  Preservando: Aeronaves, Slots de Equipamento e Sistemas ATA.")
    AsyncSessionLocal = get_session_factory()
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Remover Panes de Teste
            print("🗑️ Removendo Panes de teste...")
            from app.modules.panes.models import Pane
            stmt_panes = delete(Pane)
            res_panes = await session.execute(stmt_panes)
            print(f"   Done: {res_panes.rowcount} panes removidas.")

            # 2. Remover Inspeções e Tarefas de Teste
            print("🗑️ Removendo Inspeções e registros de tarefas...")
            from app.modules.inspecoes.models import Inspecao, InspecaoTarefa
            await session.execute(delete(InspecaoTarefa))
            res_insp = await session.execute(delete(Inspecao))
            print(f"   Done: {res_insp.rowcount} inspeções removidas.")

            # 3. Remover Itens Instalados (Inventário) - Preservando os Slots
            print("🗑️ Removendo itens instalados nos slots (Inventário)...")
            from app.modules.equipamentos.models import ItemEquipamento
            res_items = await session.execute(delete(ItemEquipamento))
            print(f"   Done: {res_items.rowcount} itens físicos removidos (Slots agora estão vazios).")

            # 4. Remover Usuários de Teste
            print("🗑️ Removendo usuários de teste (mantendo admin)...")
            from app.modules.auth.models import Usuario
            USUARIOS_TESTE = ["encarregado", "inspetor", "mantenedor"]
            stmt_users = delete(Usuario).where(Usuario.username.in_(USUARIOS_TESTE))
            res_users = await session.execute(stmt_users)
            print(f"   Done: {res_users.rowcount} usuários de teste removidos.")

            await session.commit()
            print("\n✅ Limpeza de dados de teste concluída!")
            print("🚀 A estrutura básica (Frota, Slots e ATA) foi MANTIDA.")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Erro durante a limpeza: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(cleanup())
