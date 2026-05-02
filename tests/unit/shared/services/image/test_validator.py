import pytest
from pathlib import Path
from PIL import Image
import io
from app.shared.services.image.validator import validate_image, ImageValidationError

@pytest.fixture
def temp_image_path(tmp_path):
    path = tmp_path / "test.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(path)
    return path

@pytest.fixture
def temp_image_bytes(temp_image_path):
    return temp_image_path.read_bytes()

def test_validate_image_success(temp_image_path):
    validated_path = validate_image(temp_image_path)
    assert validated_path == temp_image_path

def test_validate_image_bytes_success(temp_image_bytes):
    validated_bytes = validate_image(temp_image_bytes)
    assert validated_bytes == temp_image_bytes

def test_validate_image_not_found():
    with pytest.raises(FileNotFoundError):
        validate_image("non_existent.jpg")

def test_validate_image_invalid_extension(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("not an image")
    with pytest.raises(ImageValidationError, match="Extensão não suportada"):
        validate_image(path)

def test_validate_image_empty_file(tmp_path):
    path = tmp_path / "empty.jpg"
    path.write_bytes(b"")
    with pytest.raises(ImageValidationError, match="Arquivo vazio ou corrompido"):
        validate_image(path)

def test_validate_image_corrupted(tmp_path):
    path = tmp_path / "corrupted.jpg"
    path.write_bytes(b"not a real image content")
    with pytest.raises(ImageValidationError, match="Arquivo não parece ser uma imagem válida"):
        validate_image(path)
