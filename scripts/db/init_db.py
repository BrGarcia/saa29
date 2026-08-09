"""
scripts/init_db.py
Script de inicialização básica (Bootstrap) para o SAA29.
Garante a existência do usuário Admin e da Frota Padrão.
Seguro para rodar tanto em Dev quanto em Produção.
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from scripts.seed import seed_equipamentos, seed_aeronaves, seed_sistemas_ata, seed_vencimentos, seed_inspecoes, seed_calendario
except (ImportError, ModuleNotFoundError):
    # Fallback para execução direta via python -m scripts.db.init_db
    from scripts.seed import seed_equipamentos, seed_aeronaves, seed_sistemas_ata, seed_vencimentos, seed_inspecoes, seed_calendario

from app.bootstrap.database import get_session_factory, get_engine, Base

# Importar TODOS os modelos para o SQLAlchemy Registry (SEC-02/COR-01)
import app.modules.auth.models         # noqa: F401
import app.modules.efetivo.models      # noqa: F401
import app.modules.aeronaves.models    # noqa: F401
import app.modules.equipamentos.models # noqa: F401
import app.modules.vencimentos.models  # noqa: F401
import app.modules.panes.models        # noqa: F401
import app.modules.inspecoes.models    # noqa: F401
import app.modules.calendario.models   # noqa: F401
import app.modules.publicacoes.models  # noqa: F401


async def init_db():
    # Garantir que todas as tabelas fisicas existam no banco
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Garantir Usuários (Admin sempre)
        from app.modules.auth.service import garantir_usuarios_essenciais
        print("Garantindo usuários essenciais...")
        await garantir_usuarios_essenciais(session)
        await session.flush()

        # 2. Garantir Frota Padrão (Chamando seed centralizado)
        await seed_aeronaves.run(session)

        # 3. Garantir catálogo base de equipamentos (sem serial/instalação)
        await seed_equipamentos.run(session)

        # 4. Garantir catálogo de Sistemas ATA
        await seed_sistemas_ata.run(session)

        # 5. Garantir Tipos de Inspeção (Estrutura)
        await seed_inspecoes.run(session)

        # 6. Garantir Tipos de Controle (Vencimentos)
        await seed_vencimentos.run(session)

        # 7. Garantir Tipos de Calendário
        await seed_calendario.run(session)

        await session.commit()
        print("🚀 Inicialização do Banco concluída!")

if __name__ == "__main__":
    asyncio.run(init_db())
