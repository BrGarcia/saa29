from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:
    # Se pillow-heif não estiver instalado, o validador ainda funciona
    # para formatos que o Pillow abre nativamente.
    pass


@dataclass(frozen=True)
class ImageValidationConfig:
    allowed_extensions: frozenset[str] = frozenset(
        {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".heic",
            ".heif",
        }
    )
    max_file_size_bytes: int | None = None  # opcional
    min_file_size_bytes: int = 1


class ImageValidationError(ValueError):
    pass


def validate_image(
    input_data: str | Path | bytes,
    *,
    allowed_extensions: frozenset[str] | None = None,
    max_file_size_bytes: int | None = None,
    min_file_size_bytes: int = 1,
) -> Path | bytes:
    """
    Valida se o arquivo ou buffer existe, tem extensão suportada e é uma imagem legível.

    Retorna o Path ou bytes validado.
    """
    if isinstance(input_data, bytes):
        size = len(input_data)
        source = io.BytesIO(input_data)
        identifier = "buffer"
    else:
        path = Path(input_data).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        if not path.is_file():
            raise ImageValidationError(f"O caminho não aponta para um arquivo válido: {path}")

        # Validar extensão apenas para arquivos
        ext = path.suffix.lower()
        allowed = allowed_extensions or ImageValidationConfig.allowed_extensions
        if ext not in allowed:
            raise ImageValidationError(
                f"Extensão não suportada: {ext}. "
                f"Permitidas: {', '.join(sorted(allowed))}"
            )
        
        size = path.stat().st_size
        source = path
        identifier = str(path)

    if size < min_file_size_bytes:
        raise ImageValidationError(f"Arquivo vazio ou corrompido: {identifier}")

    if max_file_size_bytes is not None and size > max_file_size_bytes:
        raise ImageValidationError(
            f"Arquivo excede o tamanho máximo permitido ({max_file_size_bytes} bytes): {identifier}"
        )

    try:
        with Image.open(source) as img:
            img.verify()
    except UnidentifiedImageError as exc:
        raise ImageValidationError(f"Arquivo não parece ser uma imagem válida: {identifier}") from exc
    except Exception as exc:
        raise ImageValidationError(f"Falha ao validar a imagem: {identifier}") from exc

    return input_data