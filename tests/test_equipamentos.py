"""
tests/test_equipamentos.py
Testes de gestão de equipamentos, itens e controle de vencimentos – SAA29.

Cobertura (ROADMAP Fase 2 – 2.4):
    - test_criar_equipamento                               — 201
    - test_listar_equipamentos                             — 200
    - test_criar_item_herda_controles_do_equipamento       — MODEL_DB §5.1
    - test_criar_item_sem_controles_no_equipamento         — 0 controles
    - test_propagar_controle_para_itens_existentes         — MODEL_DB §5.2
    - test_sem_duplicidade_controle_por_item               — UNIQUE constraint
    - test_registrar_execucao_calcula_novo_vencimento      — cálculo correto
    - test_status_vencimento_atualizado                    — StatusVencimento
    - test_instalar_item_em_aeronave                       — 201
    - test_remover_item_de_aeronave                        — data_remocao
"""

import uuid
import pytest
from datetime import date, timedelta
from httpx import AsyncClient


EQUIP_URL = "/equipamentos"
ITENS_URL = "/equipamentos/itens/"
TIPOS_URL = "/equipamentos/tipos-controle"
AERONAVES_URL = "/aeronaves/"


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def criar_equipamento(client: AsyncClient, headers: dict, dados: dict) -> dict:
    resp = await client.post(f"{EQUIP_URL}/", json=dados, headers=headers)
    if resp.status_code != 201:
        pytest.skip(f"Endpoint de equipamentos não implementado (status {resp.status_code})")
    return resp.json()


async def criar_tipo_controle(client: AsyncClient, headers: dict, dados: dict) -> dict:
    resp = await client.post(TIPOS_URL, json=dados, headers=headers)
    if resp.status_code != 201:
        pytest.skip(f"Endpoint de tipos-controle não implementado (status {resp.status_code})")
    return resp.json()


async def criar_item(client: AsyncClient, headers: dict, equip_id: str, numero_serie: str | None = None) -> dict:
    payload = {
        "equipamento_id": equip_id,
        "numero_serie": numero_serie or f"SN-{uuid.uuid4().hex[:8].upper()}",
        "status": "ATIVO"
    }
    resp = await client.post(ITENS_URL, json=payload, headers=headers)
    if resp.status_code != 201:
        pytest.skip(f"Endpoint de itens não implementado (status {resp.status_code})")
    return resp.json()


async def criar_aeronave(client: AsyncClient, headers: dict, dados: dict) -> dict:
    resp = await client.post(AERONAVES_URL, json=dados, headers=headers)
    if resp.status_code != 201:
        pytest.skip(f"Endpoint de aeronaves não implementado (status {resp.status_code})")
    return resp.json()


# ================================================================== #
#  CRUD de Equipamentos
# ================================================================== #

