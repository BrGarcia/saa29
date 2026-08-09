#!/usr/bin/env python
"""
scripts/r2_manager.py
Script responsável por realizar backup e restore do banco de dados SQLite
usando o Cloudflare R2 com garantia de integridade, atomicidade e consistência.
"""
import os
import sys
import boto3
import sqlite3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from dotenv import load_dotenv

# Carrega as variáveis do .env (se existir)
load_dotenv()

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db")

def is_sqlite():
    return "sqlite" in DATABASE_URL.lower()

def get_db_path():
    parsed = urlparse(DATABASE_URL)
    path = parsed.path
    
    # Tratamento para URLs do SQLite relativas clássicas contendo '/.' (ex: ///./db)
    if path.startswith("/."):
        return path[1:]
    # Se começar com mais de uma barra (ex: //app/data/saa29.db), reduzir para uma barra única para manter caminho absoluto
    if path.startswith("//"):
        return "/" + path.lstrip("/")
    return path

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
    
    backup_tmp = f"{db_path}.backup.r2tmp"
    
    try:
        # Gera snapshot consistente usando a API de backup nativa do SQLite
        src_conn = sqlite3.connect(db_path)
        # Executa checkpoint para forçar sincronização do WAL com o banco de dados principal
        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        
        dst_conn = sqlite3.connect(backup_tmp)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        # Envia o snapshot consistente
        s3.upload_file(backup_tmp, R2_BUCKET_NAME, key)
        print("Backup efetuado com sucesso!")
    except ClientError:
        print("Erro ao fazer backup para R2: Acesso negado ou credenciais inválidas.")
        sys.exit(1)
    except Exception:
        print("Erro inesperado ao realizar backup para o R2.")
        sys.exit(1)
    finally:
        # Garante a limpeza do snapshot temporário gerado no disco
        if os.path.exists(backup_tmp):
            os.remove(backup_tmp)

def restore_db():
    if not is_sqlite():
        print("Restore R2 abortado: Banco não é SQLite.")
        return
        
    db_path = get_db_path()
    s3 = get_s3_client()
    key = "database/saa29_local.db"
    
    print("Tentando baixar banco de dados do R2...")
    tmp_path = f"{db_path}.r2tmp"
    
    # Garante que o diretório pai existe
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    try:
        # Tenta verificar se o objeto existe antes de transferir
        s3.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        
        # Download para temporário no mesmo diretório do banco
        s3.download_file(R2_BUCKET_NAME, key, tmp_path)
        
        # Validação de integridade física básica do SQLite baixado
        try:
            conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check;")
            result = cursor.fetchone()
            conn.close()
            if not result or result[0].lower() != "ok":
                raise ValueError(f"Falha no quick_check: {result}")
        except Exception as val_err:
            print(f"Erro de integridade no banco baixado do R2: {val_err}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            sys.exit(1)
            
        # Substituição atômica no nível do SO
        os.replace(tmp_path, db_path)
        print("Restore efetuado com sucesso. Banco de dados sincronizado.")
        
    except ClientError as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        # Se for erro 404 (Objeto não existe no bucket), inicia um banco novo
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404" or "Not Found" in str(e):
            print("Banco de dados não encontrado no R2. Iniciando com banco limpo local.")
        else:
            print("Erro crítico ao acessar o R2: Acesso não autorizado ou rede inoperante.")
            sys.exit(1)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("Erro de comunicação inesperado com o serviço de armazenamento R2.")
        sys.exit(1)

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
