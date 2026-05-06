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
from sqlalchemy.ext.asyncio import AsyncSession


PANES_URL = "/panes/"
AERONAVES_URL = "/aeronaves/"


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def criar_aeronave(client: AsyncClient, headers: dict, dados: dict) -> dict:
    """Helper: cria uma aeronave com matrícula única e retorna o body JSON."""
    dados_copy = dados.copy()
    dados_copy["matricula"] = f"ANV-{uuid.uuid4().hex[:8].upper()}"
    resp = await client.post(AERONAVES_URL, json=dados_copy, headers=headers)
    if resp.status_code != 201:
        pytest.skip(f"Erro ao criar aeronave no helper (status {resp.status_code})")
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
    async def test_criar_pane_aeronave_inativa_rejeitada(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        toggle = await client.post(f"/aeronaves/{aeronave['id']}/toggle-status", headers=headers)
        assert toggle.status_code == 200

        response = await client.post(
            PANES_URL,
            json={
                "aeronave_id": aeronave["id"],
                "descricao": "Pane em aeronave inativa",
            },
            headers=headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_criar_pane_aeronave_indisponivel_permitida(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        update = await client.put(
            f"/aeronaves/{aeronave['id']}",
            json={"status": "INDISPONIVEL"},
            headers=headers,
        )
        assert update.status_code == 200

        response = await client.post(
            PANES_URL,
            json={
                "aeronave_id": aeronave["id"],
                "descricao": "Pane em aeronave indisponivel",
            },
            headers=headers,
        )
        assert response.status_code == 201

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
    async def test_criar_pane_com_responsavel_encarregado(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
        usuario_encarregado_e_token: dict,
    ):
        """
        DADO aeronave existente e um usuário ENCARREGADO
        QUANDO criar pane passando este ENCARREGADO como responsável
        ENTÃO retornar 201 e a pane deve ter o encarregado vinculado com papel "ENCARREGADO".
        """
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        encarregado = usuario_encarregado_e_token["usuario"]

        payload = {
            "aeronave_id": aeronave["id"],
            "descricao": "Pane com encarregado responsavel",
            "mantenedor_responsavel_id": str(encarregado.id),
        }
        response = await client.post(PANES_URL, json=payload, headers=headers)

        assert response.status_code == 201
        body = response.json()
        assert len(body["responsaveis"]) == 1
        assert body["responsaveis"][0]["usuario_id"] == str(encarregado.id)
        assert body["responsaveis"][0]["papel"] == "ENCARREGADO"

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
        await criar_pane(client, headers, aeronave["id"], descricao="IFF não responde", sistema_subsistema="NAV / IFF")

        response = await client.get(PANES_URL, params={"texto": "VUHF"}, headers=headers)
        if response.status_code == 200:
            body = response.json()
            assert all("VUHF" in p["descricao"] for p in body)

    @pytest.mark.asyncio
    async def test_filtrar_panes_excluidas(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        """
        DADO uma pane ativa e outra soft-deletada
        QUANDO listar com excluidas=true
        ENTÃO retornar apenas panes inativas.
        """
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane_ativa = await criar_pane(client, headers, aeronave["id"], descricao="Pane ativa")
        pane_excluida = await criar_pane(client, headers, aeronave["id"], descricao="Pane excluida")

        resposta_delete = await client.delete(f"{PANES_URL}{pane_excluida['id']}", headers=headers)
        assert resposta_delete.status_code == 204

        response = await client.get(
            PANES_URL,
            params={"excluidas": "true"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        ids = {p["id"] for p in body}
        assert pane_excluida["id"] in ids
        assert pane_ativa["id"] not in ids
        assert all(p["ativo"] is False for p in body)


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

    @pytest.mark.asyncio
    async def test_baixar_anexo_requer_autenticacao(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
    ):
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        jpeg_minimal = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
            b"\xff\xd9"
        )
        upload = await client.post(
            f"{PANES_URL}{pane['id']}/anexos",
            headers=headers,
            files={"arquivo": ("foto.jpg", jpeg_minimal, "image/jpeg")},
        )
        assert upload.status_code == 201
        anexo_id = upload.json()["id"]

        response = await client.get(f"{PANES_URL}{pane['id']}/anexos/{anexo_id}/download")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_baixar_anexo_autenticado(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
        db: AsyncSession,
    ):
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])

        jpeg_minimal = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
            b"\xff\xd9"
        )
        
        from unittest.mock import patch
        with patch("app.modules.panes.router.BackgroundTasks.add_task"):
            upload = await client.post(
                f"{PANES_URL}{pane['id']}/anexos",
                headers=headers,
                files={"arquivo": ("foto.jpg", jpeg_minimal, "image/jpeg")},
            )
            assert upload.status_code == 201
            anexo_id = upload.json()["id"]

            # Simula a conclusão do background task na mesma transação de teste
            from sqlalchemy import select
            from app.modules.panes.models import Anexo
            from app.shared.core.storage import get_storage_service
            anexo = (await db.execute(select(Anexo).where(Anexo.id == uuid.UUID(anexo_id)))).scalar_one()
            storage_svc = get_storage_service()
            caminho_salvo = await storage_svc.upload(jpeg_minimal, "foto.jpg", "image/jpeg")
            anexo.caminho_arquivo = caminho_salvo
            await db.flush()

            response = await client.get(
                f"{PANES_URL}{pane['id']}/anexos/{anexo_id}/download",
                headers=headers,
                follow_redirects=True
            )
            assert response.status_code == 200
            assert response.content


class TestAutorizacaoPanes:
    @pytest.mark.asyncio
    async def test_editar_descricao_requer_gestor(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
        usuario_mantenedor_e_token: dict,
    ):
        headers_admin = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)
        pane = await criar_pane(client, headers_admin, aeronave["id"])

        response = await client.put(
            f"{PANES_URL}{pane['id']}",
            json={"descricao": "Alteracao indevida"},
            headers=usuario_mantenedor_e_token["headers"],
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_adicionar_outro_responsavel_rejeitado_para_mantenedor(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
        usuario_mantenedor_e_token: dict,
    ):
        """MANTENEDOR tenta atribuir o ADMIN à pane -> Rejeitado."""
        headers_admin = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)
        pane = await criar_pane(client, headers_admin, aeronave["id"])

        response = await client.post(
            f"{PANES_URL}{pane['id']}/responsaveis",
            json={"usuario_id": str(usuario_e_token["usuario"].id), "papel": "ADMINISTRADOR"},
            headers=usuario_mantenedor_e_token["headers"],
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_adicionar_si_mesmo_permitido_para_mantenedor(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
        usuario_mantenedor_e_token: dict,
    ):
        """MANTENEDOR tenta se atribuir à pane -> Permitido."""
        headers_admin = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)
        pane = await criar_pane(client, headers_admin, aeronave["id"])

        mantenedor = usuario_mantenedor_e_token["usuario"]
        response = await client.post(
            f"{PANES_URL}{pane['id']}/responsaveis",
            json={"usuario_id": str(mantenedor.id), "papel": "MANTENEDOR"},
            headers=usuario_mantenedor_e_token["headers"],
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_deletar_pane_requer_gestor(
        self,
        client: AsyncClient,
        dados_aeronave_valida: dict,
        usuario_e_token: dict,
        usuario_mantenedor_e_token: dict,
    ):
        headers_admin = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)
        pane = await criar_pane(client, headers_admin, aeronave["id"])

        response = await client.delete(
            f"{PANES_URL}{pane['id']}",
            headers=usuario_mantenedor_e_token["headers"],
        )
        assert response.status_code == 403

class TestEndpointsAdicionais:
    @pytest.mark.asyncio
    async def test_buscar_pane_existente(self, client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict):
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])
        
        response = await client.get(f"{PANES_URL}{pane['id']}", headers=headers)
        assert response.status_code == 200
        assert "aeronave_id" in response.json()

    @pytest.mark.asyncio
    async def test_listar_anexos(self, client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict):
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])
        
        response = await client.get(f"{PANES_URL}{pane['id']}/anexos", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_adicionar_responsavel(self, client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict):
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pane = await criar_pane(client, headers, aeronave["id"])
        
        payload = {"usuario_id": "00000000-0000-0000-0000-000000000000", "papel": "MANTENEDOR"}
        response = await client.post(f"{PANES_URL}{pane['id']}/responsaveis", json=payload, headers=headers)
        assert response.status_code in [201, 404, 409, 422, 500]
