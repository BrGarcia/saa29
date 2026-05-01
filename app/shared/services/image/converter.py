from __future__ import annotations

from pathlib import Path

from PIL import Image

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    _HEIF_AVAILABLE = True
except Exception:
    _HEIF_AVAILABLE = False


class ImageConversionError(ValueError):
    pass


def _default_converted_path(input_path: Path, format_name: str) -> Path:
    if format_name.lower() == "png":
        return input_path.with_suffix(".png")
    return input_path.with_suffix(".jpg")


def convert_if_needed(
    input_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """
    Converte HEIC/HEIF para um formato suportado pelo restante do pipeline.

    Regras:
    - Se o arquivo já não for HEIC/HEIF, retorna o mesmo path.
    - Se tiver transparência, converte para PNG.
    - Caso contrário, converte para JPG.
    """
    path = Path(input_path).resolve()
    ext = path.suffix.lower()

    if ext not in {".heic", ".heif"}:
        return path

    if not _HEIF_AVAILABLE:
        raise ImageConversionError(
            "Arquivo HEIC/HEIF detectado, mas pillow-heif não está instalado."
        )

    try:
        with Image.open(path) as img:
            has_alpha = (
                img.mode in ("RGBA", "LA")
                or (img.mode == "P" and "transparency" in img.info)
            )

            target_ext = ".png" if has_alpha else ".jpg"

            if output_path is None:
                converted_path = _default_converted_path(path, "png" if has_alpha else "jpg")
            else:
                converted_path = Path(output_path).resolve()
                if not converted_path.suffix:
                    converted_path = converted_path.with_suffix(target_ext)

            if has_alpha:
                rgba = img.convert("RGBA")
                rgba.save(converted_path, format="PNG", optimize=True)
            else:
                rgb = img.convert("RGB")
                rgb.save(
                    converted_path,
                    format="JPEG",
                    quality=95,
                    optimize=True,
                    progressive=True,
                )

            return converted_path

    except Exception as exc:
        raise ImageConversionError(f"Falha ao converter imagem HEIC/HEIF: {path}") from exc