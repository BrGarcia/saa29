
import asyncio
from app.database import get_session_factory
from app.auth.security import hash_senha
from sqlalchemy import select

# Importar TODOS os modelos para o SQLAlchemy resolver relacionamentos
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

from app.auth.models import Usuario

async def reset_admin():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Usuario).where(Usuario.funcao == "ADMINISTRADOR"))
        admins = result.scalars().all()
        
        if not admins:
            print("❌ Nenhum administrador encontrado no banco.")
            return

        for admin in admins:
            print(f"🔐 Resetando senha do usuário: {admin.username} para 'admin123'")
            admin.senha_hash = hash_senha("admin123")
        
        await session.commit()
        print("✅ Senha resetada com sucesso!")

if __name__ == "__main__":
    asyncio.run(reset_admin())
