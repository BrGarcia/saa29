from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.bootstrap.config.image import (
    MAX_HEIGHT,
    MAX_WIDTH,
    MIN_SIZE_SKIP,
    TARGET_PSNR,
)

from .converter import convert_if_needed
from .optimizer import optimize_image as compress_image
from .resizer import resize_image
from .validator import validate_image

logger = logging.getLogger(__name__)


def _cleanup_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        logger.warning("Não foi possível remover arquivo temporário: %s", path)


def process_image(
    input_data: str | Path | bytes,
    output_path: str | Path | None = None,
    *,
    filename_hint: str = "upload.jpg",
    max_width: int = MAX_WIDTH,
    max_height: int = MAX_HEIGHT,
    target_psnr: int = TARGET_PSNR,
    min_size_skip: int = MIN_SIZE_SKIP,
) -> str | bytes:
    """
    Processa uma imagem em etapas:
    1. validação
    2. conversão de formato, se necessário
    3. resize
    4. compressão final

    Se input_data for bytes, retorna os bytes da imagem otimizada.
    Se input_data for Path/str, retorna o caminho (string) do arquivo final.
    """
    # 1. Validação inicial (suporta bytes ou Path)
    validate_image(input_data)

    is_bytes_input = isinstance(input_data, bytes)

    with tempfile.TemporaryDirectory(prefix="saa29_img_") as tmp_dir:
        working_dir = Path(tmp_dir)

        # Preparar arquivo de origem no diretório temporário para evitar I/O no original
        if is_bytes_input:
            source_file = working_dir / filename_hint
            source_file.write_bytes(input_data)
        else:
            original_path = Path(input_data).resolve()
            # Copiamos para o diretório de trabalho para isolar as transformações
            source_file = working_dir / original_path.name
            # Se já for WebP, apenas apontamos para ele (ou copiamos se quisermos isolamento total)
            import shutil
            shutil.copy2(original_path, source_file)

        current_path = source_file

        try:
            # 2. Conversão (HEIC -> JPG/PNG)
            # convert_if_needed salva no mesmo diretório se output_path não for informado
            converted_path = convert_if_needed(current_path)
            if converted_path != current_path:
                # Se converteu, o original no temp_dir pode ser removido (TemporaryDirectory faz isso no fim, mas podemos antecipar)
                current_path = converted_path

            # 3. Redimensionamento
            resized_path = resize_image(
                current_path,
                max_width=max_width,
                max_height=max_height,
                min_size_skip=min_size_skip,
            )
            current_path = resized_path

            # 4. Otimização Final (imgdiet -> WebP)
            # Se for bytes input, salvamos o webp dentro do temp_dir
            if is_bytes_input:
                final_target = working_dir / f"{current_path.stem}.webp"
            else:
                # Se for Path input, seguimos a regra de output_path ou padrão (ao lado do original)
                final_target = output_path

            final_path = compress_image(
                current_path,
                output_path=final_target,
                target_psnr=target_psnr,
            )

            if is_bytes_input:
                return final_path.read_bytes()
            
            return str(final_path)

        except Exception as exc:
            logger.error("Falha no pipeline de processamento de imagem: %s", exc)
            raise