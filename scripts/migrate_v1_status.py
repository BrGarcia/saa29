"""
scripts/migrate_v1_status.py
Migração de dados para a v1.0: Converte panes 'EM_PESQUISA' para 'ABERTA'.
"""
import asyncio
from sqlalchemy import update
from app.bootstrap.database import get_session_factory

# Importar TODOS os módulos para resolver os nomes das classes em referências de string cruzadas
import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.panes.models

from app.modules.panes.models import Pane

async def migrate_status():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        print("🔄 Migrando panes 'EM_PESQUISA' para 'ABERTA'...")
        
        # O SQLAlchemy pode reclamar se usarmos o enum que não tem mais o valor,
        # então usamos a string literal para a migração.
        result = await session.execute(
            update(Pane)
            .where(Pane.status == "EM_PESQUISA")
            .values(status="ABERTA")
        )
        
        await session.commit()
        print(f"✅ Migração concluída. Linhas afetadas: {result.rowcount}")

if __name__ == "__main__":
    asyncio.run(migrate_status())
