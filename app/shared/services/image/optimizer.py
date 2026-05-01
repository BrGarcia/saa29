from __future__ import annotations

from pathlib import Path

from imgdiet import save


class ImageOptimizationError(ValueError):
    pass


def _default_optimized_path(input_path: Path) -> Path:
    return input_path.with_suffix(".webp")


def optimize_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    target_psnr: float = 40.0,
    verbose: bool = False,
) -> Path:
    """
    Comprime a imagem com imgdiet e retorna o caminho do arquivo final.

    Regras:
    - Se o arquivo já for WebP, retorna o próprio caminho.
    - Se output_path não for informado, cria um .webp ao lado do original.
    - Se output_path apontar para diretório, grava o arquivo dentro dele.
    """
    source_path = Path(input_path).resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {source_path}")

    if not source_path.is_file():
        raise ImageOptimizationError(
            f"O caminho não aponta para um arquivo válido: {source_path}"
        )

    if source_path.suffix.lower() == ".webp":
        return source_path

    if output_path is None:
        target_path = _default_optimized_path(source_path)
    else:
        target_path = Path(output_path).resolve()
        if target_path.exists() and target_path.is_dir():
            target_path = target_path / _default_optimized_path(source_path).name
        elif target_path.suffix.lower() != ".webp":
            target_path = target_path.with_suffix(".webp")

    try:
        source_paths, target_paths = save(
            source=str(source_path),
            target=str(target_path),
            target_psnr=target_psnr,
            verbose=verbose,
        )

        if not target_paths:
            raise ImageOptimizationError(
                f"imgdiet não retornou arquivo otimizado para: {source_path}"
            )

        final_path = Path(target_paths[0]).resolve()

        if not final_path.exists():
            raise ImageOptimizationError(
                f"Arquivo otimizado não foi criado: {final_path}"
            )

        return final_path

    except Exception as exc:
        raise ImageOptimizationError(
            f"Falha ao otimizar imagem com imgdiet: {source_path}"
        ) from exc