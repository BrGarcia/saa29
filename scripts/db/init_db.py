"""
scripts/init_db.py
Script de inicialização básica (Bootstrap) para o SAA29.
Garante a existência do usuário Admin e da Frota Padrão.
Seguro para rodar tanto em Dev quanto em Produção.
"""
import asyncio
import os
from dotenv import load_dotenv
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

async def init_db():
    # DEFAULT_ADMIN_PASSWORD MUST be set for security
    admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD")
    if not admin_pass:
        raise ValueError(
            "CRITICAL: DEFAULT_ADMIN_PASSWORD environment variable is not set.\n"
            "  - This is required for security (no hardcoded fallback).\n"
            "  - Set it before running init_db.py\n"
            "  - Example: export DEFAULT_ADMIN_PASSWORD='your_secure_password'"
        )
    
    admin_user = os.getenv("DEFAULT_ADMIN_USER", "admin").strip()
    admin_pass = admin_pass.strip()
    
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Garantir Usuário Admin
        # COR-BOOT: Primeiro busca pelo username configurado. Se não achar,
        # verifica se já existe qualquer ADMINISTRADOR no banco (banco restaurado do R2
        # pode ter um admin com username diferente da variável de ambiente atual).
        result = await session.execute(select(Usuario).where(Usuario.username == admin_user))
        admin_existente = result.scalar_one_or_none()

        if not admin_existente:
            # Verifica se já existe qualquer administrador (evita duplicata ao restaurar DB do R2)
            result_any = await session.execute(
                select(Usuario).where(Usuario.funcao == "ADMINISTRADOR")
            )
            admin_qualquer = result_any.scalar_one_or_none()

            if admin_qualquer:
                print(f"ℹ️ Admin já existe com username '{admin_qualquer.username}'. Nenhum novo admin criado.")
            else:
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

        # 1.1 Garantir Usuários de Teste (Encarregado e Mantenedor)
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
