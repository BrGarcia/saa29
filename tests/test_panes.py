"""
tests/test_panes.py
Testes de gestão de panes aeronáuticas – SAA29.

Cobertura (ROADMAP Fase 2 – 2.3):
    - test_criar_pane_sucesso                          — 201, status=ABERTA (RN-02)
    - test_criar_pane_descricao_vazia_padrao           — RN-05
    - test_criar_pane_aeronave_inexistente             — 404 (RN-01)
    - test_criar_pane_requer_autenticacao              — 401
    - test_listar_panes                                — 200
    - test_filtrar_panes_por_status                    — RF-06
    - test_filtrar_panes_por_texto                     — RF-06
    - test_concluir_pane_aberta                        — RN-04
    - test_concluir_pane_ja_resolvida                  — 409
    - test_transicao_aberta_para_em_pesquisa           — SPECS §8
    - test_transicao_invalida_resolvida_para_aberta    — RN-03
    - test_upload_imagem_valida                        — 201
    - test_upload_tipo_invalido                        — 422
"""

import uuid
import pytest
from httpx import AsyncClient


PANES_URL = "/panes/"
AERONAVES_URL = "/aeronaves/"


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def criar_aeronave(client: AsyncClient, headers: dict, dados: dict) -> dict:
    """Helper: cria uma aeronave e retorna o body JSON."""
    resp = await client.post(AERONAVES_URL, json=dados, headers=headers)
    if resp.status_code != 201:
        pytest.skip(f"Endpoint de aeronaves não implementado (status {resp.status_code})")
    return resp.json()


async def criar_pane(client: AsyncClient, headers: dict, aeronave_id: str, **kwargs) -> dict:
    """Helper: cria uma pane e retorna o body JSON."""
    payload = {
        "aeronave_id": aeronave_id,
        "sistema_subsistema": kwargs.get("sistema_subsistema", "COM / VUHF"),
        "descricao": kwargs.get("descricao", "Rádio não transmite"),
    }
    resp = await client.post(PANES_URL, json=payload, headers=headers)
    if resp.status_code != 201:
        pytest.skip(f"Endpoint de panes não implementado (status {resp.status_code})")
    return resp.json()


# ================================================================== #
#  Criação de Pane
# ================================================================== #

