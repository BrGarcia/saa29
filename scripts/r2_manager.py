#!/usr/bin/env python
"""
scripts/r2_manager.py
Script responsável por realizar backup e restore do banco de dados SQLite
usando o Cloudflare R2.
"""
import os
import sys
import boto3
from dotenv import load_dotenv

# Carrega as variáveis do .env (se existir)
load_dotenv()

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db")

# Apenas executar se for SQLite
def is_sqlite():
    return "sqlite" in DATABASE_URL.lower()

def get_db_path():
    # Extrai o caminho "/./saa29_local.db" de "sqlite+aiosqlite:///./saa29_local.db"
    return DATABASE_URL.split("///")[-1]

def get_s3_client():
    if not all([R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("Erro: Variáveis de ambiente R2 incompletas.")
        sys.exit(1)
        
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto"
    )

def backup_db():
    if not is_sqlite():
        print("Backup R2 abortado: Banco não é SQLite.")
        return
        
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Erro: Arquivo do banco {db_path} não encontrado para backup.")
        return

    print("Iniciando backup para o R2...")
    s3 = get_s3_client()
    key = "database/saa29_local.db"
    
    try:
        s3.upload_file(db_path, R2_BUCKET_NAME, key)
        print("Backup efetuado com sucesso!")
    except Exception as e:
        print(f"Erro ao fazer backup para R2: {e}")

def restore_db():
    if not is_sqlite():
        print("Restore R2 abortado: Banco não é SQLite.")
        return
        
    db_path = get_db_path()
    s3 = get_s3_client()
    key = "database/saa29_local.db"
    
    print("Tentando baixar banco de dados do R2...")
    try:
        s3.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        # Objeto existe, faz o download
        s3.download_file(R2_BUCKET_NAME, key, db_path)
        print("Restore efetuado com sucesso. Banco de dados sincronizado.")
    except Exception as e:
        # Pega erro 404 (não existe) ou outro erro
        print(f"Banco não encontrado no R2 ou erro de acesso: {e}. Iniciando com banco limpo local.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python r2_manager.py [backup|restore]")
        sys.exit(1)
        
    command = sys.argv[1].lower()
    if command == "backup":
        backup_db()
    elif command == "restore":
        restore_db()
    else:
        print(f"Comando desconhecido: {command}")
