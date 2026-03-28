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

async def seed():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # Verificar se já existe o admin
        result = await session.execute(select(Usuario).where(Usuario.username == "admin"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = Usuario(
                nome="Administrador SAA29",
                posto="Cel",
                especialidade="ELT",
                funcao="ENCARREGADO",
                ramal="1234",
                username="admin",
                senha_hash=hash_senha("admin123"),
            )
            session.add(admin)
            print("✅ Usuário admin adicionado.")
        else:
            print("ℹ️ Usuário admin já existe.")

        # Aeronaves A-29 (exemplos)
        aeronaves_dados = [
            {"matricula": "5700", "serial_number": "SN-001"},
            {"matricula": "5701", "serial_number": "SN-002"},
            {"matricula": "5702", "serial_number": "SN-003"},
            {"matricula": "5703", "serial_number": "SN-004"},
            {"matricula": "5704", "serial_number": "SN-005"},
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
