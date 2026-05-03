import asyncio
import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

# Import all models to ensure they are registered with Base
import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.panes.models
import app.modules.inspecoes.models
import app.modules.vencimentos.models
import app.modules.inventario.models

from app.bootstrap.database import create_all_tables

async def main():
    print("Criando tabelas...")
    await create_all_tables()
    print("Tabelas criadas.")

if __name__ == "__main__":
    asyncio.run(main())
