"""
tests/test_csrf.py
Testes de regressão para a proteção CSRF e sincronização do token no frontend.
"""

import uuid
from collections.abc import Callable

import pytest
from httpx import AsyncClient


CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "fastapi-csrf-token"
CSRF_BOOTSTRAP_URL = "/inventario"


def _nova_aeronave_payload() -> dict:
    sufixo = uuid.uuid4().hex[:6].upper()
    return {
        "serial_number": f"SN-CSRF-{sufixo}",
        "matricula": f"CS-{sufixo}",
        "modelo": "A-29",
        "status": "OPERACIONAL",
    }


def _url_put_aeronave() -> str:
    return f"/aeronaves/{uuid.uuid4()}"


def _url_delete_usuario() -> str:
    return f"/auth/usuarios/{uuid.uuid4()}"


WRITE_CASES = [
    pytest.param("POST", "/aeronaves/", _nova_aeronave_payload, id="post-aeronaves"),
    pytest.param(
        "PUT",
        _url_put_aeronave,
        lambda: {"modelo": "A-29B"},
        id="put-aeronaves",
    ),
    pytest.param("DELETE", _url_delete_usuario, lambda: None, id="delete-usuarios"),
]

AJAX_GET_ENDPOINTS = [
    "/auth/me",
    "/aeronaves/?limit=1&incluir_inativas=true",
    "/equipamentos/inventario/historico?limit=1",
]


def _resolver_url(url_ou_factory: str | Callable[[], str]) -> str:
    return url_ou_factory() if callable(url_ou_factory) else url_ou_factory


async def _fazer_requisicao_escrita(
    client: AsyncClient,
    metodo: str,
    url: str,
    headers: dict,
    payload: dict | None,
):
    # Sobrescrevemos o header X-Skip-CSRF para garantir que o teste seja real
    headers = headers.copy()
    headers["X-Skip-CSRF"] = "false"
    
    kwargs = {"headers": headers}
    if payload is not None:
        kwargs["json"] = payload
    return await client.request(metodo, url, **kwargs)


async def _bootstrap_csrf(client: AsyncClient) -> str:
    response = await client.get(CSRF_BOOTSTRAP_URL)
    assert response.status_code == 200

    token = response.headers.get(CSRF_HEADER)
    assert token, "Resposta inicial não retornou header X-CSRF-Token."
    assert client.cookies.get(CSRF_COOKIE), "Resposta inicial não definiu cookie CSRF."
    return token


class TestProtecaoCSRF:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("metodo,url_ou_factory,payload_factory", WRITE_CASES)
    async def test_bloqueia_escrita_sem_header_csrf(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
        metodo: str,
        url_ou_factory,
        payload_factory,
    ):
        """
        DADO um usuário autenticado
        QUANDO enviar POST/PUT/DELETE sem X-CSRF-Token
        ENTÃO o backend deve bloquear com 403 Forbidden.
        """
        response = await _fazer_requisicao_escrita(
            client=client,
            metodo=metodo,
            url=_resolver_url(url_ou_factory),
            headers=usuario_e_token["headers"],
            payload=payload_factory(),
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metodo,url_ou_factory,payload_factory", WRITE_CASES)
    async def test_bloqueia_escrita_com_token_csrf_invalido(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
        metodo: str,
        url_ou_factory,
        payload_factory,
    ):
        """
        DADO um usuário autenticado
        QUANDO enviar POST/PUT/DELETE com X-CSRF-Token adulterado
        ENTÃO o backend deve bloquear com 403 Forbidden.
        """
        headers = {
            **usuario_e_token["headers"],
            CSRF_HEADER: "csrf-token-invalido",
        }

        response = await _fazer_requisicao_escrita(
            client=client,
            metodo=metodo,
            url=_resolver_url(url_ou_factory),
            headers=headers,
            payload=payload_factory(),
        )

        assert response.status_code == 403


class TestSincronizacaoCSRF:
    @pytest.mark.asyncio
    async def test_respostas_ajax_get_retorna_header_csrf_para_sincronizacao(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
    ):
        """
        DADO um cliente que já recebeu o primeiro token CSRF
        QUANDO encadear chamadas AJAX de leitura
        ENTÃO cada resposta deve devolver X-CSRF-Token para o frontend se manter sincronizado.
        """
        token_atual = await _bootstrap_csrf(client)

        for endpoint in AJAX_GET_ENDPOINTS:
            response = await client.get(
                endpoint,
                headers={
                    **usuario_e_token["headers"],
                    CSRF_HEADER: token_atual,
                    "X-Skip-CSRF": "false",
                },
            )
            assert response.status_code == 200

            token_atual = response.headers.get(CSRF_HEADER)
            assert token_atual, f"Resposta de {endpoint} não retornou {CSRF_HEADER}."

    @pytest.mark.asyncio
    async def test_resposta_ajax_de_escrita_retorna_novo_header_csrf(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
    ):
        """
        DADO um cliente autenticado com CSRF inicializado
        QUANDO enviar uma mutation AJAX válida
        ENTÃO a resposta deve devolver X-CSRF-Token para a próxima requisição.
        """
        token_atual = await _bootstrap_csrf(client)

        response = await client.post(
            "/aeronaves/",
            json=_nova_aeronave_payload(),
            headers={
                **usuario_e_token["headers"],
                CSRF_HEADER: token_atual,
                "X-Skip-CSRF": "false",
            },
        )

        assert response.status_code == 201
        assert response.headers.get(CSRF_HEADER)
