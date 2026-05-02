import pytest
from pathlib import Path
from PIL import Image
from app.shared.services.image.converter import convert_if_needed, ImageConversionError

@pytest.fixture
def temp_jpg_path(tmp_path):
    path = tmp_path / "test.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(path)
    return path

def test_convert_if_needed_no_action_for_jpg(temp_jpg_path):
    # Não deve fazer nada se for JPG
    converted_path = convert_if_needed(temp_jpg_path)
    assert converted_path == temp_jpg_path
    assert converted_path.suffix == ".jpg"

# Nota: Testar HEIC real exige um arquivo .heic físico ou mockar a Image.open
# Como não temos um .heic aqui, vamos focar no comportamento de bypass e erros básicos.

def test_convert_if_needed_non_existent():
    # Se não existe, Path().resolve() pode falhar ou o Image.open vai falhar
    # O converter atual não checa existência explicitamente antes do Image.open
    with pytest.raises(Exception):
        convert_if_needed("non_existent.heic")
