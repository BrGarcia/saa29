"""
app/shared/exporter.py
Utilitário genérico para exportação de relatórios em CSV e XLSX.
"""

import io
import csv
from typing import Sequence, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def gerar_csv(headers: list[str], rows: Sequence[Sequence[Any]]) -> str:
    """Gera uma string CSV formatada (UTF-8 com BOM para Excel carregar acentos corretamente)."""
    output = io.StringIO()
    # Ecrever BOM UTF-8
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([str(item) if item is not None else "" for item in row])
    return output.getvalue()


def gerar_xlsx(titulo_aba: str, headers: list[str], rows: Sequence[Sequence[Any]]) -> bytes:
    """Gera os bytes de um arquivo Excel (.xlsx) estilizado."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo_aba[:31]  # Limite do Excel de 31 caracteres para abas

    # Estilos
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    data_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )

    # Escrever Cabeçalho
    ws.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    # Escrever Linhas de Dados
    for row_idx, row_data in enumerate(rows, start=2):
        formatted_row = [str(item) if item is not None else "" for item in row_data]
        ws.append(formatted_row)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border

    # Ajustar largura automática de colunas
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
