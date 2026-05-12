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
from app.modules.equipamentos.schemas import AjusteInventarioCreate
from app.modules.equipamentos import service as equip_service


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


async def processar_xlsx_inventario(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    usuario_id: uuid.UUID,
) -> XlsxResultado:
    """
    Processa um arquivo XLSX de inventário e atualiza os seriais da aeronave.
    
    Parâmetros:
        db: Sessão assíncrona do banco de dados
        file_content: Conteúdo binário do arquivo XLSX
        filename: Nome do arquivo (ex: "5906.xlsx")
        usuario_id: ID do usuário que está realizando a operação
    """
    resultado = XlsxResultado()

    # 1. Extrair matrícula do nome do arquivo
    nome_base = os.path.splitext(filename)[0].strip()
    resultado.matricula = nome_base

    # 2. Buscar aeronave pelo campo matrícula
    res_acft = await db.execute(
        select(Aeronave).where(Aeronave.matricula == nome_base)
    )
    aeronave = res_acft.scalar_one_or_none()
    if not aeronave:
        resultado.erros.append(
            f"Aeronave com matrícula '{nome_base}' não encontrada no sistema."
        )
        return resultado

    # 3. Carregar catálogo de PNs do banco (mapa PN → modelo)
    res_modelos = await db.execute(select(ModeloEquipamento))
    modelos_map: dict[str, ModeloEquipamento] = {
        m.part_number.upper(): m for m in res_modelos.scalars().all()
    }

    # 4. Carregar slots e indexar por modelo_id E por posicao_xlsx
    res_slots = await db.execute(select(SlotInventario))
    slots_por_modelo: dict[uuid.UUID, list[SlotInventario]] = {}
    slots_por_posicao: dict[str, SlotInventario] = {}  # posicao_xlsx → slot
    for slot in res_slots.scalars().all():
        slots_por_modelo.setdefault(slot.modelo_id, []).append(slot)
        if slot.posicao_xlsx:
            slots_por_posicao[slot.posicao_xlsx.upper()] = slot

    # 5. Ler o XLSX
    wb = load_workbook(filename=BytesIO(file_content), read_only=True, data_only=True)
    ws = wb.active  # Usa a primeira aba

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        resultado.total_linhas += 1

        # Col B (idx 1) = PN, Col E (idx 4) = Posição, Col F (idx 5) = SN Real
        pn_raw = str(row[1]).strip().upper() if row[1] else None
        pos_raw = str(row[4]).strip().upper() if row[4] else None
        sn_raw = str(row[5]).strip() if row[5] else None

        if not pn_raw or not sn_raw or sn_raw.lower() in ("none", "", "-"):
            continue

        # 6. Buscar modelo pelo PN
        modelo = modelos_map.get(pn_raw)
        if not modelo:
            resultado.pns_ignorados += 1
            continue

        resultado.pns_encontrados += 1

        # 7. Desambiguar slot usando posicao_xlsx (coluna E)
        slot_alvo = None
        if pos_raw and pos_raw in slots_por_posicao:
            # Match direto pela posição da planilha
            slot_alvo = slots_por_posicao[pos_raw]
        else:
            # Fallback: se o PN tem um único slot, usar direto
            slots_do_pn = slots_por_modelo.get(modelo.id, [])
            if len(slots_do_pn) == 1:
                slot_alvo = slots_do_pn[0]
            elif len(slots_do_pn) == 0:
                resultado.erros.append(
                    f"Linha {row_idx}: PN '{pn_raw}' sem slot configurado."
                )
                continue
            else:
                resultado.erros.append(
                    f"Linha {row_idx}: PN '{pn_raw}' possui {len(slots_do_pn)} slots, "
                    f"mas posição '{pos_raw}' não tem correspondência em posicao_xlsx."
                )
                continue

        # 8. Ajustar inventário no slot identificado
        try:
            dados = AjusteInventarioCreate(
                aeronave_id=aeronave.id,
                slot_id=slot_alvo.id,
                numero_serie_real=sn_raw,
                forcar_transferencia=False,
                usuario_id=usuario_id,
            )
            resp = await equip_service.ajustar_inventario_item(db, dados)
            if resp.sucesso:
                resultado.itens_atualizados += 1
                resultado.detalhes.append(
                    f"✅ {slot_alvo.nome_posicao} ({pn_raw}) → SN: {sn_raw}"
                )
            else:
                resultado.detalhes.append(
                    f"⚠️ {slot_alvo.nome_posicao}: {resp.mensagem}"
                )
        except Exception as e:
            resultado.erros.append(
                f"Linha {row_idx}, Slot {slot_alvo.nome_posicao}: {str(e)}"
            )

    wb.close()
    return resultado
