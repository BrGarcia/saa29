"""
app/core/file_validators.py
Módulo de segurança para validação rigorosa de uploads (MIME type e Magic Bytes).
"""
import magic
from fastapi import UploadFile, HTTPException, status
import os

ALLOWED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "application/pdf": [".pdf"],
}

async def validate_file_upload(file: UploadFile) -> None:
    """Valida o tipo e a extensão de um arquivo usando libmagic."""
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
    
    # Valida usando magic
    mime_type = magic.from_buffer(file_content, mime=True)
    
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
