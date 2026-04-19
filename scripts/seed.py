"""
scripts/seed.py
Popula o banco de dados com dados iniciais para desenvolvimento.
Executar: python -m scripts.seed
"""
import asyncio
import os
from dotenv import load_dotenv
from app.database import get_session_factory
from app.auth.security import hash_senha
from sqlalchemy import select

# Carregar variáveis do .env explicitamente
load_dotenv()

# Importar TODOS os módulos para resolver os nomes das classes em referências de string cruzadas (avoid InvalidRequestError)
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

from app.auth.models import Usuario
from app.aeronaves.models import Aeronave

FROTA_PADRAO = [
    "5902", "5905", "5906", "5912", "5914", "5915", "5916", "5919", "5937", "5941", "5945",
    "5946", "5947", "5949", "5952", "5954", "5955", "5956", "5957", "5958", "5962",
]


async def seed():
    # Carregar variáveis do .env explicitamente dentro da função
    load_dotenv(override=True)
    
    admin_user = os.getenv("DEFAULT_ADMIN_USER", "admin").strip()
    admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "BisKP76pg3IU").strip()
    
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # Verificar se já existe o admin com o username configurado
        result = await session.execute(select(Usuario).where(Usuario.username == admin_user))
        admin = result.scalar_one_or_none()
        
        if not admin:
            # Caso não exista o novo admin, verificar se existe o antigo 'admin' para renomear/atualizar
            if admin_user != "admin":
                res_old = await session.execute(select(Usuario).where(Usuario.username == "admin"))
                old_admin = res_old.scalar_one_or_none()
                if old_admin:
                    print(f"🔄 Atualizando admin antigo para {admin_user}...")
                    old_admin.username = admin_user
                    old_admin.senha_hash = hash_senha(admin_pass)
                    admin = old_admin
            
            if not admin:
                print(f"➕ Criando usuário {admin_user}...")
                admin = Usuario(
                    nome="Administrador",
                    posto="-",
                    especialidade="-",
                    funcao="ADMINISTRADOR",
                    ramal="1234",
                    username=admin_user,
                    senha_hash=hash_senha(admin_pass),
                )
                session.add(admin)
            
            print(f"✅ Usuário {admin_user} configurado.")
        else:
            print(f"ℹ️ Usuário {admin_user} já existe. Atualizando senha...")
            admin.senha_hash = hash_senha(admin_pass)
            print("✅ Senha atualizada.")

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
