from __future__ import annotations

import logging
from pathlib import Path

from app.bootstrap.config.image import (
    MAX_HEIGHT,
    MAX_WIDTH,
    MIN_SIZE_SKIP,
    TARGET_PSNR,
)

from .converter import convert_if_needed
from .optimizer import compress_image
from .resizer import resize_image
from .validator import validate_image

logger = logging.getLogger(__name__)


def _cleanup_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        logger.warning("Não foi possível remover arquivo temporário: %s", path)


def _replace_stage(
    current_path: Path,
    next_path: Path,
    keep_original: Path,
) -> Path:
    """
    Remove o arquivo anterior quando ele tiver sido gerado por uma etapa intermediária.
    O arquivo original enviado pelo usuário nunca é removido aqui.
    """
    if next_path != current_path and current_path != keep_original:
        _cleanup_file(current_path)
    return next_path


def process_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    max_width: int = MAX_WIDTH,
    max_height: int = MAX_HEIGHT,
    target_psnr: int = TARGET_PSNR,
    min_size_skip: int = MIN_SIZE_SKIP,
    cleanup_intermediate_files: bool = True,
) -> str:
    """
    Processa uma imagem em etapas:
    1. validação
    2. conversão de formato, se necessário
    3. resize
    4. compressão final

    Retorna o caminho do arquivo final processado.
    """
    source_path = Path(input_path).resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {source_path}")

    validate_image(source_path)

    current_path = source_path
    intermediates: list[Path] = []

    try:
        converted_path = convert_if_needed(current_path)
        if converted_path != current_path:
            intermediates.append(current_path)
            current_path = converted_path

        resized_path = resize_image(
            current_path,
            max_width=max_width,
            max_height=max_height,
            min_size_skip=min_size_skip,
        )
        if resized_path != current_path:
            intermediates.append(current_path)
            current_path = resized_path

        final_path = compress_image(
            current_path,
            output_path=output_path,
            target_psnr=target_psnr,
        )
        if final_path != current_path:
            intermediates.append(current_path)
            current_path = final_path

        return str(current_path)

    finally:
        if cleanup_intermediate_files:
            for path in reversed(intermediates):
                if path != source_path:
                    _cleanup_file(path)