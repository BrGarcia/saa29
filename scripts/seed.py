"""
scripts/seed.py
Popula o banco de dados com dados iniciais para desenvolvimento.
Executar: $env:PYTHONPATH="."; .venv\Scripts\python -m scripts.seed
"""
import asyncio
import uuid
from app.database import get_session_factory
from app.auth.security import hash_senha
from app.auth.models import Usuario
from app.aeronaves.models import Aeronave
from app.equipamentos.models import Equipamento, ItemEquipamento, TipoControle
from app.panes.models import Pane
from app.core.enums import StatusAeronave

async def seed():
    async_session = get_session_factory()
    async with async_session() as session:
        # 1. Limpar dados existentes (opcional, para garantir idempotência)
        # Para um seed simples, vamos apenas adicionar se não existir.
        
        # 2. Usuário admin (INSPETOR)
        admin_username = "admin"
        # Verificar se já existe
        from sqlalchemy import select
        result = await session.execute(select(Usuario).where(Usuario.username == admin_username))
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = Usuario(
                nome="Administrador SAA29",
                posto="Capitão",
                funcao="INSPETOR",
                username=admin_username,
                senha_hash=hash_senha("admin123"),
            )
            session.add(admin)
            print(f"✅ Usuário '{admin_username}' criado.")
        else:
            print(f"ℹ️ Usuário '{admin_username}' já existe.")

        # 3. Aeronaves A-29 (exemplos)
        matriculas = ["5700", "5701", "5702", "5703", "5704"]
        for mat in matriculas:
            result = await session.execute(select(Aeronave).where(Aeronave.matricula == mat))
            if not result.scalar_one_or_none():
                aeronave = Aeronave(
                    matricula=mat,
                    serial_number=f"BR-{mat}",
                    modelo="A-29",
                    status=StatusAeronave.OPERACIONAL.value
                )
                session.add(aeronave)
                print(f"✅ Aeronave '{mat}' criada.")
            else:
                print(f"ℹ️ Aeronave '{mat}' já existe.")

        await session.commit()
        print("🚀 Seed concluído com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed())
