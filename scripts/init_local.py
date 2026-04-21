import asyncio
import sys
import os

# Adiciona o diretório raiz ao path para importar o app
sys.path.append(os.getcwd())

# Importar TODOS os modelos para garantir que o SQLAlchemy Registry os conheça (COR-01)
import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.panes.models

from app.bootstrap.database import create_all_tables, drop_all_tables
from scripts.db.seed import seed
from scripts.seed_equipamentos import seed as seed_equipamentos

async def main():
    print("Resetando banco de dados (Drop all)...")
    try:
        await drop_all_tables()
        print("Iniciando criação das tabelas no SQLite...")
        await create_all_tables()
        print("Tabelas criadas com sucesso!")
        
        print("Populando banco de dados (Básico)...")
        await seed()
        
        print("Populando equipamentos e slots...")
        await seed_equipamentos()
        
        print("Inicialização concluída!")
    except Exception as e:
        print(f"Erro na inicialização: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
