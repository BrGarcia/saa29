import asyncio
import sys
import os
import subprocess

# Adiciona o diretório raiz ao path para importar o app
sys.path.append(os.getcwd())

# Importar TODOS os modelos para garantir que o SQLAlchemy Registry os conheça (COR-01)
import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.equipamentos.models
import app.modules.panes.models
import app.modules.inspecoes.models
import app.modules.vencimentos.models
import app.modules.efetivo.models

from app.bootstrap.database import drop_all_tables, create_all_tables
from scripts.seed.seed import main as run_seeds

async def main():
    print("🗑️ Resetando banco de dados (Drop all)...")
    try:
        # 1. Limpar banco
        await drop_all_tables()
        
        # 2. Criar tabelas via SQLAlchemy (mais robusto para SQLite em ambiente de seed)
        print("🏗️ Criando tabelas via SQLAlchemy (create_all)...")
        await create_all_tables()
        
        # 3. Marcar como 'head' no Alembic para que o container não tente recriar as tabelas
        print("🏗️ Sincronizando versão do Alembic (stamp head)...")
        env = os.environ.copy()
        env["PYTHONPATH"] = env.get("PYTHONPATH", "") + (":" if env.get("PYTHONPATH") else "") + os.getcwd()
        subprocess.run(["python", "-m", "alembic", "stamp", "head"], check=True, env=env)
        print("✅ Banco de dados e Alembic sincronizados!")
        
        # 4. Rodar seeds
        print("🌱 Iniciando carga de dados (Seeds)...")
        await run_seeds()
        
        print("🚀 Inicialização concluída com sucesso!")
    except Exception as e:
        print(f"❌ Erro na inicialização: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
