import zipfile
import pytest
from pathlib import Path
from scripts.publicacoes.publicar import (
    validar_pacote_zip,
    extrair_pacote_zip_seguro,
    ValidacaoZipError,
)


def test_validar_pacote_zip_valido(tmp_path: Path):
    zip_path = tmp_path / "valid.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Manuais/AMM/01_intro.pdf", b"%PDF-1.4 dummy pdf content")
        zf.writestr("fim.json", b'{"test": 1}')

    entradas, ignoradas = validar_pacote_zip(zip_path)
    assert entradas == 2
    assert ignoradas == []


def test_validar_pacote_zip_zip_slip(tmp_path: Path):
    zip_path = tmp_path / "zip_slip.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", b"malicious content")

    with pytest.raises(ValidacaoZipError, match="Zip-Slip risk"):
        validar_pacote_zip(zip_path)


def test_validar_pacote_zip_extensao_proibida_e_ignorada_sem_bloquear_pacote(tmp_path: Path):
    """
    Disco bruto legitimamente contém instaladores/autorun do leitor de
    manuais. Em vez de rejeitar o pacote inteiro (comportamento antigo), a
    entrada proibida deve ser reportada em `ignoradas` para não ser extraída.
    """
    zip_path = tmp_path / "disco.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Manuais/AMM/01_intro.pdf", b"%PDF-1.4 dummy pdf content")
        zf.writestr("Autorun/instalador.exe", b"executable content")

    entradas, ignoradas = validar_pacote_zip(zip_path)
    assert entradas == 2
    assert ignoradas == ["Autorun/instalador.exe"]


def test_validar_pacote_zip_muitas_entradas(tmp_path: Path):
    zip_path = tmp_path / "too_many.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for i in range(15):
            zf.writestr(f"file_{i}.txt", b"a")

    with pytest.raises(ValidacaoZipError, match="muitas entradas"):
        validar_pacote_zip(zip_path, max_entradas=10)


def test_extrair_pacote_zip_seguro_pula_entradas_ignoradas(tmp_path: Path):
    zip_path = tmp_path / "disco.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Manuais/AMM/01_intro.pdf", b"%PDF-1.4 dummy pdf content")
        zf.writestr("Autorun/instalador.exe", b"executable content")

    entradas, ignoradas = validar_pacote_zip(zip_path)
    destino = tmp_path / "extraido"
    destino.mkdir()
    extrair_pacote_zip_seguro(zip_path, destino, ignoradas)

    assert (destino / "Manuais/AMM/01_intro.pdf").is_file()
    assert not (destino / "Autorun/instalador.exe").exists()
