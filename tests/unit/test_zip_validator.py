import io
import zipfile
import pytest
from pathlib import Path
from scripts.publicacoes.publicar import validar_pacote_zip, ValidacaoZipError


def test_validar_pacote_zip_valido(tmp_path: Path):
    zip_path = tmp_path / "valid.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Manuais/AMM/01_intro.pdf", b"%PDF-1.4 dummy pdf content")
        zf.writestr("fim.json", b'{"test": 1}')

    entradas = validar_pacote_zip(zip_path)
    assert entradas == 2


def test_validar_pacote_zip_zip_slip(tmp_path: Path):
    zip_path = tmp_path / "zip_slip.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", b"malicious content")

    with pytest.raises(ValidacaoZipError, match="Zip-Slip risk"):
        validar_pacote_zip(zip_path)


def test_validar_pacote_zip_extensao_proibida(tmp_path: Path):
    zip_path = tmp_path / "malware.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Manuais/payload.exe", b"executable content")

    with pytest.raises(ValidacaoZipError, match="proibida encontrada"):
        validar_pacote_zip(zip_path)


def test_validar_pacote_zip_muitas_entradas(tmp_path: Path):
    zip_path = tmp_path / "too_many.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for i in range(15):
            zf.writestr(f"file_{i}.txt", b"a")

    with pytest.raises(ValidacaoZipError, match="muitas entradas"):
        validar_pacote_zip(zip_path, max_entradas=10)
