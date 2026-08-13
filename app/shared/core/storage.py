"""
app/core/storage.py
Serviço de abstração de armazenamento de arquivos (Local ou R2).
"""

import os
import uuid
import functools
import boto3
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from app.bootstrap.config import get_settings
from app.shared.core.file_validators import EXTENSOES_PERMITIDAS, validar_nome_arquivo_seguro


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

    @abstractmethod
    async def iniciar_multipart(self, file_key: str, content_type: str = "application/zip") -> str:
        """Inicia upload multipart e retorna upload_id (UploadId no R2 ou UUID local)."""
        pass

    @abstractmethod
    async def presign_parte(self, file_key: str, upload_id: str, numero: int) -> str:
        """Gera URL pré-assinada (ou endpoint dev local) para upload da parte N."""
        pass

    @abstractmethod
    async def concluir_multipart(self, file_key: str, upload_id: str, partes: list[dict]) -> None:
        """Conclui upload multipart reunindo todas as partes ({PartNumber, ETag})."""
        pass

    @abstractmethod
    async def abortar_multipart(self, file_key: str, upload_id: str) -> None:
        """Aborta o upload multipart e descarta partes incompletas."""
        pass


class LocalStorageService(StorageService):
    """Implementação de Storage Local na pasta `uploads` com staging local de chunks."""

    def __init__(self):
        settings = get_settings()
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.staging_chunks_dir = Path("var/publicacoes/staging/chunks")
        self.staging_chunks_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, file_content: bytes, original_filename: str, content_type: str) -> str:
        # Sanitizar nome de arquivo contra path traversal (Defesa em Profundidade)
        validar_nome_arquivo_seguro(original_filename)

        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in EXTENSOES_PERMITIDAS:
            raise ValueError(f"Extensão de arquivo não permitida: {ext}")
            
        new_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = self.upload_dir / new_filename

        # Gravação em thread separada — I/O de arquivo é bloqueante e, feita
        # direto na coroutine, trava o event loop inteiro (todas as outras
        # requisições concorrentes) pela duração da escrita. Mesmo padrão já
        # usado por R2StorageService._run_in_executor ao lado.
        await asyncio.to_thread(file_path.write_bytes, file_content)

        return str(file_path)

    async def get_url(self, file_path: str) -> str:
        # Para local storage, retornamos o caminho absoluto para o router ler o
        # arquivo. resolve() toca o filesystem, entao vai para thread pelo mesmo
        # motivo do upload acima: nao travar o event loop.
        return await asyncio.to_thread(lambda: str(Path(file_path).resolve()))

    async def delete(self, file_path: str) -> bool:
        path = Path(file_path)
        # Dois chamadores, duas convenções de caminho: `upload()` devolve um
        # path que já embute upload_dir (ex.: "var/uploads/xxx.pdf"), enquanto
        # os file_keys do fluxo multipart são relativos a upload_dir (ex.:
        # "publicacoes/uploads/<job_id>/edicao.zip", mesma resolução de
        # `concluir_multipart`). Tenta as duas em vez de adivinhar qual é.
        candidatos = [path] if path.is_absolute() else [path, self.upload_dir / path]

        # exists()/is_file()/unlink() sao syscalls bloqueantes; com 2 workers
        # Gunicorn, executa-las na coroutine trava todas as requisicoes
        # concorrentes daquele worker pela duracao do I/O.
        def _delete() -> bool:
            for candidato in candidatos:
                if candidato.exists() and candidato.is_file():
                    candidato.unlink()
                    return True
            return False

        return await asyncio.to_thread(_delete)

    async def iniciar_multipart(self, file_key: str, content_type: str = "application/zip") -> str:
        upload_id = uuid.uuid4().hex
        chunk_dir = self.staging_chunks_dir / upload_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        return upload_id

    async def presign_parte(self, file_key: str, upload_id: str, numero: int) -> str:
        return f"/publicacoes/api/edicoes/uploads/local-parte?upload_id={upload_id}&numero={numero}"

    async def salvar_parte_local(self, upload_id: str, numero: int, content: bytes) -> str:
        chunk_dir = self.staging_chunks_dir / upload_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        part_file = chunk_dir / f"part_{numero:04d}.dat"
        await asyncio.to_thread(part_file.write_bytes, content)
        return f"local-etag-{numero}"

    async def concluir_multipart(self, file_key: str, upload_id: str, partes: list[dict]) -> None:
        chunk_dir = self.staging_chunks_dir / upload_id
        dest_path = Path(file_key)
        if not dest_path.is_absolute():
            dest_path = self.upload_dir / file_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        def _montar():
            part_files = sorted(chunk_dir.glob("part_*.dat"))
            with open(dest_path, "wb") as out_f:
                for pf in part_files:
                    with open(pf, "rb") as in_f:
                        out_f.write(in_f.read())
                    pf.unlink()
            if chunk_dir.exists():
                chunk_dir.rmdir()

        await asyncio.to_thread(_montar)

    async def abortar_multipart(self, file_key: str, upload_id: str) -> None:
        chunk_dir = self.staging_chunks_dir / upload_id
        def _limpar():
            if chunk_dir.exists():
                for pf in chunk_dir.glob("*"):
                    pf.unlink()
                chunk_dir.rmdir()
        await asyncio.to_thread(_limpar)


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
        validar_nome_arquivo_seguro(original_filename)

        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in EXTENSOES_PERMITIDAS:
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
            except Exception as e:
                import botocore.exceptions
                if isinstance(e, botocore.exceptions.ClientError) and e.response.get('Error', {}).get('Code') in ['NoSuchKey', '404']:
                    return True
                raise
                
        return await self._run_in_executor(perform_delete)

    async def iniciar_multipart(self, file_key: str, content_type: str = "application/zip") -> str:
        def perform_iniciar():
            res = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=file_key,
                ContentType=content_type
            )
            return res["UploadId"]
        return await self._run_in_executor(perform_iniciar)

    async def presign_parte(self, file_key: str, upload_id: str, numero: int) -> str:
        def perform_presign():
            return self.s3_client.generate_presigned_url(
                ClientMethod="upload_part",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": file_key,
                    "UploadId": upload_id,
                    "PartNumber": numero,
                },
                ExpiresIn=3600,
            )
        return await self._run_in_executor(perform_presign)

    async def concluir_multipart(self, file_key: str, upload_id: str, partes: list[dict]) -> None:
        def perform_concluir():
            parts_formatted = []
            for i, p in enumerate(partes):
                part_num = int(p.get("numero") or p.get("PartNumber") or (i + 1))
                etag = str(p.get("etag") or p.get("ETag") or "")
                parts_formatted.append({"PartNumber": part_num, "ETag": etag})
            self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=file_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts_formatted},
            )
        await self._run_in_executor(perform_concluir)

    async def abortar_multipart(self, file_key: str, upload_id: str) -> None:
        def perform_abortar():
            self.s3_client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=file_key,
                UploadId=upload_id,
            )
        await self._run_in_executor(perform_abortar)


@functools.lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    """Fábrica de Storage: Retorna Local ou R2 dependendo da configuração."""
    settings = get_settings()
    if settings.storage_backend.lower() == "r2":
        return R2StorageService()
    return LocalStorageService()
