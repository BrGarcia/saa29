"""
app/core/storage.py
Serviço de abstração de armazenamento de arquivos (Local ou R2).
"""

import os
import uuid
import boto3
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

from app.bootstrap.config import get_settings


class StorageService(ABC):
    """Interface abstrata para armazenamento de arquivos."""

    @abstractmethod
    async def upload(self, file_content: bytes, original_filename: str, content_type: str) -> str:
        """Faz o upload de um arquivo e retorna seu caminho/key."""
        pass

    @abstractmethod
    async def get_url(self, file_path: str) -> str:
        """Gera uma URL pública (ou pré-assinada) para o arquivo."""
        pass

    @abstractmethod
    async def delete(self, file_path: str) -> bool:
        """Deleta um arquivo de Storage."""
        pass


class LocalStorageService(StorageService):
    """Implementação de Storage Local na pasta `uploads`."""

    def __init__(self):
        settings = get_settings()
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, file_content: bytes, original_filename: str, content_type: str) -> str:
        # Sanitizar nome de arquivo contra path traversal (Defesa em Profundidade)
        if '..' in original_filename or '/' in original_filename or '\\' in original_filename:
            raise ValueError("Tentativa de path traversal detectada no nome do arquivo.")
            
        ext = os.path.splitext(original_filename)[1].lower()
        ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx']
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Extensão de arquivo não permitida: {ext}")
            
        new_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = self.upload_dir / new_filename

        # Gravação local (pode bloquear levemente event loop em arquivos grandes, mas é local)
        with open(file_path, "wb") as f:
            f.write(file_content)

        return str(file_path)

    async def get_url(self, file_path: str) -> str:
        # Para local storage, retornamos o caminho absoluto para o router ler o arquivo
        return str(Path(file_path).resolve())

    async def delete(self, file_path: str) -> bool:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False


class R2StorageService(StorageService):
    """Implementação de Storage no Cloudflare R2 (Compatível com S3) utilizando boto3."""

    def __init__(self):
        settings = get_settings()
        
        if not all([settings.r2_endpoint, settings.r2_access_key_id, settings.r2_secret_access_key, settings.r2_bucket_name]):
            raise ValueError("Configurações do R2 ausentes ou incompletas.")
            
        self.bucket_name = settings.r2_bucket_name
        from botocore.config import Config
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="us-east-1",  # R2 permite usar us-east-1 ou weur (padrão)
            config=Config(signature_version='s3v4')
        )

    async def _run_in_executor(self, func, *args, **kwargs):
        """Executa funções bloqueantes do boto3 em uma thread separada."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def upload(self, file_content: bytes, original_filename: str, content_type: str) -> str:
        # Sanitizar nome de arquivo contra path traversal
        if '..' in original_filename or '/' in original_filename or '\\' in original_filename:
            raise ValueError("Tentativa de path traversal detectada no nome do arquivo.")
            
        ext = os.path.splitext(original_filename)[1].lower()
        ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx']
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Extensão de arquivo não permitida: {ext}")
            
        key = f"anexos/{uuid.uuid4().hex}{ext}"

        def perform_upload():
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type
            )
        
        await self._run_in_executor(perform_upload)
        return key

    async def get_url(self, file_path: str) -> str:
        """Gera URL pré-assinada válida por 60 minutos."""
        def generate_presigned_url():
            return self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": file_path},
                ExpiresIn=3600  # 60 minutos
            )
            
        return await self._run_in_executor(generate_presigned_url)

    async def delete(self, file_path: str) -> bool:
        def perform_delete():
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
                return True
            except Exception:
                return False
                
        return await self._run_in_executor(perform_delete)


def get_storage_service() -> StorageService:
    """Fábrica de Storage: Retorna Local ou R2 dependendo da configuração."""
    settings = get_settings()
    if settings.storage_backend.lower() == "r2":
        return R2StorageService()
    return LocalStorageService()
