"""
app/core/file_validators.py
Módulo de segurança para validação rigorosa de uploads (MIME type e Magic Bytes).
"""
import logging
from fastapi import UploadFile, HTTPException, status
import os

logger = logging.getLogger(__name__)

try:
    import magic
    _MAGIC_AVAILABLE = True
except Exception as e:
    logger.warning("python-magic ou libmagic não está disponível. Usando validador manual de assinaturas (fallback). Erro: %s", e)
    _MAGIC_AVAILABLE = False

ALLOWED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "application/pdf": [".pdf"],
}

def _detect_mime_type_fallback(content: bytes) -> str | None:
    """Detecta o MIME type a partir da assinatura de bytes (magic bytes)."""
    if content.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif content.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    elif content.startswith(b'%PDF'):
        return "application/pdf"
    return None

async def validate_file_upload(file: UploadFile) -> None:
    """Valida o tipo e a extensão de um arquivo usando libmagic ou fallback manual."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo inválido (sem nome)."
        )
    
    # 1. Path traversal check name
    if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nome de arquivo inválido. (Path Traversal não permitido)"
        )

    # 2. Validar extensão
    ext = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = [e for exts in ALLOWED_MIME_TYPES.values() for e in exts]
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extensão não permitida. Permitidas: {', '.join(allowed_extensions)}"
        )

    # 3. Validar conteúdo e Content-Type (Magic Bytes)
    file_content = await file.read(2048)  # Lê o início do arquivo
    await file.seek(0)  # Reseta o ponteiro
    
    # Valida usando magic se disponível, senão fallback manual
    if _MAGIC_AVAILABLE:
        try:
            mime_type = magic.from_buffer(file_content, mime=True)
        except Exception as e:
            logger.warning("Falha ao usar python-magic, recorrendo ao validador manual: %s", e)
            mime_type = _detect_mime_type_fallback(file_content)
    else:
        mime_type = _detect_mime_type_fallback(file_content)
    
    if not mime_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Não foi possível identificar o tipo de arquivo de forma segura por sua assinatura."
        )
        
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo de arquivo (MIME) rejeitado por segurança: {mime_type}"
        )
        
    # 4. Cross-check da extensão com o MIME type real
    if ext not in ALLOWED_MIME_TYPES[mime_type]:
         raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extensão {ext} não condiz com o conteúdo real do arquivo ({mime_type})"
        )

