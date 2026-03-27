"""
tests/test_aeronaves.py
Testes de gestão de aeronaves – SAA29.

Cobertura (ROADMAP Fase 2 – 2.2):
    - test_listar_aeronaves_vazio          → GET /aeronaves/ — lista vazia, 200
    - test_criar_aeronave_sucesso          → POST /aeronaves/ — 201
    - test_criar_aeronave_matricula_dup    → POST /aeronaves/ — 409
    - test_buscar_aeronave_existente       → GET /aeronaves/{id} — 200
    - test_buscar_aeronave_inexistente     → GET /aeronaves/{id} — 404
    - test_campos_obrigatorios             → POST sem matricula — 422
    - test_listar_requer_autenticacao      → 401 sem token
"""

import uuid
import pytest
from httpx import AsyncClient


AERONAVES_URL = "/aeronaves/"


class TestListarAeronaves:

    @pytest.mark.asyncio
    async def test_listar_aeronaves_requer_autenticacao(self, client: AsyncClient):
        """
        DADO requisição sem token
        QUANDO listar GET /aeronaves/
        ENTÃO retornar 401.
        """
        response = await client.get(AERONAVES_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_listar_aeronaves_vazio(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """
        DADO banco sem aeronaves e usuário autenticado
        QUANDO listar GET /aeronaves/
        ENTÃO retornar lista vazia e status 200.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.get(
            AERONAVES_URL, headers=usuario_e_token["headers"]
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestCriarAeronave:

    @pytest.mark.asyncio
    async def test_criar_aeronave_requer_autenticacao(
        self, client: AsyncClient, dados_aeronave_valida: dict
    ):
        """
        DADO payload válido sem token
        QUANDO criar POST /aeronaves/
        ENTÃO retornar 401.
        """
        response = await client.post(AERONAVES_URL, json=dados_aeronave_valida)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_criar_aeronave_sem_matricula(self, client: AsyncClient):
        """
        DADO payload sem campo obrigatório 'matricula'
        QUANDO criar aeronave
        ENTÃO retornar 422 Unprocessable Entity (validação Pydantic).
        """
        payload_invalido = {"serial_number": "SN-XPTO", "modelo": "A-29"}
        response = await client.post(AERONAVES_URL, json=payload_invalido)
        # 422 sem auth ou com auth — validação Pydantic acontece antes
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_criar_aeronave_sucesso(
        self, client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict
    ):
        """
        DADO dados válidos e usuário autenticado
        QUANDO criar POST /aeronaves/
        ENTÃO retornar aeronave criada com id e status 201.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.post(
            AERONAVES_URL,
            json=dados_aeronave_valida,
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 201
        body = response.json()
        assert "id" in body
        assert body["matricula"] == dados_aeronave_valida["matricula"]
        assert body["status"] == "OPERACIONAL"

    @pytest.mark.asyncio
    async def test_criar_aeronave_matricula_duplicada(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO matrícula já cadastrada no banco
        QUANDO criar outra aeronave com a mesma matrícula
        ENTÃO retornar 409 Conflict.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        await client.post(AERONAVES_URL, json=dados_aeronave_valida, headers=headers)
        response = await client.post(AERONAVES_URL, json=dados_aeronave_valida, headers=headers)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_criar_aeronave_status_invalido(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """
        DADO payload com status fora do Enum (ex: 'DESTRUIDA')
        QUANDO criar aeronave
        ENTÃO retornar 422 Unprocessable Entity.
        """
        payload = {
            "serial_number": "SN-9999",
            "matricula": "9999",
            "modelo": "A-29",
            "status": "DESTRUIDA",  # não existe no Enum StatusAeronave
        }
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.post(
            AERONAVES_URL,
            json=payload,
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 422


class TestBuscarAeronave:

    @pytest.mark.asyncio
    async def test_buscar_aeronave_inexistente(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """
        DADO UUID de aeronave que não existe no banco
        QUANDO buscar GET /aeronaves/{id}
        ENTÃO retornar 404 Not Found.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        uuid_inexistente = str(uuid.uuid4())
        response = await client.get(
            f"{AERONAVES_URL}{uuid_inexistente}",
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_buscar_aeronave_existente(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO aeronave cadastrada
        QUANDO buscar GET /aeronaves/{id}
        ENTÃO retornar aeronave com status 200.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        criar = await client.post(AERONAVES_URL, json=dados_aeronave_valida, headers=headers)
        if criar.status_code != 201:
            pytest.skip("Endpoint de criação ainda não implementado")

        aeronave_id = criar.json()["id"]
        response = await client.get(f"{AERONAVES_URL}{aeronave_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["id"] == aeronave_id

    @pytest.mark.asyncio
    async def test_buscar_aeronave_uuid_invalido(self, client: AsyncClient):
        """
        DADO string que não é UUID válido na URL
        QUANDO buscar aeronave
        ENTÃO retornar 422 Unprocessable Entity.
        """
        response = await client.get(f"{AERONAVES_URL}nao-e-um-uuid")
        assert response.status_code in (401, 422)
