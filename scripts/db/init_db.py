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

from app.bootstrap.database import get_session_factory

# Carregar variáveis do .env
load_dotenv()

# Importar TODOS os modelos para o SQLAlchemy Registry (SEC-02/COR-01)
import app.modules.inspecoes.models
import app.modules.auth.models
import app.modules.efetivo.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.vencimentos.models
import app.modules.panes.models

from app.modules.aeronaves.models import Aeronave

# (Removido duplicidade de FROTA_PADRAO)

async def init_db():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Garantir Usuários (Admin sempre; usuários de teste só se
        # APP_ENV=development E ENABLE_TEST_USERS=true — ver
        # garantir_usuarios_essenciais, que é a única fonte desta lógica
        # desde a correção do item #4/Etapa 4 (antes havia uma segunda
        # implementação duplicada e divergente aqui, com usuários e senhas
        # diferentes dos criados por garantir_usuarios_essenciais).
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
        # await seed_calendario.run(session)

        await session.commit()
        print(f"🚀 Inicialização do Banco concluída!")

if __name__ == "__main__":
    asyncio.run(init_db())
