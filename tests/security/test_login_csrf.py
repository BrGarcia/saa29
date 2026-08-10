"""
Regressao para o fluxo de login protegido por CSRF.
"""

import re

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha


CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "fastapi-csrf-token"
LOGIN_PAGE_URL = "/login"
LOGIN_URL = "/auth/login"


def _extrair_csrf_meta(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)">', html)
    assert match, "Pagina de login nao renderizou meta csrf-token."
    return match.group(1)


@pytest.mark.asyncio
async def test_login_html_com_csrf_nao_e_cacheavel(client: AsyncClient):
    response = await client.get(LOGIN_PAGE_URL)

    assert response.status_code == 200
    assert response.headers.get(CSRF_HEADER)
    assert client.cookies.get(CSRF_COOKIE)
    assert "no-store" in response.headers.get("Cache-Control", "")
    assert response.headers.get("Pragma") == "no-cache"
    assert response.headers.get("Expires") == "0"
    _extrair_csrf_meta(response.text)


@pytest.mark.asyncio
async def test_login_com_credenciais_validas_envia_csrf_real(
    client: AsyncClient,
    db: AsyncSession,
    dados_usuario_valido: dict,
):
    usuario = Usuario(
        nome=dados_usuario_valido["nome"],
        posto=dados_usuario_valido["posto"],
        funcao=dados_usuario_valido["funcao"],
        username=dados_usuario_valido["username"],
        senha_hash=hash_senha(dados_usuario_valido["password"]),
    )
    db.add(usuario)
    await db.flush()

    login_page_response = await client.get(LOGIN_PAGE_URL)
    csrf_token = _extrair_csrf_meta(login_page_response.text)

    response = await client.post(
        LOGIN_URL,
        data={
            "username": dados_usuario_valido["username"],
            "password": dados_usuario_valido["password"],
        },
        headers={
            CSRF_HEADER: csrf_token,
            # Sobrescreve o bypass padrao da fixture para validar o caminho real.
            "X-Skip-CSRF": "false",
        },
    )

    assert response.status_code == 200
    assert response.json()["usuario"]["username"] == dados_usuario_valido["username"]
    assert response.cookies.get("saa29_token")
    assert response.cookies.get("saa29_refresh_token")
    assert response.headers.get(CSRF_HEADER)
