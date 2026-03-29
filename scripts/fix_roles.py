import asyncio
from app.database import get_session_factory
from app.auth.models import Usuario
from app.auth.security import hash_senha
from sqlalchemy import select

# Importar TODOS os módulos para resolver os nomes das classes em referências de string cruzadas (avoid InvalidRequestError)
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

async def main():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # Ensure role of admin is ADMINISTRADOR
        result = await session.execute(select(Usuario).where(Usuario.username == "admin"))
        admin = result.scalar_one_or_none()
        if admin:
            admin.funcao = "ADMINISTRADOR"
            session.add(admin)
            print("Role do admin corrigido para ADMINISTRADOR")
            
        # Ensure encarregado exists
        result = await session.execute(select(Usuario).where(Usuario.username == "encarregado"))
        enc = result.scalar_one_or_none()
        if not enc:
            enc = Usuario(
                nome="Chefe de Linha",
                posto="Cap",
                especialidade="BMB",
                funcao="ENCARREGADO",
                ramal="2222",
                username="encarregado",
                senha_hash=hash_senha("123"),
            )
            session.add(enc)
            print("Usuário encarregado criado (senha: 123)")
            
        # Ensure mantenedor exists
        result = await session.execute(select(Usuario).where(Usuario.username == "mantenedor"))
        man = result.scalar_one_or_none()
        if not man:
            man = Usuario(
                nome="Técnico Especialista",
                posto="Sgt",
                especialidade="BMB",
                funcao="MANTENEDOR",
                ramal="3333",
                username="mantenedor",
                senha_hash=hash_senha("123"),
            )
            session.add(man)
            print("Usuário mantenedor criado (senha: 123)")
            
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
