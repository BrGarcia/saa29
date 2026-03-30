"""
scripts/seed.py
Popula o banco de dados com dados iniciais para desenvolvimento.
Executar: python -m scripts.seed
"""
import asyncio
from app.database import get_session_factory
from app.auth.security import hash_senha
from sqlalchemy import select

# Importar TODOS os módulos para resolver os nomes das classes em referências de string cruzadas (avoid InvalidRequestError)
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


async def seed():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # Verificar se já existe o admin
        result = await session.execute(select(Usuario).where(Usuario.username == "admin"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = Usuario(
                nome="Administrador",
                posto="-",
                especialidade="-",
                funcao="ADMINISTRADOR",
                ramal="1234",
                username="admin",
                senha_hash=hash_senha("admin123"),
            )
            session.add(admin)
            print("✅ Usuário admin adicionado.")
        else:
            print("ℹ️ Usuário admin já existe.")

        aeronaves_dados = [
            {"matricula": matricula, "serial_number": f"SN-{matricula}"}
            for matricula in FROTA_PADRAO
        ]
        
        for dados in aeronaves_dados:
            result = await session.execute(select(Aeronave).where(Aeronave.matricula == dados["matricula"]))
            if not result.scalar_one_or_none():
                aeronave = Aeronave(
                    matricula=dados["matricula"],
                    serial_number=dados["serial_number"],
                    modelo="A-29"
                )
                session.add(aeronave)
                print(f"✅ Aeronave {dados['matricula']} adicionada.")

        await session.commit()
        print(f"🎉 Seed completo!")

if __name__ == "__main__":
    asyncio.run(seed())
