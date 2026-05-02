import pytest
from pathlib import Path
from PIL import Image
from app.shared.services.image.resizer import resize_image

@pytest.fixture
def large_image_path(tmp_path):
    # Cria uma imagem maior que o skip (200KB) e maior que Full HD para forçar resize
    path = tmp_path / "large.jpg"
    img = Image.new("RGB", (3000, 2000), color="green")
    img.save(path)
    return path

@pytest.fixture
def small_image_path(tmp_path):
    # Cria uma imagem menor que o skip (200KB)
    path = tmp_path / "small.jpg"
    img = Image.new("RGB", (100, 100), color="white")
    img.save(path)
    return path

def test_resize_image_skip_small(small_image_path):
    # Deve pular se for pequena
    resized_path = resize_image(small_image_path, min_size_skip=1000000)
    assert resized_path == small_image_path

def test_resize_image_execute_large(large_image_path):
    # Deve redimensionar se for grande
    # min_size_skip baixo para garantir execução
    resized_path = resize_image(large_image_path, max_width=1000, max_height=1000, min_size_skip=10)
    
    assert resized_path != large_image_path
    assert resized_path.exists()
    
    with Image.open(resized_path) as img:
        w, h = img.size
        assert w <= 1000
        assert h <= 1000
        # Checa proporção (3:2 original)
        assert w == 1000
        assert h == round(1000 * 2000 / 3000)

def test_resize_image_already_within_limits(tmp_path):
    path = tmp_path / "within.jpg"
    img = Image.new("RGB", (800, 600), color="yellow")
    img.save(path)
    
    resized_path = resize_image(path, max_width=1000, max_height=1000, min_size_skip=10)
    assert resized_path == path
