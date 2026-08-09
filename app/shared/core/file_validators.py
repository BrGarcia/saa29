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
    "image/heic": [".heic", ".heif"],
    "image/heif": [".heif", ".heic"],
}

# Fonte única de verdade para a allowlist de upload. Antes desta correção,
# a mesma decisão ("quais arquivos podem ser enviados") estava duplicada e
# divergente em 3 lugares: aqui (sem HEIC/HEIF), em
# `app/shared/core/storage.py` (com .doc/.docx que este módulo rejeitava) e
# em `app/modules/panes/service.py` (com HEIC/HEIF, que ESTE módulo — que
# roda primeiro, no router, antes de qualquer código de panes — rejeitava
# com 422). Resultado prático: o pipeline inteiro de conversão HEIC→JPEG em
# `app/shared/services/image/converter.py` era código morto, inalcançável a
# partir do endpoint real de upload. `.doc`/`.docx` foram removidos daqui e
# de `storage.py`: não há validação de magic bytes para eles em lugar
# nenhum do código (nem aqui, nem no fallback manual), então aceitá-los no
# storage sem que este validador os reconheça era uma lacuna de segurança,
# não um recurso — se o suporte a Office for necessário no futuro, deve
# entrar aqui primeiro, com magic bytes reais.
EXTENSOES_PERMITIDAS: frozenset[str] = frozenset(
    ext for exts in ALLOWED_MIME_TYPES.values() for ext in exts
)
MIMES_PERMITIDOS: frozenset[str] = frozenset(ALLOWED_MIME_TYPES.keys())
EXTENSAO_MIME_MAP: dict[str, frozenset[str]] = {
    ext: frozenset(mime for mime, exts in ALLOWED_MIME_TYPES.items() if ext in exts)
    for ext in EXTENSOES_PERMITIDAS
}

def _detect_mime_type_fallback(content: bytes) -> str | None:
    """Detecta o MIME type a partir da assinatura de bytes (magic bytes)."""
    if content.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif content.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    elif content.startswith(b'%PDF'):
        return "application/pdf"
    elif len(content) >= 12 and content[4:8] == b'ftyp':
        # HEIC/HEIF: contêiner ISOBMFF com caixa "ftyp" no offset 4; o
        # "brand" nos bytes 8-12 indica a variante. Cobre os brands mais
        # comuns gerados por iPhones (heic/heix/mif1/msf1/heif).
        brand = content[8:12]
        if brand in (b'heic', b'heix', b'hevc', b'hevx'):
            return "image/heic"
        if brand in (b'mif1', b'msf1', b'heif'):
            return "image/heif"
    return None

async def validate_file_upload(file: UploadFile) -> None:
    """Valida o tipo e a extensão de um arquivo usando libmagic ou fallback manual."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo inválido (sem nome)."
        )
    
    # 1. Path traversal check name
    try:
        validar_nome_arquivo_seguro(file.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nome de arquivo inválido. (Path Traversal não permitido)"
        ) from exc

    # 2. Validar extensão
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extensão não permitida. Permitidas: {', '.join(sorted(EXTENSOES_PERMITIDAS))}"
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


def validar_nome_arquivo_seguro(filename: str) -> None:
    """Rejeita nomes de arquivo com tentativa de path traversal.

    Antes duplicada de forma idêntica em `storage.py` (2x, uma por
    implementação de `StorageService`) e aqui em `validate_file_upload` —
    3 cópias do mesmo `if '..' in nome or '/' in nome or '\\\\' in nome`.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Tentativa de path traversal detectada no nome do arquivo.")


async def ler_upload_com_limite(file: UploadFile, max_bytes: int) -> bytes:
    """Lê o corpo de um upload em chunks, rejeitando antes de materializar
    o arquivo inteiro em memória se ultrapassar `max_bytes`.

    Item #4/Etapa 5: antes, o router lia o upload inteiro com um único
    `await file.read()` sem limite algum, e só depois — já com todo o
    conteúdo em RAM — `panes.service.upload_anexo` verificava o tamanho.
    Um upload de vários GB consumia toda a memória disponível antes de
    qualquer rejeição. `Content-Length` não é usado como única defesa (é
    controlado pelo cliente e pode estar ausente em `chunked` encoding) —
    a contagem real de bytes lidos é o que decide.
    """
    chunks: list[bytes] = []
    total = 0
    tamanho_chunk = 1024 * 1024  # 1 MiB por chunk
    while True:
        chunk = await file.read(tamanho_chunk)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            await file.close()
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Arquivo excede o tamanho máximo permitido de {max_bytes / (1024 * 1024):.1f} MB.",
            )
        chunks.append(chunk)
    await file.seek(0)
    return b"".join(chunks)

