import pytest
from pathlib import Path
from PIL import Image
from app.shared.services.image.optimizer import optimize_image

@pytest.fixture
def temp_png_path(tmp_path):
    path = tmp_path / "test.png"
    # Cria uma imagem colorida para que o WebP tenha o que comprimir
    img = Image.new("RGB", (200, 200), color="orange")
    img.save(path)
    return path

def test_optimize_image_to_webp(temp_png_path):
    # Deve converter para WebP
    optimized_path = optimize_image(temp_png_path)
    
    assert optimized_path.exists()
    assert optimized_path.suffix == ".webp"
    assert optimized_path != temp_png_path

def test_optimize_image_already_webp(tmp_path):
    path = tmp_path / "test.webp"
    img = Image.new("RGB", (100, 100), color="purple")
    img.save(path, format="WEBP")
    
    optimized_path = optimize_image(path)
    assert optimized_path == path

def test_optimize_image_custom_output(temp_png_path, tmp_path):
    custom_output = tmp_path / "custom" / "my_image.webp"
    custom_output.parent.mkdir()
    
    optimized_path = optimize_image(temp_png_path, output_path=custom_output)
    assert optimized_path == custom_output
    assert optimized_path.exists()
