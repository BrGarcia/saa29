from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


class ImageResizeError(ValueError):
    pass


def _default_resized_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_resized{input_path.suffix}")


def resize_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    max_width: int = 1654,
    max_height: int = 2339,
    min_size_skip: int = 200_000,
) -> Path:
    """
    Redimensiona a imagem mantendo a proporção.

    Regras:
    - Se o arquivo for menor que min_size_skip, retorna o mesmo path.
    - Se a imagem já estiver dentro dos limites, retorna o mesmo path.
    - Caso precise redimensionar, grava uma nova imagem e retorna o novo path.
    """
    path = Path(input_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    if path.stat().st_size < min_size_skip:
        return path

    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)

            original_width, original_height = img.size

            if original_width <= max_width and original_height <= max_height:
                return path

            resized = img.copy()
            resized.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            if output_path is None:
                resized_path = _default_resized_path(path)
            else:
                resized_path = Path(output_path).resolve()
                if resized_path.is_dir():
                    resized_path = resized_path / _default_resized_path(path).name

            ext = resized_path.suffix.lower()

            save_kwargs: dict[str, object] = {"optimize": True}

            if ext in {".jpg", ".jpeg"}:
                if resized.mode in ("RGBA", "LA", "P"):
                    resized = resized.convert("RGB")
                save_kwargs.update(
                    {
                        "format": "JPEG",
                        "quality": 95,
                        "progressive": True,
                    }
                )
            elif ext == ".png":
                if resized.mode not in ("RGBA", "LA", "P"):
                    resized = resized.convert("RGBA")
                save_kwargs.update({"format": "PNG"})
            elif ext == ".webp":
                save_kwargs.update(
                    {
                        "format": "WEBP",
                        "quality": 95,
                    }
                )
            else:
                # Fallback seguro: salvar no formato original detectado pelo Pillow
                save_kwargs["format"] = img.format or "JPEG"

            resized.save(resized_path, **save_kwargs)
            return resized_path

    except Exception as exc:
        raise ImageResizeError(f"Falha ao redimensionar imagem: {path}") from exc