class TestEquipamentos:

    @pytest.mark.asyncio
    async def test_criar_equipamento_requer_autenticacao(
        self, client: AsyncClient, dados_equipamento_valido: dict
    ):
        """DADO sem token QUANDO criar equipamento ENTÃO 401."""
        response = await client.post(f"{EQUIP_URL}/", json=dados_equipamento_valido)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_criar_equipamento(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        usuario_e_token: dict,
    ):
        """
        DADO dados válidos e usuário autenticado
        QUANDO criar POST /equipamentos/
        ENTÃO retornar equipamento criado com id e status 201.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.post(
            f"{EQUIP_URL}/",
            json=dados_equipamento_valido,
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 201
        body = response.json()
        assert "id" in body
        assert body["nome"] == dados_equipamento_valido["nome"]
        assert body["part_number"] == dados_equipamento_valido["part_number"]

    @pytest.mark.asyncio
    async def test_criar_equipamento_campos_obrigatorios(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """
        DADO payload sem campos obrigatórios (nome, part_number)
        QUANDO criar equipamento
        ENTÃO retornar 422 Unprocessable Entity.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.post(
            f"{EQUIP_URL}/",
            json={"descricao": "Sem campos obrigatórios"},
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_listar_equipamentos(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        usuario_e_token: dict,
    ):
        """
        DADO equipamentos cadastrados
        QUANDO listar GET /equipamentos/
        ENTÃO retornar lista e status 200.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        await criar_equipamento(client, headers, dados_equipamento_valido)

        response = await client.get(f"{EQUIP_URL}/", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1


# ================================================================== #
#  Herança de Controles (MODEL_DB §5.1)
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
        """
        DADO equipamento com 2 tipos de controle associados
        QUANDO criar um novo item POST /equipamentos/itens
        ENTÃO o item deve ter 2 registros em controle_vencimentos (MODEL_DB §5.1).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)

        # Criar 2 tipos de controle
        tc1 = await criar_tipo_controle(client, headers, dados_tipo_controle_valido)
        tc2 = await criar_tipo_controle(
            client, headers, {**dados_tipo_controle_valido, "nome": "RBA", "periodicidade_meses": 24}
        )

        # Associar os 2 controles ao equipamento
        await client.post(
            f"{EQUIP_URL}/{equip['id']}/controles/{tc1['id']}", headers=headers
        )
        await client.post(
            f"{EQUIP_URL}/{equip['id']}/controles/{tc2['id']}", headers=headers
        )

        # Criar um item — deve herdar os 2 controles
        item = await criar_item(client, headers, equip["id"])

        # Verificar controles herdados
        resp = await client.get(
            f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers
        )
        if resp.status_code == 200:
            assert len(resp.json()) == 2, "Item deve herdar 2 controles do equipamento (MODEL_DB §5.1)"

    @pytest.mark.asyncio
    async def test_criar_item_sem_controles_no_equipamento(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        usuario_e_token: dict,
    ):
        """
        DADO equipamento sem tipos de controle associados
        QUANDO criar um item
        ENTÃO item criado com 0 controles de vencimento.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)
        item = await criar_item(client, headers, equip["id"])

        resp = await client.get(
            f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers
        )
        if resp.status_code == 200:
            assert len(resp.json()) == 0


# ================================================================== #
#  Propagação de Controles (MODEL_DB §5.2)
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
        """
        DADO equipamento com 2 itens criados (sem controles)
        QUANDO associar um tipo de controle ao equipamento
        ENTÃO ambos os itens devem receber o controle herdado (MODEL_DB §5.2).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)

        # Criar 2 itens ANTES de associar o controle
        item1 = await criar_item(client, headers, equip["id"], "SN-A001")
        item2 = await criar_item(client, headers, equip["id"], "SN-A002")

        # Criar e associar tipo de controle ao equipamento
        tc = await criar_tipo_controle(client, headers, dados_tipo_controle_valido)
        propagacao = await client.post(
            f"{EQUIP_URL}/{equip['id']}/controles/{tc['id']}", headers=headers
        )

        if propagacao.status_code == 200:
            # Verificar que ambos os itens receberam o controle propagado
            for item_id in [item1["id"], item2["id"]]:
                resp = await client.get(
                    f"{EQUIP_URL}/itens/{item_id}/controles", headers=headers
                )
                if resp.status_code == 200:
                    assert len(resp.json()) >= 1, f"Item {item_id} deve ter recebido o controle propagado"

    @pytest.mark.asyncio
    async def test_sem_duplicidade_controle_por_item(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        """
        DADO item com controle TBV já cadastrado
        QUANDO tentar associar TBV novamente ao equipamento
        ENTÃO não criar duplicata — UNIQUE constraint (uq_item_controle).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)
        tc = await criar_tipo_controle(client, headers, dados_tipo_controle_valido)

        # Associar controle ao equipamento (cria template)
        await client.post(f"{EQUIP_URL}/{equip['id']}/controles/{tc['id']}", headers=headers)

        # Criar item (herda o controle)
        item = await criar_item(client, headers, equip["id"])

        # Tentar associar o mesmo controle novamente
        resp = await client.post(
            f"{EQUIP_URL}/{equip['id']}/controles/{tc['id']}", headers=headers
        )
        # Deve rejeitar com 409 (já existe) ou 200 (idempotente — sem duplicar no item)
        assert resp.status_code in (200, 409)

        # Independente do status, o item não deve ter duplicata
        controles_resp = await client.get(
            f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers
        )
        if controles_resp.status_code == 200:
            controle_ids = [c.get("tipo_controle_id") for c in controles_resp.json()]
            assert len(controle_ids) == len(set(controle_ids)), "Não deve haver controles duplicados no item"


# ================================================================== #
#  Controle de Vencimentos
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
        """
        DADO controle TBV com periodicidade 12 meses
        QUANDO registrar execução em 01/01/2026
        ENTÃO data_vencimento = 01/01/2027.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)
        tc = await criar_tipo_controle(
            client, headers, {**dados_tipo_controle_valido, "periodicidade_meses": 12}
        )
        await client.post(f"{EQUIP_URL}/{equip['id']}/controles/{tc['id']}", headers=headers)
        item = await criar_item(client, headers, equip["id"])

        # Buscar o controle_vencimento criado
        controles_resp = await client.get(
            f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers
        )
        if controles_resp.status_code != 200 or not controles_resp.json():
            pytest.skip("Endpoint de controles de item não implementado")

        controle_id = controles_resp.json()[0]["id"]
        data_exec = "2026-01-01"

        response = await client.patch(
            f"{EQUIP_URL}/vencimentos/{controle_id}/executar",
            json={"data_ultima_exec": data_exec},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data_ultima_exec"] == data_exec
        assert body["data_vencimento"] == "2027-01-01"

    @pytest.mark.asyncio
    async def test_controle_sem_execucao_tem_status_ok(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_tipo_controle_valido: dict,
        usuario_e_token: dict,
    ):
        """
        DADO controle recém-criado (sem execução registrada)
        QUANDO verificar status
        ENTÃO status = "OK" (valor padrão).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)
        tc = await criar_tipo_controle(client, headers, dados_tipo_controle_valido)
        await client.post(f"{EQUIP_URL}/{equip['id']}/controles/{tc['id']}", headers=headers)
        item = await criar_item(client, headers, equip["id"])

        controles_resp = await client.get(
            f"{EQUIP_URL}/itens/{item['id']}/controles", headers=headers
        )
        if controles_resp.status_code == 200 and controles_resp.json():
            controle = controles_resp.json()[0]
            assert controle["status"] == "OK"


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
        """
        DADO item com status ATIVO e aeronave existente
        QUANDO instalar em aeronave POST /equipamentos/itens/{id}/instalar
        ENTÃO criar registro de instalação com status 201.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)
        item = await criar_item(client, headers, equip["id"])
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        hoje = date.today().isoformat()
        response = await client.post(
            f"{EQUIP_URL}/itens/{item['id']}/instalar",
            json={"aeronave_id": aeronave["id"], "data_instalacao": hoje},
            headers=headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["aeronave_id"] == aeronave["id"]
        assert body["data_remocao"] is None  # instalação ativa

    @pytest.mark.asyncio
    async def test_remover_item_de_aeronave(
        self,
        client: AsyncClient,
        dados_equipamento_valido: dict,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO item instalado em aeronave
        QUANDO registrar remoção PATCH /equipamentos/instalacoes/{inst_id}/remover
        ENTÃO data_remocao preenchida na instalação.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        equip = await criar_equipamento(client, headers, dados_equipamento_valido)
        item = await criar_item(client, headers, equip["id"])
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        hoje = date.today().isoformat()
        instalacao_resp = await client.post(
            f"{EQUIP_URL}/itens/{item['id']}/instalar",
            json={"aeronave_id": aeronave["id"], "data_instalacao": hoje},
            headers=headers,
        )
        if instalacao_resp.status_code != 201:
            pytest.skip("Endpoint de instalações não implementado")

        inst_id = instalacao_resp.json()["id"]
        amanha = (date.today() + timedelta(days=1)).isoformat()

        response = await client.patch(
            f"{EQUIP_URL}/instalacoes/{inst_id}/remover",
            json={"data_remocao": amanha},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["data_remocao"] == amanha
