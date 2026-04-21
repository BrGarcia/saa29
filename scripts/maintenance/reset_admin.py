
import asyncio
import os
from dotenv import load_dotenv
from app.bootstrap.database import get_session_factory
from app.modules.auth.security import hash_senha
from sqlalchemy import select

# Carregar variáveis do .env
load_dotenv()

# Importar TODOS os modelos para o SQLAlchemy resolver relacionamentos
import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.panes.models

from app.modules.auth.models import Usuario

async def reset_admin():
    # DEFAULT_ADMIN_PASSWORD MUST be set for security
    admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD")
    if not admin_pass:
        raise ValueError(
            "CRITICAL: DEFAULT_ADMIN_PASSWORD environment variable is not set.\n"
            "  - This is required for security (no hardcoded fallback).\n"
            "  - Set it before running reset_admin.py\n"
            "  - Example: export DEFAULT_ADMIN_PASSWORD='your_secure_password'"
        )
    
    admin_user = os.getenv("DEFAULT_ADMIN_USER", "administrador").strip()
    admin_pass = admin_pass.strip()

    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # Primeiro tenta encontrar pelo username definido no .env
        result = await session.execute(select(Usuario).where(Usuario.username == admin_user))
        admin = result.scalar_one_or_none()

        if not admin:
            # Se não achar pelo username, tenta encontrar qualquer usuário com função ADMINISTRADOR
            result = await session.execute(select(Usuario).where(Usuario.funcao == "ADMINISTRADOR"))
            admin = result.scalar_one_or_none()

        if not admin:
            print(f"❌ Nenhum administrador ({admin_user}) encontrado no banco.")
            return

        print(f"🔐 Resetando senha do usuário: {admin.username}...")
        admin.senha_hash = hash_senha(admin_pass)
        
        await session.commit()
        print(f"✅ Senha resetada com sucesso para o valor do .env!")

if __name__ == "__main__":
    asyncio.run(reset_admin())