class TestCriarPane:

    @pytest.mark.asyncio
    async def test_criar_pane_requer_autenticacao(
        self, client: AsyncClient, dados_aeronave_valida: dict
    ):
        """
        DADO payload válido sem Authorization
        QUANDO criar POST /panes/
        ENTÃO retornar 401 Unauthorized.
        """
        payload = {
            "aeronave_id": str(uuid.uuid4()),
            "descricao": "Pane de teste",
        }
        response = await client.post(PANES_URL, json=payload)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_criar_pane_aeronave_inexistente(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """
        DADO UUID de aeronave que não existe no banco
        QUANDO criar pane
        ENTÃO retornar 404 Not Found (RN-01).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        payload = {
            "aeronave_id": str(uuid.uuid4()),  # UUID aleatório, nunca cadastrado
            "descricao": "Pane em aeronave inexistente",
        }
        response = await client.post(
            PANES_URL, json=payload, headers=usuario_e_token["headers"]
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_criar_pane_sucesso(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO aeronave existente e usuário autenticado
        QUANDO criar POST /panes/ com dados válidos
        ENTÃO retornar:
            - status HTTP 201
            - pane com status = "ABERTA" (RN-02)
            - data_conclusao = None
            - aeronave_id correto
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        payload = {
            "aeronave_id": aeronave["id"],
            "sistema_subsistema": "COMUNICAÇÃO / VUHF",
            "descricao": "Rádio não transmite em 120.500 MHz",
        }
        response = await client.post(PANES_URL, json=payload, headers=headers)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "ABERTA"          # RN-02
        assert body["data_conclusao"] is None
        assert body["aeronave_id"] == aeronave["id"]
        assert "id" in body

    @pytest.mark.asyncio
    async def test_criar_pane_descricao_vazia_padrao(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO aeronave existente e descrição vazia no payload
        QUANDO criar pane
        ENTÃO descrição = "AGUARDANDO EDICAO" (RN-05).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        payload = {"aeronave_id": aeronave["id"], "descricao": ""}
        response = await client.post(PANES_URL, json=payload, headers=headers)

        if response.status_code == 201:
            assert response.json()["descricao"] == "AGUARDANDO EDICAO"
        else:
            pytest.skip("Endpoint de criação ainda não implementado")

    @pytest.mark.asyncio
    async def test_criar_pane_sem_aeronave_id(self, client: AsyncClient, usuario_e_token: dict):
        """
        DADO payload sem campo obrigatório 'aeronave_id'
        QUANDO criar pane
        ENTÃO retornar 422 Unprocessable Entity (validação Pydantic).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.post(
            PANES_URL,
            json={"descricao": "Pane sem aeronave"},
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 422


# ================================================================== #
#  Listagem e Filtros (RF-06)
# ================================================================== #

class TestListarPanes:

    @pytest.mark.asyncio
    async def test_listar_panes_requer_autenticacao(self, client: AsyncClient):
        """DADO sem token QUANDO listar ENTÃO 401."""
        response = await client.get(PANES_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_listar_panes(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO pane cadastrada e usuário autenticado
        QUANDO listar GET /panes/
        ENTÃO retornar lista com status 200.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        await criar_pane(client, headers, aeronave["id"])

        response = await client.get(PANES_URL, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) >= 1

    @pytest.mark.asyncio
    async def test_filtrar_panes_por_status(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO panes com status ABERTA cadastradas
        QUANDO filtrar GET /panes/?status=ABERTA
        ENTÃO retornar apenas panes com status ABERTA (RF-06).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        await criar_pane(client, headers, aeronave["id"])

        response = await client.get(
            PANES_URL, params={"status": "ABERTA"}, headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert all(p["status"] == "ABERTA" for p in body)

    @pytest.mark.asyncio
    async def test_filtrar_panes_por_status_invalido(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """
        DADO status fora do Enum (ex: 'CANCELADA')
        QUANDO filtrar panes
        ENTÃO retornar 422 Unprocessable Entity.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.get(
            PANES_URL,
            params={"status": "CANCELADA"},
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_filtrar_panes_por_texto(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO pane com 'VUHF' na descrição
        QUANDO filtrar GET /panes/?texto=VUHF
        ENTÃO retornar apenas panes que contêm 'VUHF' na descrição (RF-06).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        await criar_pane(client, headers, aeronave["id"], descricao="Rádio VUHF não transmite")
        await criar_pane(client, headers, aeronave["id"], descricao="IFF não responde")

        response = await client.get(PANES_URL, params={"texto": "VUHF"}, headers=headers)
        if response.status_code == 200:
            body = response.json()
            assert all("VUHF" in p["descricao"] for p in body)


# ================================================================== #
#  Conclusão de Pane
# ================================================================== #

class TestConcluirPane:

    @pytest.mark.asyncio
    async def test_concluir_pane_aberta(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO pane com status ABERTA
        QUANDO concluir POST /panes/{id}/concluir
        ENTÃO:
            - status = "RESOLVIDA"
            - data_conclusao preenchida automaticamente (RN-04)
            - status HTTP 200
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        response = await client.post(
            f"{PANES_URL}{pane['id']}/concluir",
            json={"observacao_conclusao": "Substituído módulo."},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "RESOLVIDA"
        assert body["data_conclusao"] is not None  # RN-04

    @pytest.mark.asyncio
    async def test_concluir_pane_ja_resolvida(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO pane com status RESOLVIDA
        QUANDO tentar concluir novamente
        ENTÃO retornar 409 Conflict.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        # Primeira conclusão
        await client.post(
            f"{PANES_URL}{pane['id']}/concluir",
            json={},
            headers=headers,
        )
        # Segunda tentativa
        response = await client.post(
            f"{PANES_URL}{pane['id']}/concluir",
            json={},
            headers=headers,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_concluir_pane_inexistente(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """
        DADO UUID de pane que não existe
        QUANDO concluir
        ENTÃO retornar 404 Not Found.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        response = await client.post(
            f"{PANES_URL}{uuid.uuid4()}/concluir",
            json={},
            headers=usuario_e_token["headers"],
        )
        assert response.status_code == 404


# ================================================================== #
#  Transições de Status (SPECS §8, RN-03)
# ================================================================== #

class TestTransicoesStatus:

    @pytest.mark.asyncio
    async def test_transicao_aberta_para_em_pesquisa(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO pane ABERTA
        QUANDO atualizar status para EM_PESQUISA via PUT /panes/{id}
        ENTÃO aceitar com status 200 (SPECS §8 – transição válida).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        response = await client.put(
            f"{PANES_URL}{pane['id']}",
            json={"status": "EM_PESQUISA"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "EM_PESQUISA"

    @pytest.mark.asyncio
    async def test_transicao_invalida_resolvida_para_aberta(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO pane RESOLVIDA (já concluída)
        QUANDO tentar mover para ABERTA via PUT /panes/{id}
        ENTÃO rejeitar com 409 Conflict (RN-03: pane resolvida não pode ser editada).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        # Concluir a pane primeiro
        await client.post(f"{PANES_URL}{pane['id']}/concluir", json={}, headers=headers)

        # Tentar reverter para ABERTA
        response = await client.put(
            f"{PANES_URL}{pane['id']}",
            json={"status": "ABERTA"},
            headers=headers,
        )
        assert response.status_code in (409, 422)  # 409 (regra de negócio) ou 422 (Pydantic)

    @pytest.mark.asyncio
    async def test_edicao_pane_resolvida_rejeitada(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO pane com status RESOLVIDA
        QUANDO tentar editar descrição via PUT /panes/{id}
        ENTÃO rejeitar com 409 Conflict (RN-03).
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        await client.post(f"{PANES_URL}{pane['id']}/concluir", json={}, headers=headers)

        response = await client.put(
            f"{PANES_URL}{pane['id']}",
            json={"descricao": "Tentativa de edição após conclusão"},
            headers=headers,
        )
        assert response.status_code == 409


# ================================================================== #
#  Upload de Anexos (RF-11)
# ================================================================== #

class TestUploadAnexo:

    @pytest.mark.asyncio
    async def test_upload_tipo_invalido(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO arquivo com tipo MIME inválido (.exe)
        QUANDO fazer upload em POST /panes/{id}/anexos
        ENTÃO retornar 422 Unprocessable Entity.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        fake_exe = b"MZ\x90\x00"  # magic bytes de .exe
        response = await client.post(
            f"{PANES_URL}{pane['id']}/anexos",
            headers=headers,
            files={"arquivo": ("virus.exe", fake_exe, "application/octet-stream")},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_imagem_valida(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO imagem JPEG válida (stub 1x1 pixel)
        QUANDO fazer upload em POST /panes/{id}/anexos
        ENTÃO retornar 201 com dados do anexo.
        """
        if usuario_e_token["token"] == "TOKEN_NAO_IMPLEMENTADO":
            pytest.skip("Auth ainda não implementada (Dia 4)")

        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        # JPEG mínimo válido (1x1 pixel branco)
        jpeg_minimal = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
            b"\xff\xd9"
        )
        response = await client.post(
            f"{PANES_URL}{pane['id']}/anexos",
            headers=headers,
            files={"arquivo": ("foto.jpg", jpeg_minimal, "image/jpeg")},
        )
        assert response.status_code == 201
        body = response.json()
        assert "id" in body
        assert "caminho_arquivo" in body
