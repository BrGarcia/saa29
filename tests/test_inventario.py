"""
tests/test_inventario.py
Testes do módulo de Inventário de Equipamentos por Aeronave – SAA29.
Alinhado com a arquitetura PN vs Slot e novas siglas (CEI, CES, 1P, 2P).
"""

import uuid
import pytest
import asyncio
from datetime import date, timedelta, datetime
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.equipamentos.models import SlotInventario, Instalacao


EQUIP_URL = "/equipamentos"
AERONAVES_URL = "/aeronaves/"
INVENTARIO_URL = "/equipamentos/inventario"


# ------------------------------------------------------------------ #
#  Helpers (Arquitetura PN vs Slot via API + DB Injetado)
# ------------------------------------------------------------------ #

async def _criar_modelo(client: AsyncClient, headers: dict, pn: str, nome: str) -> dict:
    """Helper: cria um Modelo de Equipamento (PN)."""
    payload = {"part_number": pn, "nome_generico": nome, "descricao": f"Modelo {nome}"}
    resp = await client.post(f"{EQUIP_URL}/", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _criar_slot(db: AsyncSession, nome: str, sistema: str, modelo_id: str) -> dict:
    """Helper: cria um Slot de Inventário via DB."""
    slot = SlotInventario(
        id=uuid.uuid4(),
        nome_posicao=nome,
        sistema=sistema,
        modelo_id=uuid.UUID(modelo_id)
    )
    db.add(slot)
    await db.commit()
    return {"id": str(slot.id), "nome_posicao": slot.nome_posicao}


async def _ajustar_inventario(client: AsyncClient, headers: dict, aeronave_id: str, slot_id: str, sn: str) -> dict:
    """Helper: sincroniza um S/N real em um slot."""
    payload = {
        "aeronave_id": aeronave_id,
        "slot_id": slot_id,
        "numero_serie_real": sn,
        "forcar_transferencia": True
    }
    resp = await client.post(f"{INVENTARIO_URL}/ajuste", json=payload, headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def _criar_aeronave(client: AsyncClient, headers: dict, matricula: str, serial: str) -> dict:
    """Helper: cria uma aeronave."""
    payload = {"serial_number": serial, "matricula": matricula, "modelo": "A-29", "status": "OPERACIONAL"}
    resp = await client.post(AERONAVES_URL, json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _montar_inventario_completo(client: AsyncClient, db: AsyncSession, headers: dict) -> dict:
    """Helper composto: cria aeronave de teste com 3 slots."""
    prefix = uuid.uuid4().hex[:4]
    aeronave = await _criar_aeronave(client, headers, f"T-{prefix}", f"SN-{prefix}")
    mod_adf = await _criar_modelo(client, headers, f"PN-ADF-{prefix}", "ADF RECEIVER")
    mod_pdu = await _criar_modelo(client, headers, f"PN-PDU-{prefix}", "PDU")
    slot_adf = await _criar_slot(db, "ADF", "CEI", mod_adf["id"])
    slot_vuhf = await _criar_slot(db, "VUHF1", "CEI", mod_adf["id"]) 
    slot_pdu = await _criar_slot(db, "PDU", "1P", mod_pdu["id"])
    await _ajustar_inventario(client, headers, aeronave["id"], slot_adf["id"], f"SN-ADF-{prefix}")
    await _ajustar_inventario(client, headers, aeronave["id"], slot_vuhf["id"], f"SN-VUHF-{prefix}")
    await _ajustar_inventario(client, headers, aeronave["id"], slot_pdu["id"], f"SN-PDU-{prefix}")
    return {"aeronave": aeronave, "prefix": prefix}


# ================================================================== #
#  Testes
# ================================================================== #

class TestInventarioFull:
    @pytest.mark.asyncio
    async def test_t01_fluxo_completo_inventario(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        dados = await _montar_inventario_completo(client, db, headers)
        response = await client.get(f"{INVENTARIO_URL}/{dados['aeronave']['id']}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        nomes_retornados = [i["nome_posicao"] for i in body]
        assert "ADF" in nomes_retornados

    @pytest.mark.asyncio
    async def test_t02_rastreabilidade_e_timestamp(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        prefix = uuid.uuid4().hex[:4]
        anv1 = await _criar_aeronave(client, headers, f"A-{prefix}", f"SN1-{prefix}")
        anv2 = await _criar_aeronave(client, headers, f"B-{prefix}", f"SN2-{prefix}")
        anv3 = await _criar_aeronave(client, headers, f"C-{prefix}", f"SN3-{prefix}")
        mod = await _criar_modelo(client, headers, f"PN-TR-{prefix}", "RADIO")
        slot = await _criar_slot(db, f"RAD-{prefix}", "CEI", mod["id"])
        sn = f"SN-TR-{prefix}"

        # Sequência: Instalar na A e depois na B
        await _ajustar_inventario(client, headers, anv1["id"], slot["id"], sn)
        await _ajustar_inventario(client, headers, anv2["id"], slot["id"], sn)
        
        # Garantir IDs como UUID e created_at como datetime
        anv1_id = uuid.UUID(anv1["id"])
        data_passada = datetime.now() - timedelta(days=1)

        # HACK: Atrasar instalação da ANV1
        await db.execute(
            update(Instalacao)
            .where(Instalacao.aeronave_id == anv1_id)
            .values(created_at=data_passada)
        )
        await db.commit()

        # Instalar na C
        await _ajustar_inventario(client, headers, anv3["id"], slot["id"], sn)

        response = await client.get(f"{INVENTARIO_URL}/{anv3['id']}", headers=headers)
        body = response.json()
        item = next((i for i in body if i["slot_id"] == slot["id"]), None)
        
        assert item is not None
        assert item["aeronave_anterior"] == f"B-{prefix}"

    @pytest.mark.asyncio
    async def test_t03_agrupamento_frontend(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        prefix = uuid.uuid4().hex[:4]
        anv = await _criar_aeronave(client, headers, f"F-{prefix}", f"SNF-{prefix}")
        mod = await _criar_modelo(client, headers, f"PN-F-{prefix}", "F")
        await _criar_slot(db, f"S1-{prefix}", "CEI", mod["id"])
        await _criar_slot(db, f"S2-{prefix}", "1P", mod["id"])
        response = await client.get(f"{INVENTARIO_URL}/{anv['id']}", headers=headers)
        body = response.json()
        sistemas = {i["sistema"] for i in body if prefix in i["nome_posicao"]}
        assert "CEI" in sistemas
        assert "1P" in sistemas

    @pytest.mark.asyncio
    async def test_t04_historico_alteracoes_com_trigrama(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict,
    ):
        """T04: Valida se o histórico registra o trigrama do usuário corretamente."""
        headers = usuario_e_token["headers"]
        user = usuario_e_token["usuario"]
        
        # 1. Setup (Atualizar usuário com trigrama para o teste)
        from sqlalchemy import update
        from app.auth.models import Usuario
        await db.execute(update(Usuario).where(Usuario.id == user.id).values(trigrama="ABC"))
        await db.commit()

        prefix = uuid.uuid4().hex[:4]
        anv = await _criar_aeronave(client, headers, f"H-{prefix}", f"SNH-{prefix}")
        mod = await _criar_modelo(client, headers, f"PN-H-{prefix}", "RADIO H")
        slot = await _criar_slot(db, f"RAD-H-{prefix}", "CEI", mod["id"])

        # 2. Realizar ajuste (Passando o usuario_id)
        sn = f"SN-H-{prefix}"
        payload = {
            "aeronave_id": anv["id"],
            "slot_id": slot["id"],
            "numero_serie_real": sn,
            "usuario_id": str(user.id)
        }
        await client.post(f"{INVENTARIO_URL}/ajuste", json=payload, headers=headers)

        # 3. Consultar histórico
        response = await client.get(f"{INVENTARIO_URL}/historico", headers=headers)
        assert response.status_code == 200
        logs = response.json()

        # Buscar o log específico deste teste na lista (pode haver sujeira de outros testes)
        nosso_log = next((l for l in logs if l["item_sn"] == sn.upper()), None)
        
        assert nosso_log is not None, f"Log para o item {sn} não encontrado no histórico"
        assert nosso_log["usuario_trigrama"] == "ABC"
        assert nosso_log["aeronave_matricula"] == f"H-{prefix}"
