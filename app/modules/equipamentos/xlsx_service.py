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

    # 4. Carregar slots para esta aeronave (ou todos e filtramos depois se necessário)
    # Como o objetivo é atualizar os slots do sistema baseado no XLSX:
    res_slots = await db.execute(
        select(SlotInventario, ModeloEquipamento)
        .join(ModeloEquipamento, SlotInventario.modelo_id == ModeloEquipamento.id)
    )
    slots_ativos = res_slots.all()

    # 5. Ler o XLSX e indexar por (PN, POSICAO)
    wb = load_workbook(filename=BytesIO(file_content), data_only=True)
    ws = wb.active

    xlsx_data: dict[tuple[str, str], str] = {} # (PN, POS) -> SN
    for row in ws.iter_rows(min_row=2, values_only=True):
        # Col B (idx 1) = PN, Col E (idx 4) = Posição, Col F (idx 5) = SN Real
        pn_xlsx = str(row[1]).strip().upper() if row[1] else None
        pos_xlsx = str(row[4]).strip().upper() if row[4] else ""
        sn_xlsx = str(row[5]).strip() if row[5] else None

        if pn_xlsx:
            xlsx_data[(pn_xlsx, pos_xlsx)] = sn_xlsx

    # 6. Processar slot por slot do sistema
    for slot, modelo in slots_ativos:
        resultado.total_linhas += 1 # Aqui total_linhas representa slots processados
        
        pn_sistema = modelo.part_number.upper()
        pos_sistema = slot.posicao_xlsx.upper() if slot.posicao_xlsx else ""
        
        # Tenta encontrar no XLSX
        chave = (pn_sistema, pos_sistema)
        
        sn_final = None
        status_msg = ""
        
        if chave in xlsx_data:
            sn_xlsx = xlsx_data[chave]
            resultado.pns_encontrados += 1
            
            if not sn_xlsx or sn_xlsx.lower() in ("none", "", "-"):
                # Caso encontre a equivalencia porem a coluna 6 (sn) esta vazia, considere desinstalado
                sn_final = "" # Indica desinstalação (o service agora trata "" como remoção)
                status_msg = f"∅ {slot.nome_posicao} ({pn_sistema}): Removido (vazio no XLSX)"
            else:
                sn_final = sn_xlsx
                status_msg = f"✅ {slot.nome_posicao} ({pn_sistema}) → SN: {sn_final}"
        else:
            # Caso nao encontre a equivalencia altere o SN para XXXXXXX
            # Usamos um sufixo para evitar conflito de duplicidade no banco (mesmo SN no mesmo modelo em slots diferentes)
            resultado.pns_ignorados += 1
            sn_final = f"XXXXXXX-{slot.nome_posicao}"
            status_msg = f"❓ {slot.nome_posicao} ({pn_sistema}) [{pos_sistema}]: Não localizado no XLSX → {sn_final}"

        # 7. Ajustar inventário no slot identificado
        try:
            dados = AjusteInventarioCreate(
                aeronave_id=aeronave.id,
                slot_id=slot.id,
                numero_serie_real=sn_final,
                forcar_transferencia=False,
                usuario_id=usuario_id,
            )
            resp = await equip_service.ajustar_inventario_item(db, dados)
            if resp.sucesso:
                resultado.itens_atualizados += 1
                resultado.detalhes.append(status_msg)
            else:
                resultado.detalhes.append(
                    f"⚠️ {slot.nome_posicao}: {resp.mensagem}"
                )
        except Exception as e:
            resultado.erros.append(
                f"Slot {slot.nome_posicao} ({pn_sistema}): {str(e)}"
            )

    wb.close()
    return resultado
