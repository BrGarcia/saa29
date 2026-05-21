import uuid
import pytest
from io import BytesIO
from openpyxl import Workbook
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.equipamentos.models import SlotInventario, ModeloEquipamento
from app.modules.aeronaves.models import Aeronave

@pytest.mark.asyncio
async def test_xlsx_preview_and_process_flow(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    headers = usuario_e_token["headers"]
    user = usuario_e_token["usuario"]

    # 1. Setup: Criar Aeronave, Modelo e Slot
    matricula = "5906"
    from datetime import date
    aeronave = Aeronave(
        id=uuid.uuid4(), 
        matricula=matricula, 
        serial_number="SN-5906",
        modelo="A-29",
        status="DISPONIVEL",
        data_inicio_operacao=date.today()
    )
    db.add(aeronave)
    
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number="PN123", nome_generico="Equipamento Teste")
    db.add(modelo)
    
    slot = SlotInventario(
        id=uuid.uuid4(), 
        nome_posicao="POSICAO 1", 
        sistema="SISTEMA", 
        modelo_id=modelo.id,
        posicao_xlsx="COL-E-VAL"
    )
    db.add(slot)
    await db.commit()

    # 2. Criar arquivo XLSX em memória
    wb = Workbook()
    ws = wb.active
    ws.append(["Header", "PN", "Header", "Header", "POSICAO_XLSX", "SN_REAL"])
    ws.append(["Data", "PN123", "Data", "Data", "COL-E-VAL", "SN-NOVO-123"])
    
    stream = BytesIO()
    wb.save(stream)
    xlsx_content = stream.getvalue()

    # 3. Testar Preview
    files = {"file": (f"{matricula}.xlsx", xlsx_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = await client.post("/equipamentos/inventario/upload-xlsx/preview", files=files, headers=headers)
    
    assert response.status_code == 200
    preview = response.json()
    assert preview["matricula"] == matricula
    assert preview["aeronave_id"] == str(aeronave.id)
    assert len(preview["itens"]) == 1
    assert preview["itens"][0]["sn_encontrado"] == "SN-NOVO-123"
    assert preview["itens"][0]["status"] == "OK"

    # 4. Testar Process (Confirmação)
    payload = {
        "aeronave_id": str(aeronave.id),
        "itens": [
            {
                "slot_id": preview["itens"][0]["slot_id"],
                "sn_final": preview["itens"][0]["sn_encontrado"]
            }
        ]
    }
    response = await client.post("/equipamentos/inventario/upload-xlsx/process", json=payload, headers=headers)
    
    assert response.status_code == 200
    result = response.json()
    assert result["sucesso"] is True
    assert result["itens_atualizados"] == 1

    # 5. Verificar se o SN foi realmente atualizado no banco/inventário
    response = await client.get(f"/equipamentos/inventario/{aeronave.id}", headers=headers)
    assert response.status_code == 200
    inventario = response.json()
    item = next((i for i in inventario if i["slot_id"] == str(slot.id)), None)
    assert item is not None
    assert item["numero_serie"] == "SN-NOVO-123"
