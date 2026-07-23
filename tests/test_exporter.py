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
