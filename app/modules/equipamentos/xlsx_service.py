"""
app/modules/equipamentos/xlsx_service.py
Serviço de processamento de inventário via arquivo XLSX.
"""
import os
import uuid
from io import BytesIO
from dataclasses import dataclass, field

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario
from app.modules.equipamentos import schemas, service as equip_service


@dataclass
class XlsxPreviewItem:
    """Representa um item individual na prévia do XLSX."""
    slot_id: uuid.UUID
    nome_posicao: str
    pn: str
    posicao_xlsx: str
    sn_encontrado: str | None
    status: str  # 'OK', 'NOT_FOUND', 'REMOVED'
    status_msg: str

@dataclass
class XlsxResultado:
    """Relatório de processamento do XLSX."""
    matricula: str = ""
    total_linhas: int = 0
    pns_encontrados: int = 0
    pns_ignorados: int = 0
    itens_atualizados: int = 0
    erros: list[str] = field(default_factory=list)
    detalhes: list[str] = field(default_factory=list)

@dataclass
class XlsxPreviewResultado:
    """Resultado da etapa de pré-visualização."""
    matricula: str = ""
    aeronave_id: uuid.UUID | None = None
    total_linhas: int = 0
    pns_encontrados: int = 0
    pns_ignorados: int = 0
    itens: list[XlsxPreviewItem] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

async def obter_previa_xlsx_inventario(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
) -> XlsxPreviewResultado:
    """
    Lê o XLSX e gera uma prévia das alterações sem persistir no banco.
    """
    resultado = XlsxPreviewResultado()

    # 1. Extrair matrícula do nome do arquivo
    nome_base = os.path.splitext(filename)[0].strip()
    resultado.matricula = nome_base

    # 2. Buscar aeronave
    res_acft = await db.execute(
        select(Aeronave).where(Aeronave.matricula == nome_base)
    )
    aeronave = res_acft.scalar_one_or_none()
    if not aeronave:
        resultado.erros.append(
            f"Aeronave com matrícula '{nome_base}' não encontrada no sistema."
        )
        return resultado
    
    resultado.aeronave_id = aeronave.id

    # 3. Carregar slots e PNs
    res_slots = await db.execute(
        select(SlotInventario, ModeloEquipamento)
        .join(ModeloEquipamento, SlotInventario.modelo_id == ModeloEquipamento.id)
    )
    slots_ativos = res_slots.all()

    # 4. Ler o XLSX
    try:
        wb = load_workbook(filename=BytesIO(file_content), data_only=True)
        ws = wb.active

        xlsx_data: dict[tuple[str, str], str] = {} # (PN, POS) -> SN
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) < 6: continue
            pn_xlsx = str(row[1]).strip().upper() if row[1] else None
            pos_xlsx = str(row[4]).strip().upper() if row[4] else ""
            sn_xlsx = str(row[5]).strip() if row[5] else None

            if pn_xlsx:
                xlsx_data[(pn_xlsx, pos_xlsx)] = sn_xlsx
    except Exception as e:
        resultado.erros.append(f"Erro ao ler arquivo XLSX: {str(e)}")
        return resultado

    # 5. Gerar itens de prévia
    for slot, modelo in slots_ativos:
        resultado.total_linhas += 1
        
        pn_sistema = modelo.part_number.upper()
        pos_sistema = slot.posicao_xlsx.upper() if slot.posicao_xlsx else ""
        
        chave = (pn_sistema, pos_sistema)
        
        sn_final = None
        status = "NOT_FOUND"
        status_msg = ""
        
        if chave in xlsx_data:
            sn_xlsx = xlsx_data[chave]
            resultado.pns_encontrados += 1
            
            if not sn_xlsx or sn_xlsx.lower() in ("none", "", "-"):
                sn_final = ""
                status = "REMOVED"
                status_msg = f"∅ Removido (vazio no XLSX)"
            else:
                sn_final = sn_xlsx
                status = "OK"
                status_msg = f"✅ SN: {sn_final}"
        else:
            resultado.pns_ignorados += 1
            sn_final = f"XXXXXXX-{slot.nome_posicao}"
            status = "NOT_FOUND"
            status_msg = f"❓ Não localizado → {sn_final}"

        resultado.itens.append(XlsxPreviewItem(
            slot_id=slot.id,
            nome_posicao=slot.nome_posicao,
            pn=pn_sistema,
            posicao_xlsx=pos_sistema,
            sn_encontrado=sn_final,
            status=status,
            status_msg=status_msg
        ))

    if hasattr(wb, 'close'): wb.close()
    return resultado

async def processar_xlsx_inventario(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    usuario_id: uuid.UUID,
) -> XlsxResultado:
    """
    Processa um arquivo XLSX de inventário e atualiza os seriais da aeronave.
    Mantido para compatibilidade ou se decidirmos processar direto.
    """
    # Podemos reutilizar obter_previa e apenas aplicar
    previa = await obter_previa_xlsx_inventario(db, file_content, filename)
    
    resultado = XlsxResultado(
        matricula=previa.matricula,
        total_linhas=previa.total_linhas,
        pns_encontrados=previa.pns_encontrados,
        pns_ignorados=previa.pns_ignorados,
        erros=previa.erros
    )

    if previa.erros:
        return resultado

    if not previa.aeronave_id:
        resultado.erros.append("ID da aeronave não identificado.")
        return resultado

    # Aplicar cada item
    for item in previa.itens:
        try:
            dados = AjusteInventarioCreate(
                aeronave_id=previa.aeronave_id,
                slot_id=item.slot_id,
                numero_serie_real=item.sn_encontrado,
                forcar_transferencia=False,
                usuario_id=usuario_id,
            )
            resp = await equip_service.ajustar_inventario_item(db, dados)
            if resp.sucesso:
                resultado.itens_atualizados += 1
                resultado.detalhes.append(f"{item.nome_posicao} ({item.pn}): {item.status_msg}")
            else:
                resultado.detalhes.append(
                    f"⚠️ {item.nome_posicao}: {resp.mensagem}"
                )
        except Exception as e:
            resultado.erros.append(
                f"Slot {item.nome_posicao} ({item.pn}): {str(e)}"
            )

    return resultado

async def processar_confirmacao_xlsx(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
    itens: list[schemas.XlsxProcessConfirmItem],
    usuario_id: uuid.UUID,
) -> XlsxResultado:
    """
    Processa a lista de itens confirmados e persiste no banco.
    """
    resultado = XlsxResultado()
    resultado.total_linhas = len(itens)

    for item in itens:
        try:
            dados = AjusteInventarioCreate(
                aeronave_id=aeronave_id,
                slot_id=item.slot_id,
                numero_serie_real=item.sn_final,
                forcar_transferencia=False,
                usuario_id=usuario_id,
            )
            resp = await equip_service.ajustar_inventario_item(db, dados)
            if resp.sucesso:
                resultado.itens_atualizados += 1
                # resultado.detalhes.append(f"Sucesso: {item.slot_id} → {item.sn_final}")
            else:
                resultado.detalhes.append(
                    f"⚠️ Falha no Slot {item.slot_id}: {resp.mensagem}"
                )
        except Exception as e:
            resultado.erros.append(
                f"Erro no Slot {item.slot_id}: {str(e)}"
            )

    return resultado
