import pytest
from pathlib import Path
from PIL import Image
from app.shared.services.image.pipeline import process_image

@pytest.fixture
def source_image(tmp_path):
    path = tmp_path / "source.jpg"
    # Imagem grande o suficiente para disparar resize
    img = Image.new("RGB", (2000, 2000), color="cyan")
    img.save(path)
    return path

@pytest.fixture
def source_bytes(source_image):
    return source_image.read_bytes()

def test_process_image_full_pipeline_path(source_image, tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    final_path_str = process_image(
        source_image, 
        output_path=output_dir,
        max_width=1000,
        max_height=1000,
        min_size_skip=10 # Força resize
    )
    
    final_path = Path(final_path_str)
    assert final_path.exists()
    assert final_path.suffix == ".webp"
    assert final_path.parent == output_dir.resolve()
    
    with Image.open(final_path) as img:
        w, h = img.size
        assert w <= 1000
        assert h <= 1000

def test_process_image_full_pipeline_bytes(source_bytes):
    # Deve retornar bytes quando recebe bytes
    result_bytes = process_image(
        source_bytes,
        filename_hint="camera.jpg",
        max_width=500,
        max_height=500,
        min_size_skip=10
    )
    
    assert isinstance(result_bytes, bytes)
    assert len(result_bytes) > 0
    
    # Valida se os bytes resultantes são uma imagem WebP válida
    import io
    with Image.open(io.BytesIO(result_bytes)) as img:
        assert img.format == "WEBP"
        w, h = img.size
        assert w <= 500
        assert h <= 500

def test_process_image_isolation_no_leaks(source_image, tmp_path):
    # O pipeline não deve deixar lixo no diretório original
    # nem modificar o original
    original_mtime = source_image.stat().st_mtime

    final_path_str = process_image(
        source_image,
        max_width=500,
        max_height=500,
        min_size_skip=10
    )

    assert source_image.exists()
    assert source_image.stat().st_mtime == original_mtime

    # O arquivo intermediário _resized.jpg NÃO deve existir no diretório original
    # (Pois agora usamos TemporaryDirectory internamente)
    resized_path = source_image.with_name(f"{source_image.stem}_resized{source_image.suffix}")
    assert not resized_path.exists()


def test_process_image_cleans_up_temp_directory(source_image, tmp_path):
    """Garante que o TemporaryDirectory criado pelo pipeline é removido após a execução."""
    import tempfile
    from unittest.mock import patch, MagicMock

    captured_tmp_dirs: list[str] = []
    _original_tmp_dir = tempfile.TemporaryDirectory

    class _CapturingTmpDir:
        """Wrapper que delega ao TemporaryDirectory real e captura o caminho."""

        def __init__(self, *args, **kwargs):
            self._real = _original_tmp_dir(*args, **kwargs)
            captured_tmp_dirs.append(self._real.name)

        def __enter__(self):
            return self._real.__enter__()

        def __exit__(self, *args):
            return self._real.__exit__(*args)

    with patch("app.shared.services.image.pipeline.tempfile.TemporaryDirectory", _CapturingTmpDir):
        process_image(source_image, max_width=500, max_height=500, min_size_skip=10)

    assert len(captured_tmp_dirs) == 1, "Exatamente um TemporaryDirectory deve ter sido criado"
    tmp_path_created = Path(captured_tmp_dirs[0])
    assert not tmp_path_created.exists(), (
        f"TemporaryDirectory '{tmp_path_created}' não foi removido após o pipeline"
    )
