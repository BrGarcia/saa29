"""
scripts/init_db.py
Script de inicialização básica (Bootstrap) para o SAA29.
Garante a existência do usuário Admin e da Frota Padrão.
Seguro para rodar tanto em Dev quanto em Produção.
"""
import asyncio
import os
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
    from scripts.seed.seed_equipamentos import garantir_catalogo_e_slots
except (ImportError, ModuleNotFoundError):
    # Fallback para execução direta via python -m scripts.db.init_db
    from scripts.seed.seed_equipamentos import garantir_catalogo_e_slots

from app.bootstrap.database import get_session_factory
from app.modules.auth.security import hash_senha
from sqlalchemy import select

# Carregar variáveis do .env
load_dotenv()

# Importar TODOS os modelos para o SQLAlchemy Registry (SEC-02/COR-01)
import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.panes.models

from app.modules.auth.models import Usuario
from app.modules.aeronaves.models import Aeronave

FROTA_PADRAO = [
    "5902", "5905", "5906", "5912", "5914", "5915", "5916", "5919", "5937", "5941", "5945",
    "5946", "5947", "5949", "5952", "5954", "5955", "5956", "5957", "5958", "5962",
]


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}

async def init_db():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Garantir Usuários (Admin e Teste se dev)
        from app.modules.auth.service import garantir_usuarios_essenciais
        print("Garantindo usuários essenciais...")
        await garantir_usuarios_essenciais(session)
        await session.flush()

        # 1.1 Usuários de teste só podem ser criados com flag explícita
        app_env = os.getenv("APP_ENV", "production").strip().lower()
        enable_test_users = _env_flag("ENABLE_TEST_USERS", default=False)

        if app_env != "production" and enable_test_users:
            usuarios_teste = [
                {
                    "nome": "Encarregado Eletrônica",
                    "funcao": "ENCARREGADO",
                    "username": "encarregado",
                    "senha": "12345678",
                    "posto": "1S",
                    "especialidade": "BCO"
                },
                {
                    "nome": "Mantenedor Linha",
                    "funcao": "MANTENEDOR",
                    "username": "mantenedor",
                    "senha": "12345678",
                    "posto": "3S",
                    "especialidade": "BET"
                }
            ]

            for u in usuarios_teste:
                res_u = await session.execute(select(Usuario).where(Usuario.username == u["username"]))
                if not res_u.scalar_one_or_none():
                    print(f"➕ Criando usuário de teste: {u['username']}...")
                    novo_u = Usuario(
                        nome=u["nome"],
                        posto=u["posto"],
                        especialidade=u["especialidade"],
                        funcao=u["funcao"],
                        ramal="5678",
                        username=u["username"],
                        senha_hash=hash_senha(u["senha"]),
                    )
                    session.add(novo_u)
                else:
                    print(f"ℹ️ Usuário {u['username']} já existe.")
        else:
            print("⏭️ Criação de usuários de teste desabilitada.")

        # 2. Garantir Frota Padrão
        for matricula in FROTA_PADRAO:
            result = await session.execute(select(Aeronave).where(Aeronave.matricula == matricula))
            if not result.scalar_one_or_none():
                aeronave = Aeronave(
                    matricula=matricula,
                    serial_number=f"SN-{matricula}",
                    modelo="A-29"
                )
                session.add(aeronave)
                print(f"✅ Aeronave {matricula} adicionada.")

        # 3. Garantir catálogo base de equipamentos (sem serial/instalação)
        await garantir_catalogo_e_slots(session, create_sample_items=False)

        await session.commit()
        print(f"🚀 Inicialização do Banco concluída!")

if __name__ == "__main__":
    asyncio.run(init_db())
