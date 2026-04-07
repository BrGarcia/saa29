
import asyncio
import sys
import os

# Adiciona o diretório raiz ao path para importar o app
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.database import get_session_factory
from app.auth.models import Usuario
# Importa todos os modelos para registrar no SQLAlchemy
import app.panes.models 
import app.aeronaves.models
import app.equipamentos.models

async def list_efetivo():
    print("📋 Lendo efetivo cadastrado no sistema...\n")
    print(f"{'POSTO/GRAD':<12} | {'NOME':<25} | {'FUNÇÃO':<15} | {'TRIGRAMA':<8} | {'USUÁRIO':<12} | {'STATUS':<8}")
    print("-" * 90)
    
    async with get_session_factory()() as session:
        result = await session.execute(select(Usuario).order_by(Usuario.funcao, Usuario.nome))
        usuarios = result.scalars().all()
        
        for u in usuarios:
            status = "ATIVO" if u.ativo else "INATIVO"
            posto_nome = f"{u.posto or ''} {u.nome or ''}"
            print(f"{u.posto or '-':<12} | {u.nome[:25]:<25} | {u.funcao:<15} | {u.trigrama or '-':<8} | {u.username:<12} | {status:<8}")
        
    print(f"\n✅ Total de {len(usuarios)} usuários encontrados.")

if __name__ == "__main__":
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./saa29_local.db"
    asyncio.run(list_efetivo())
