"""
app/modules/inspecoes/pdf_service.py
Serviço de geração de relatórios PDF (Ordem de Serviço / Inspeção) via ReportLab.
"""

import io
import uuid
from datetime import datetime, date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from app.modules.inspecoes.models import Inspecao, InspecaoTarefa
from app.modules.equipamentos.models import Instalacao, ItemEquipamento
from app.modules.vencimentos.models import ControleVencimento
from app.shared.core import exceptions as domain_exc


def _format_date(d: Any, fmt: str = "%d/%m/%Y") -> str:
    if not d:
        return "---"
    if isinstance(d, datetime):
        return d.strftime(fmt + " %H:%M")
    if isinstance(d, date):
        return d.strftime(fmt)
    return str(d)


async def gerar_pdf_ordem_inspecao(db: AsyncSession, inspecao_id: uuid.UUID) -> bytes:
    """
    Gera o PDF formatado (A4 Retrato) da Ordem de Inspeção com Checklist,
    Inventário Completo da Aeronave e Tabela de Vencimentos/Calibrações.
    Operação 100% passiva e somente-leitura.
    """
    # 1. Carregar dados completos da inspeção
    result = await db.execute(
        select(Inspecao)
        .where(Inspecao.id == inspecao_id)
        .options(
            selectinload(Inspecao.aeronave),
            selectinload(Inspecao.tipos_aplicados),
            selectinload(Inspecao.aberto_por),
            selectinload(Inspecao.concluido_por),
            selectinload(Inspecao.tarefas).selectinload(InspecaoTarefa.executado_por),
        )
    )
    inspecao = result.scalar_one_or_none()
    if not inspecao:
        raise domain_exc.EntidadeNaoEncontradaError("Inspeção não encontrada.")

    # 2. Carregar inventário completo instalado na aeronave
    aeronave_id = inspecao.aeronave_id
    stmt_inst = (
        select(Instalacao)
        .where(Instalacao.aeronave_id == aeronave_id, Instalacao.data_remocao.is_(None))
        .options(
            selectinload(Instalacao.slot),
            selectinload(Instalacao.item).selectinload(ItemEquipamento.modelo),
            selectinload(Instalacao.item)
            .selectinload(ItemEquipamento.controles_vencimento)
            .selectinload(ControleVencimento.tipo_controle),
        )
    )
    res_inst = await db.execute(stmt_inst)
    todas_instalacoes = list(res_inst.scalars().all())

    # Filtrar apenas instalações onde o item possui controles de vencimento cadastrados
    itens_controlados = [
        inst for inst in todas_instalacoes if inst.item and inst.item.controles_vencimento
    ]

    # 3. Montar documento PDF com ReportLab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
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
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#FFFFFF"),
        backColor=colors.HexColor("#1F497D"),
        spaceBefore=8,
        spaceAfter=6,
        borderPadding=(4, 6, 4, 6),
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

    elements = []

    # --- CABEÇALHO DO DOCUMENTO ---
    header_data = [
        [
            Paragraph("<b>FORÇA AÉREA BRASILEIRA</b><br/>SISTEMA DE GESTÃO DE PANES E MANUTENÇÃO — ELETRÔNICA A-29 (SAA29)", title_style),
        ],
        [
            Paragraph("<b>ORDEM DE INSPEÇÃO E MANUTENÇÃO PROGRAMADA</b>", subtitle_style)
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

    # --- BLOCO 1: IDENTIFICAÇÃO DA INSPEÇÃO ---
    elements.append(Paragraph("<b>1. IDENTIFICAÇÃO DA INSPEÇÃO</b>", section_heading))
    
    matricula = inspecao.aeronave.matricula if inspecao.aeronave else "---"
    tipos_str = " / ".join([t.nome for t in inspecao.tipos_aplicados]) if inspecao.tipos_aplicados else "---"
    aberto_por_str = inspecao.aberto_por.trigrama if (inspecao.aberto_por and inspecao.aberto_por.trigrama) else (inspecao.aberto_por.nome if inspecao.aberto_por else "---")
    
    dt_inicio = _format_date(inspecao.data_inicio, "%d/%m/%Y")
    dt_dpe = _format_date(inspecao.data_fim_prevista, "%d/%m/%Y")
    dt_gerado = datetime.now().strftime("%d/%m/%Y %H:%M")

    info_data = [
        [
            Paragraph("<b>Aeronave:</b>", label_style), Paragraph(matricula, val_style),
            Paragraph("<b>Status Inspeção:</b>", label_style), Paragraph(f"<b>{inspecao.status}</b>", val_style),
        ],
        [
            Paragraph("<b>Tipo(s) Inspeção:</b>", label_style), Paragraph(tipos_str, val_style),
            Paragraph("<b>Responsável (Abertura):</b>", label_style), Paragraph(aberto_por_str, val_style),
        ],
        [
            Paragraph("<b>Data Início:</b>", label_style), Paragraph(dt_inicio, val_style),
            Paragraph("<b>DPE (Data Prevista):</b>", label_style), Paragraph(dt_dpe, val_style),
        ],
        [
            Paragraph("<b>Emitido em:</b>", label_style), Paragraph(dt_gerado, val_style),
            Paragraph("<b>Observações:</b>", label_style), Paragraph(inspecao.observacoes or "Nenhuma", val_style),
        ]
    ]

    info_table = Table(info_data, colWidths=[95, 165, 110, 150])
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
    elements.append(Spacer(1, 10))

    # --- CHECKLIST DE TAREFAS ---
    elements.append(Paragraph("<b>2. CHECKLIST DE TAREFAS DA INSPEÇÃO</b>", section_heading))

    tarefas_data = [
        [
            Paragraph("<b>Item</b>", table_header_style),
            Paragraph("<b>Tarefa / Descrição</b>", table_header_style),
            Paragraph("<b>Status</b>", table_header_style),
            Paragraph("<b>Resp. (Trigrama)</b>", table_header_style),
            Paragraph("<b>Atualizado em</b>", table_header_style),
            Paragraph("<b>Observações</b>", table_header_style),
        ]
    ]

    tarefas_ordenadas = sorted(inspecao.tarefas, key=lambda t: t.ordem) if inspecao.tarefas else []
    
    if not tarefas_ordenadas:
        tarefas_data.append([
            Paragraph("---", cell_style_center),
            Paragraph("Nenhuma tarefa cadastrada nesta inspeção.", cell_style),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style),
        ])
    else:
        for idx, t in enumerate(tarefas_ordenadas, start=1):
            executor_str = "---"
            if t.executado_por:
                executor_str = t.executado_por.trigrama or t.executado_por.nome
            
            dt_exec = _format_date(t.data_execucao)

            status_color = "#333333"
            if t.status == "CONCLUIDA":
                status_color = "#166534"
            elif t.status == "PENDENTE":
                status_color = "#854D0E"
            elif t.status == "ANOMALIA":
                status_color = "#991B1B"

            status_para = Paragraph(f"<font color='{status_color}'><b>{t.status}</b></font>", cell_style_center)
            titulo_para = Paragraph(f"<b>{t.titulo}</b><br/><font color='#555555'>{t.descricao or ''}</font>", cell_style)
            obs_para = Paragraph(t.observacao_execucao or "", cell_style)

            tarefas_data.append([
                Paragraph(f"{idx:02d}", cell_style_center),
                titulo_para,
                status_para,
                Paragraph(executor_str, cell_style_center),
                Paragraph(dt_exec, cell_style_center),
                obs_para,
            ])

    tarefas_table = Table(tarefas_data, colWidths=[30, 180, 75, 75, 75, 85])
    tarefas_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F497D")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(tarefas_table)

    # --- QUEBRA DE PÁGINA OBRIGATÓRIA PARA O INVENTÁRIO ---
    elements.append(PageBreak())

    # --- BLOCO 3: INVENTÁRIO COMPLETO DA AERONAVE ---
    elements.append(Paragraph(f"<b>3. INVENTÁRIO COMPLETO DA AERONAVE ({matricula})</b>", section_heading))
    elements.append(Paragraph("<i>Relação geral de todos os equipamentos aviônicos instalados na célula.</i>", val_style))
    elements.append(Spacer(1, 6))

    inv_full_headers = [
        Paragraph("<b>Slot / Posição</b>", table_header_style),
        Paragraph("<b>Equipamento / Modelo</b>", table_header_style),
        Paragraph("<b>Part Number (PN)</b>", table_header_style),
        Paragraph("<b>Serial (SN)</b>", table_header_style),
        Paragraph("<b>Data Instalação</b>", table_header_style),
    ]
    
    inv_full_rows = [inv_full_headers]

    if not todas_instalacoes:
        inv_full_rows.append([
            Paragraph("---", cell_style_center),
            Paragraph("Nenhum equipamento instalado nesta aeronave.", cell_style),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style_center),
        ])
    else:
        for inst in todas_instalacoes:
            slot_nome = inst.slot.nome_posicao if inst.slot else "---"
            item = inst.item
            nome_eq = item.modelo.nome_generico if (item and item.modelo) else "---"
            pn = item.modelo.part_number if (item and item.modelo) else "---"
            sn = item.numero_serie if item else "---"
            dt_inst = _format_date(inst.data_instalacao, "%d/%m/%Y")

            inv_full_rows.append([
                Paragraph(slot_nome, cell_style),
                Paragraph(nome_eq, cell_style),
                Paragraph(pn, cell_style_center),
                Paragraph(sn, cell_style_center),
                Paragraph(dt_inst, cell_style_center),
            ])

    inv_full_table = Table(inv_full_rows, colWidths=[110, 150, 100, 80, 80])
    inv_full_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F497D")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(inv_full_table)
    elements.append(Spacer(1, 14))

    # --- BLOCO 4: VENCIMENTOS E CALIBRAÇÕES DA AERONAVE ---
    elements.append(Paragraph(f"<b>4. VENCIMENTOS E CALIBRAÇÕES CONTROLADAS ({matricula})</b>", section_heading))
    elements.append(Paragraph("<i>Exibindo exclusivamente componentes com regras de calibração/vencimento temporal monitorado.</i>", val_style))
    elements.append(Spacer(1, 6))

    venc_headers = [
        Paragraph("<b>Slot / Posição</b>", table_header_style),
        Paragraph("<b>Equipamento</b>", table_header_style),
        Paragraph("<b>Part Number (PN)</b>", table_header_style),
        Paragraph("<b>Serial (SN)</b>", table_header_style),
        Paragraph("<b>Tipo Controle</b>", table_header_style),
        Paragraph("<b>Próximo Vencimento</b>", table_header_style),
    ]
    
    venc_rows = [venc_headers]

    if not itens_controlados:
        venc_rows.append([
            Paragraph("---", cell_style_center),
            Paragraph("Nenhum item com vencimento controlado instalado na aeronave.", cell_style),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style_center),
            Paragraph("---", cell_style_center),
        ])
    else:
        for inst in itens_controlados:
            slot_nome = inst.slot.nome_posicao if inst.slot else "---"
            item = inst.item
            nome_eq = item.modelo.nome_generico if (item and item.modelo) else "---"
            pn = item.modelo.part_number if (item and item.modelo) else "---"
            sn = item.numero_serie if item else "---"

            for ctrl in (item.controles_vencimento if item else []):
                tipo_ctrl_nome = ctrl.tipo_controle.nome if ctrl.tipo_controle else "---"
                dt_venc = _format_date(ctrl.data_vencimento, "%d/%m/%Y")
                status_venc = ctrl.status or "OK"

                venc_color = "#166534"
                if status_venc == "VENCIDO":
                    venc_color = "#991B1B"
                elif status_venc == "VENCENDO":
                    venc_color = "#854D0E"
                elif status_venc == "PRORROGADO":
                    venc_color = "#1D4ED8"

                venc_para = Paragraph(f"{dt_venc}<br/><font color='{venc_color}'><b>({status_venc})</b></font>", cell_style_center)

                venc_rows.append([
                    Paragraph(slot_nome, cell_style),
                    Paragraph(nome_eq, cell_style),
                    Paragraph(pn, cell_style_center),
                    Paragraph(sn, cell_style_center),
                    Paragraph(tipo_ctrl_nome, cell_style_center),
                    venc_para,
                ])

    venc_table = Table(venc_rows, colWidths=[90, 110, 85, 75, 80, 80])
    venc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F497D")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(venc_table)

    # 4. Construir PDF em memória
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
