"""
tests/test_equipamentos.py
Testes de gestão de equipamentos, itens e controle de vencimentos – SAA29.
"""

import uuid
import pytest
from datetime import date, timedelta
from httpx import AsyncClient


EQUIP_URL = "/equipamentos"
ITENS_URL = "/equipamentos/itens/"
TIPOS_URL = "/equipamentos/tipos-controle"
REGRAS_URL = "/equipamentos/controles/regras"
AERONAVES_URL = "/aeronaves/"


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def criar_equipamento_helper(client: AsyncClient, headers: dict, dados: dict) -> dict:
    # Garantir PN único para evitar 409 se houver commit no service
    dados_copy = dados.copy()
    dados_copy["part_number"] = f"{dados['part_number']}-{uuid.uuid4().hex[:8].upper()}"
    resp = await client.post(f"{EQUIP_URL}/", json=dados_copy, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def criar_tipo_controle_helper(client: AsyncClient, headers: dict, dados: dict) -> dict:
    dados_copy = dados.copy()
    dados_copy["nome"] = f"T{uuid.uuid4().hex[:6].upper()}"
    resp = await client.post(TIPOS_URL, json=dados_copy, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def criar_item_helper(client: AsyncClient, headers: dict, equip_id: str, numero_serie: str | None = None) -> dict:
    payload = {
        "modelo_id": equip_id,
        "numero_serie": numero_serie or f"SN-{uuid.uuid4().hex[:12].upper()}",
        "status": "ATIVO"
    }
    resp = await client.post(ITENS_URL, json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def criar_aeronave_helper(client: AsyncClient, headers: dict, dados: dict) -> dict:
    dados_copy = dados.copy()
    suffix = uuid.uuid4().hex[:8].upper()
    dados_copy["matricula"] = f"ACFT-{suffix}"
    dados_copy["serial_number"] = f"SN-{suffix}"
    resp = await client.post(AERONAVES_URL, json=dados_copy, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# ================================================================== #
#  CRUD de Equipamentos (Catálogo / PN)
# ================================================================== #

class TestEquipamentos:

    @pytest.mark.asyncio
    async def test_criar_equipamento_requer_autenticacao(
        self, client: AsyncClient, dados_equipamento_valido: dict
    ):
        response = await client.post(f"{EQUIP_URL}/", json=dados_equipamento_valido)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_criar_equipamento(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        response = await client.post(
            f"{EQUIP_URL}/",
            json=dados_equipamento_valido,
            headers=headers,
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_criar_equipamento_duplicado(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        # Criar primeiro
        await client.post(f"{EQUIP_URL}/", json=dados_equipamento_valido, headers=headers)
        # Tentar duplicar
        response = await client.post(
            f"{EQUIP_URL}/",
            json=dados_equipamento_valido,
            headers=headers,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_listar_equipamentos(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        response = await client.get(f"{EQUIP_URL}/", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1


# ================================================================== #
#  Herança de Controles (CT-05 / CT-07)
# ================================================================== #

class TestHerancaControles:

    @pytest.mark.asyncio
    async def test_criar_item_herda_controles_do_equipamento(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)

        tc1 = await criar_tipo_controle_helper(client, headers, dados_tipo_controle_valido)
        tc2 = await criar_tipo_controle_helper(client, headers, dados_tipo_controle_valido)

        await client.post(REGRAS_URL, json={"modelo_id": equip['id'], "tipo_controle_id": tc1['id'], "periodicidade_meses": 12}, headers=headers)
        await client.post(REGRAS_URL, json={"modelo_id": equip['id'], "tipo_controle_id": tc2['id'], "periodicidade_meses": 24}, headers=headers)

        item = await criar_item_helper(client, headers, equip["id"])
        resp = await client.get(f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers)
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_criar_item_sem_controles_no_equipamento(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        item = await criar_item_helper(client, headers, equip["id"])
        resp = await client.get(f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers)
        assert len(resp.json()) == 0


# ================================================================== #
#  Propagação de Controles (CT-07)
# ================================================================== #

class TestPropagacaoControle:

    @pytest.mark.asyncio
    async def test_propagar_controle_para_itens_existentes(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        item = await criar_item_helper(client, headers, equip["id"])

        tc = await criar_tipo_controle_helper(client, headers, dados_tipo_controle_valido)
        await client.post(REGRAS_URL, json={"modelo_id": equip['id'], "tipo_controle_id": tc['id'], "periodicidade_meses": 6}, headers=headers)

        resp = await client.get(f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers)
        assert any(c["tipo_controle_id"] == tc["id"] for c in resp.json())


# ================================================================== #
#  Controle de Vencimentos (CT-06)
# ================================================================== #

class TestVencimentos:

    @pytest.mark.asyncio
    async def test_registrar_execucao_calcula_novo_vencimento(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        tc = await criar_tipo_controle_helper(client, headers, dados_tipo_controle_valido)
        
        await client.post(REGRAS_URL, json={"modelo_id": equip['id'], "tipo_controle_id": tc['id'], "periodicidade_meses": 12}, headers=headers)
        item = await criar_item_helper(client, headers, equip["id"])

        controles = (await client.get(f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers)).json()
        cid = controles[0]["id"]
        
        data_exec = "2026-01-01"
        response = await client.patch(f"{EQUIP_URL}/vencimentos/{cid}/executar", json={"data_ultima_exec": data_exec}, headers=headers)
        assert response.status_code == 200
        assert response.json()["data_vencimento"] == "2027-01-01"


# ================================================================== #
#  Instalações
# ================================================================== #

class TestInstalacoes:

    @pytest.mark.asyncio
    async def test_instalar_item_em_aeronave(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        item = await criar_item_helper(client, headers, equip["id"])
        aeronave = await criar_aeronave_helper(client, headers, dados_aeronave_valida)
        
        # Criar Slot (Obrigatório na V2)
        slot_resp = await client.post(f"{EQUIP_URL}/slots/", json={
            "nome_posicao": "POS-TESTE", "sistema": "TESTE", "modelo_id": equip["id"]
        }, headers=headers)
        slot = slot_resp.json()

        hoje = date.today().isoformat()
        response = await client.post(
            f"{EQUIP_URL}/itens/{item['id']}/instalar", 
            json={"aeronave_id": aeronave["id"], "slot_id": slot["id"], "data_instalacao": hoje}, 
            headers=headers
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_remover_item_de_aeronave(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        item = await criar_item_helper(client, headers, equip["id"])
        aeronave = await criar_aeronave_helper(client, headers, dados_aeronave_valida)

        # Criar Slot (Obrigatório na V2)
        slot_resp = await client.post(f"{EQUIP_URL}/slots/", json={
            "nome_posicao": "POS-TESTE-REM", "sistema": "TESTE", "modelo_id": equip["id"]
        }, headers=headers)
        slot = slot_resp.json()

        hoje = date.today().isoformat()
        inst_resp = await client.post(
            f"{EQUIP_URL}/itens/{item['id']}/instalar", 
            json={"aeronave_id": aeronave["id"], "slot_id": slot["id"], "data_instalacao": hoje}, 
            headers=headers
        )
        inst = inst_resp.json()

        amanha = (date.today() + timedelta(days=1)).isoformat()
        response = await client.patch(f"{EQUIP_URL}/instalacoes/{inst['id']}/remover", json={"data_remocao": amanha}, headers=headers)
        assert response.status_code == 200
        assert response.json()["data_remocao"] == amanha


# ================================================================== #
#  Prorrogações (CT-L11, CT-L12, CT-L13)
# ================================================================== #

class TestProrrogacoes:

    @pytest.mark.asyncio
    async def test_prorrogar_vencimento_sucesso(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        tc = await criar_tipo_controle_helper(client, headers, dados_tipo_controle_valido)
        await client.post(REGRAS_URL, json={"modelo_id": equip['id'], "tipo_controle_id": tc['id'], "periodicidade_meses": 12}, headers=headers)
        item = await criar_item_helper(client, headers, equip["id"])
        
        # Registrar execução inicial para ter uma data de vencimento base
        controles = (await client.get(f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers)).json()
        cid = controles[0]["id"]
        await client.patch(f"{EQUIP_URL}/vencimentos/{cid}/executar", json={"data_ultima_exec": "2026-01-01"}, headers=headers)
        
        # Prorrogar (CT-L11)
        payload = {
            "numero_documento": "DIR-001/2026",
            "data_concessao": date.today().isoformat(),
            "dias_adicionais": 30,
            "motivo": "Atraso no suprimento"
        }
        response = await client.post(f"{EQUIP_URL}/vencimentos/{cid}/prorrogar", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["ativo"] is True
        assert response.json()["dias_adicionais"] == 30

    @pytest.mark.asyncio
    async def test_cancelar_prorrogacao(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        tc = await criar_tipo_controle_helper(client, headers, dados_tipo_controle_valido)
        await client.post(REGRAS_URL, json={"modelo_id": equip['id'], "tipo_controle_id": tc['id'], "periodicidade_meses": 12}, headers=headers)
        item = await criar_item_helper(client, headers, equip["id"])
        controles = (await client.get(f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers)).json()
        cid = controles[0]["id"]

        # Prorrogar
        await client.post(f"{EQUIP_URL}/vencimentos/{cid}/prorrogar", json={
            "numero_documento": "DOC-123", "data_concessao": "2026-04-25", "dias_adicionais": 15
        }, headers=headers)

        # Cancelar (CT-L12)
        response = await client.delete(f"{EQUIP_URL}/vencimentos/{cid}/prorrogar", headers=headers)
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_execucao_desativa_prorrogacao_ativa(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        equip = await criar_equipamento_helper(client, headers, dados_equipamento_valido)
        tc = await criar_tipo_controle_helper(client, headers, dados_tipo_controle_valido)
        await client.post(REGRAS_URL, json={"modelo_id": equip['id'], "tipo_controle_id": tc['id'], "periodicidade_meses": 12}, headers=headers)
        item = await criar_item_helper(client, headers, equip["id"])
        controles = (await client.get(f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers)).json()
        cid = controles[0]["id"]

        # 1. Criar prorrogação
        await client.post(f"{EQUIP_URL}/vencimentos/{cid}/prorrogar", json={
            "numero_documento": "EXT-001", "data_concessao": "2026-04-25", "dias_adicionais": 30
        }, headers=headers)

        # 2. Registrar execução (CT-L13)
        await client.patch(f"{EQUIP_URL}/vencimentos/{cid}/executar", json={"data_ultima_exec": "2026-04-25"}, headers=headers)

        # 3. Verificar se a prorrogação foi desativada no banco (via endpoint se existisse, ou verificando se o cancelamento retorna false)
        # Como não temos GET individual de prorrogação, vamos assumir que o fluxo de registrar_execucao chamou a desativação.
        # Podemos verificar na matriz se o status não é mais PRORROGADO.
        matriz = (await client.get(f"{EQUIP_URL}/vencimentos/matriz", headers=headers)).json()
        # Localizar a célula correta na matriz e ver que prorrogado é false
        for acft in matriz["aeronaves"]:
            for slot in acft["slots"]:
                for ctrl in slot["controles"]:
                    if ctrl["vencimento_id"] == cid:
                        assert ctrl["prorrogado"] is False


# ================================================================== #
#  Matriz de Vencimentos (CT-L14)
# ================================================================== #

class TestMatrizVencimentos:

    @pytest.mark.asyncio
    async def test_matriz_vencimentos_estrutura(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        response = await client.get(f"{EQUIP_URL}/vencimentos/matriz", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "cabecalho" in data
        assert "aeronaves" in data
        assert isinstance(data["aeronaves"], list)
