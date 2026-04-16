"""
scripts/init_db.py
Script de inicialização básica (Bootstrap) para o SAA29.
Garante a existência do usuário Admin e da Frota Padrão.
Seguro para rodar tanto em Dev quanto em Produção.
"""
import asyncio
import os
from dotenv import load_dotenv
from app.database import get_session_factory
from app.auth.security import hash_senha
from sqlalchemy import select

# Carregar variáveis do .env
load_dotenv()

# Importar TODOS os modelos para o SQLAlchemy Registry (SEC-02/COR-01)
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

from app.auth.models import Usuario
from app.aeronaves.models import Aeronave

FROTA_PADRAO = [
    "5902", "5905", "5906", "5912", "5914", "5915", "5919", "5937", "5941", "5945",
    "5946", "5947", "5949", "5952", "5954", "5955", "5956", "5957", "5958", "5962",
]

async def init_db():
    admin_user = os.getenv("DEFAULT_ADMIN_USER", "admin").strip()
    admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123").strip()
    
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Garantir Usuário Admin
        result = await session.execute(select(Usuario).where(Usuario.username == admin_user))
        if not result.scalar_one_or_none():
            print(f"➕ Criando usuário mestre: {admin_user}...")
            admin = Usuario(
                nome="Administrador Sistema",
                posto="MAJ",
                especialidade="ELE",
                funcao="ADMINISTRADOR",
                ramal="1234",
                username=admin_user,
                senha_hash=hash_senha(admin_pass),
            )
            session.add(admin)
        else:
            print(f"ℹ️ Usuário {admin_user} já existe.")

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

        await session.commit()
        print(f"🚀 Inicialização do Banco concluída!")

if __name__ == "__main__":
    asyncio.run(init_db())
