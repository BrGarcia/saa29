import os
import boto3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=os.getenv('R2_ENDPOINT_URL'),
        aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def download_db():
    bucket = os.getenv('R2_BUCKET_NAME')
    db_path = "./saa29_local.db"
    client = get_r2_client()
    try:
        print(f"📥 Baixando backup de {bucket}...")
        client.download_file(bucket, 'saa29_local.db', db_path)
        print("✅ Banco de dados restaurado do R2.")
    except Exception as e:
        print(f"⚠️ Nenhum backup encontrado ou erro ao baixar: {e}")

def upload_db():
    bucket = os.getenv('R2_BUCKET_NAME')
    db_path = "./saa29_local.db"
    if not os.path.exists(db_path):
        print("❌ Arquivo de banco não encontrado para backup.")
        return
    
    client = get_r2_client()
    try:
        print(f"📤 Enviando backup para {bucket}...")
        client.upload_file(db_path, bucket, 'saa29_local.db')
        print("✅ Backup concluído com sucesso no R2.")
    except Exception as e:
        print(f"❌ Erro no backup: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        download_db()
    else:
        upload_db()
