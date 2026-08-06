"""
scripts/gerar_pdf_checklist_delineamento.py
Gerador do PDF formatado do Checklist de Eletrônica (Delineamento Inspeções A-29)
utilizando ReportLab com o padrão visual da Ordem de Serviço (OS) do SAA29.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


def gerar_pdf_checklist(filename: str = "docs/CHECKLIST Delineamento A-29.pdf"):
    """Gera o arquivo PDF do Checklist de Delineamento A-29 com o layout padronizado da OS."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=36,   # ~13mm
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#1F497D"),
        alignment=TA_CENTER,
    )

    subtitle_style = ParagraphStyle(
        "HeaderSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#333333"),
        alignment=TA_CENTER,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=11.5,
        textColor=colors.HexColor("#FFFFFF"),
        backColor=colors.HexColor("#1F497D"),
        spaceBefore=7,
        spaceAfter=5,
        borderPadding=(4, 6, 4, 6),
    )

    subsection_heading = ParagraphStyle(
        "SubSectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#1F497D"),
        spaceBefore=4,
        spaceAfter=3,
    )

    label_style = ParagraphStyle(
        "LabelStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1F497D"),
    )

    val_style = ParagraphStyle(
        "ValueStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#111111"),
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#FFFFFF"),
        alignment=TA_CENTER,
    )

    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#222222"),
    )

    cell_style_center = ParagraphStyle(
        "TableCellCenter",
        parent=cell_style,
        alignment=TA_CENTER,
    )

    manual_box_style = ParagraphStyle(
        "ManualBox",
        parent=cell_style_center,
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#555555"),
    )

    elements = []

    # --- CABEÇALHO PADRÃO FAB / SAA29 ---
    header_data = [
        [
            Paragraph("<b>FORÇA AÉREA BRASILEIRA</b><br/>SISTEMA DE GESTÃO DE PANES E MANUTENÇÃO — ELETRÔNICA A-29 (SAA29)", title_style),
        ],
        [
            Paragraph("<b>CHECKLIST DE ELETRÔNICA — DELINEAMENTO DE INSPEÇÕES A-29</b>", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1F497D"), spaceBefore=4, spaceAfter=8))

    # --- BLOCO 1: IDENTIFICAÇÃO DA ANV E INSPEÇÃO ---
    elements.append(Paragraph("<b>1. IDENTIFICAÇÃO DA AERONAVE E INSPEÇÃO</b>", section_heading))

    info_data = [
        [
            Paragraph("<b>Aeronave (ANV):</b>", label_style), Paragraph("____________________", val_style),
            Paragraph("<b>Inspeção:</b>", label_style), Paragraph("____________________", val_style),
        ],
        [
            Paragraph("<b>Data da Inspeção:</b>", label_style), Paragraph("____/____/________", val_style),
            Paragraph("<b>Inspetor Responsável:</b>", label_style), Paragraph("____________________", val_style),
        ]
    ]

    info_table = Table(info_data, colWidths=[100, 160, 100, 160])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8))

    def build_checklist_table(items, col_widths=(28, 352, 60, 80)):
        headers = [
            Paragraph("<b>Item</b>", table_header_style),
            Paragraph("<b>Descrição da Tarefa de Inspeção / Delineamento</b>", table_header_style),
            Paragraph("<b>Status</b>", table_header_style),
            Paragraph("<b>Visto / Obs.</b>", table_header_style),
        ]
        rows = [headers]
        for num, text, extra_info in items:
            desc_content = f"<b>{text}</b>"
            if extra_info:
                desc_content += f"<br/><font color='#555555'>{extra_info}</font>"
            
            rows.append([
                Paragraph(f"<b>{num:02d}</b>" if isinstance(num, int) else f"<b>{num}</b>", cell_style_center),
                Paragraph(desc_content, cell_style),
                Paragraph("[  ] OK<br/>[  ] PNE", manual_box_style),
                Paragraph("________", cell_style_center),
            ])

        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F497D")),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ]))
        return t

    # --- BLOCO 2: RELATÓRIO DE VOO ---
    elements.append(Paragraph("<b>2. RELATÓRIO DE VOO</b>", section_heading))
    items_relatorio = [
        (1, "Verificar as Panes de Parte 2 e Horas de Célula da ANV", None),
        (2, "Verificar as Panes de Parte 3", None),
        (3, "Verificar os Itens a vencer na Parte 4", None),
    ]
    elements.append(build_checklist_table(items_relatorio))
    elements.append(Spacer(1, 8))

    # --- BLOCO 3: INSPEÇÃO VISUAL ---
    elements.append(Paragraph("<b>3. INSPEÇÃO VISUAL</b>", section_heading))
    items_visual = [
        (4, "Verificar o estado geral do Descarregador de estática do TDP de Nariz e selagem dos parafusos", None),
        (5, "Verificar o estado geral dos conjuntos (descarregadores e Parafusos) das superfícies de comando quanto à corrosão", None),
        (6, "Verificar o estado geral das antenas quanto à instalação, corrosão e selagem", None),
        (7, "Verificar o estado geral dos equipamentos nos compartimentos eletrônico e de V/UHF, quanto a instalação, plugs, corrosão e vencimentos", None),
        (8, "Verificar a Instalação dos equipamentos nas cabines 1p/2p, quanto à correta fixação", None),
        (9, "Verificar o estado geral das telas CMFD’s, HUD e UFCP, quanto a arranhões e trincas", None),
        (10, "Verificar o estado geral e a instalação dos cabos de comunicação nos assentos 1p/2p", None),
        (11, "Verificar o estado Geral dos knob’s de controle dos equipamentos eletrônicos nas cabines 1p/2p", None),
        (12, "Verificar Estado geral e instalação (frenos) dos Stick Grips 1p/2p", None),
        (13, "Verificar Estado geral e instalação PTT e TDC das manetes 1p/2p", None),
        (14, "Ligar a aeronave e verificar as Falhas ativas nas páginas PFL e BIT", None),
    ]
    elements.append(build_checklist_table(items_visual))
    elements.append(Spacer(1, 6))

    ofp_data = [
        [
            Paragraph("<b>VERSÕES OFP MDP:</b>", label_style),
            Paragraph("<b>MDP1:</b> ___________________________ [  ] CHECKLIST MDP1", val_style),
            Paragraph("<b>MDP2:</b> ___________________________ [  ] CHECKLIST MDP2", val_style),
        ]
    ]
    ofp_table = Table(ofp_data, colWidths=[110, 205, 205])
    ofp_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(ofp_table)
    elements.append(Spacer(1, 8))

    # --- BLOCO 4: CHECKS DOS SISTEMAS ---
    elements.append(Paragraph("<b>4. CHECKS DOS SISTEMAS</b>", section_heading))
    
    elements.append(Paragraph("<b>4.1. Na Cabine do 1P (Piloto):</b>", subsection_heading))
    items_1p = [
        (15, "Colocar o EGIR para o Modo TEST, após o END TEST colocar para alinhamento no modo STHD e verificar se o READY cicla com menos de 1 min", "Parâmetros: HDG EGIR: ________ | HDG BCKP: ________"),
        (16, "Checar o funcionamento e validade do GPS STANDALONE", None),
        (17, "Checar o funcionamento interfone, ajuste do VOX do volume, PTT do manche 1p e tecla PTT do ASP 1p", None),
        (18, "Checar o correto funcionamento dos alertas FIRE, WARN e CAUTION tanto na sua forma visual (Botões em cima dos CMFD’s, EICAS e HUD) quanto Aural (Fones)", None),
        (19, "Checar o áudio e indicações (PÁGINA ADHSI) do VOR, DME, ADF e fazer check rádio com V/UHF1 e V/UHF2", None),
        (20, "Realizar BIT teste dos sistemas nas páginas BIT P e BIT M, verificar falhas de DATALINK (VUHF2 024/025 FAIL)", None),
        (21, "Verificar o funcionamento do HUD, da CHVC, do UFCP de todas as suas teclas e observar a existência de falhas de pixels ou indicações", None),
        (22, "Realizar o teste da ARTU", None),
        (23, "Realizar teste do HOTAS e dos botões de comando dos compensadores Pitch, Roll e Yaw", None),
        (24, "Realizar teste do P.A", None),
        (25, "Checar o funcionamento da iluminação dos painéis no modo noturno, bem como a atenuação do Brilho dos CMFD’s e HUD/UFCP", None),
    ]
    elements.append(build_checklist_table(items_1p))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("<b>4.2. Na Cabine do 2P (Copiloto):</b>", subsection_heading))
    items_2p = [
        (26, "Checar funcionamento interfone, ajuste do VOX do volume, PTT do manche 2p e tecla PTT do ASP 2p", None),
        (27, "Checar o correto funcionamento dos alertas FIRE, WARN e CAUTION tanto na sua forma visual (Botões em cima dos CMFD’s, EICAS e HUD) quanto Aural (Fones)", None),
        (28, "Checar o áudio e indicações (PÁGINA ADHSI) do VOR, DME, ADF e fazer check rádio com V/UHF1 e V/UHF2", None),
        (29, "Realizar o teste da ARTU", None),
        (30, "Realizar teste do HOTAS e dos botões de comando dos compensadores Pitch, Roll e Yaw", None),
        (31, "Checar o funcionamento da iluminação dos painéis no modo noturno, bem como a atenuação do Brilho dos CMFD’s e HUD/UFCP", None),
        (32, "Checar o Funcionamento dos Botões ON/OFF dos CMFD", None),
    ]
    elements.append(build_checklist_table(items_2p))
    elements.append(Spacer(1, 8))

    # --- BLOCO 5: DELINEAMENTO ---
    elements.append(Paragraph("<b>5. DELINEAMENTO E SILOMS</b>", section_heading))
    items_delineamento = [
        (33, "Preencher o Delineamento e lançar as tarefas delineadas no SILOMS", None),
    ]
    elements.append(build_checklist_table(items_delineamento))
    elements.append(Spacer(1, 8))

    # --- BLOCO 6: DISCREPÂNCIAS E OBSERVAÇÕES ---
    elements.append(Paragraph("<b>6. DISCREPÂNCIAS / OBSERVAÇÕES ENCONTRADAS</b>", section_heading))
    
    disc_data = [
        [Paragraph("<i>Espaço destinado para anotação manual de panes ou discrepâncias encontradas durante a inspeção:</i><br/><br/><br/><br/><br/>", manual_box_style)]
    ]
    disc_table = Table(disc_data, colWidths=[520])
    disc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFFFFF")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(disc_table)
    elements.append(Spacer(1, 14))

    # --- BLOCO DE ASSINATURA ---
    sig_data = [
        [
            Paragraph("<b>INSPETOR DE ELETRÔNICA:</b>", label_style),
            Paragraph("____________________________________________", val_style),
            Paragraph("<b>DATA:</b>", label_style),
            Paragraph("____/____/________", val_style),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[130, 210, 50, 130])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    print(f"PDF gerado com sucesso em: {filename}")


if __name__ == "__main__":
    gerar_pdf_checklist()
