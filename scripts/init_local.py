
import asyncio
import sys
import os

# Adiciona o diretório raiz ao path para importar o app
sys.path.append(os.getcwd())

from app.database import create_all_tables
from scripts.seed import seed

async def main():
    print("🚀 Iniciando criação das tabelas no SQLite...")
    try:
        await create_all_tables()
        print("✅ Tabelas criadas com sucesso!")
        
        print("🌱 Populando banco de dados...")
        await seed()
        print("✨ Inicialização concluída!")
    except Exception as e:
        print(f"❌ Erro na inicialização: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
