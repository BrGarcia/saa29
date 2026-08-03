"""
tests/test_exporter.py
Testes unitários para o gerador de relatórios CSV e XLSX.
"""

import pytest
from app.shared.exporter import gerar_csv, gerar_xlsx


def test_gerar_csv():
    headers = ["Coluna A", "Coluna B"]
    rows = [["Dado 1", 123], ["Dado 2", None]]
    
    csv_out = gerar_csv(headers, rows)
    
    assert "\ufeff" in csv_out
    assert "Coluna A;Coluna B" in csv_out
    assert "Dado 1;123" in csv_out
    assert "Dado 2;" in csv_out


def test_gerar_xlsx():
    headers = ["Header 1", "Header 2"]
    rows = [["Val 1", 100], ["Val 2", 200]]
    
    xlsx_bytes = gerar_xlsx("AbaTeste", headers, rows)
    
    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 0
    # Valida mágicos de arquivo zip (.xlsx é um container ZIP PK)
    assert xlsx_bytes[:2] == b"PK"


def test_gerar_xlsx_calcula_largura_de_coluna_em_passada_unica():
    """Item #7/Etapa 5: a largura de coluna passou a ser acumulada durante a
    mesma passada de escrita, em vez de uma segunda leitura completa via
    `ws.columns`. Confirma que o resultado visível (largura calculada) é
    equivalente ao comportamento anterior: max(maior_valor + 4, 12)."""
    import openpyxl
    import io as _io

    headers = ["Nome"]
    rows = [["Um valor bem comprido para testar largura"], ["curto"]]
    xlsx_bytes = gerar_xlsx("Teste", headers, rows)
    wb = openpyxl.load_workbook(_io.BytesIO(xlsx_bytes))
    ws = wb.active

    maior_valor = len("Um valor bem comprido para testar largura")
    largura_esperada = max(maior_valor + 4, 12)
    assert ws.column_dimensions["A"].width == largura_esperada
