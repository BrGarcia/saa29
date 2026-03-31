
import os
import sys
import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    # Garante que as vars do .env sejam carregadas (especialmente para o Uvicorn ler)
    load_dotenv()
    
    # Adiciona o diretório atual ao sys.path para que o uvicorn encontre o módulo 'app'
    sys.path.insert(0, os.getcwd())
    
    # Força SQLite se estivermos em desenvolvimento e o usuário não setou DATABASE_URL
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./saa29_local.db"
    
    print(f"🚀 Iniciando SAA29 com DATABASE_URL: {os.environ.get('DATABASE_URL')}")
    
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )
