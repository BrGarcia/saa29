
import asyncio
import os
from dotenv import load_dotenv
from app.database import get_session_factory
from app.auth.security import hash_senha
from sqlalchemy import select

# Carregar variáveis do .env
load_dotenv()

# Importar TODOS os modelos para o SQLAlchemy resolver relacionamentos
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

from app.auth.models import Usuario

async def reset_admin():
    admin_user = os.getenv("DEFAULT_ADMIN_USER", "administrador").strip()
    admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123").strip()

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
