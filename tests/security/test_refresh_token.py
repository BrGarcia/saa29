"""
tests/test_refresh_token.py
Testes de regressão para rotação e invalidação de refresh tokens.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import TokenRefresh, Usuario
from app.modules.auth.security import decodificar_token, hash_senha


CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "fastapi-csrf-token"
LOGIN_URL = "/auth/login"
REFRESH_URL = "/auth/refresh"


async def _bootstrap_csrf(client: AsyncClient) -> str:
    response = await client.get("/login")
    assert response.status_code == 200

    csrf_token = response.headers.get(CSRF_HEADER)
    assert csrf_token, "Resposta inicial não retornou header X-CSRF-Token."
    assert client.cookies.get(CSRF_COOKIE), "Resposta inicial não definiu cookie CSRF."
    return csrf_token


class TestRefreshTokenRotation:
    @pytest.mark.asyncio
    async def test_refresh_token_rotation_revoga_token_antigo_e_bloqueia_replay(
        self,
        client: AsyncClient,
        db: AsyncSession,
        dados_usuario_valido: dict,
    ):
        """
        DADO um usuário autenticado com refresh token válido
        QUANDO consumir /auth/refresh
        ENTÃO o backend deve gerar um novo par de tokens, revogar o refresh antigo
        e bloquear uma segunda reutilização do token anterior.
        """
        username = f"{dados_usuario_valido['username']}_{uuid.uuid4().hex[:6]}"
        usuario = Usuario(
            nome=dados_usuario_valido["nome"],
            posto=dados_usuario_valido["posto"],
            especialidade=dados_usuario_valido["especialidade"],
            funcao=dados_usuario_valido["funcao"],
            ramal=dados_usuario_valido["ramal"],
            username=username,
            senha_hash=hash_senha(dados_usuario_valido["password"]),
        )
        db.add(usuario)
        await db.flush()

        csrf_token = await _bootstrap_csrf(client)

        login_response = await client.post(
            LOGIN_URL,
            data={
                "username": username,
                "password": dados_usuario_valido["password"],
            },
            headers={CSRF_HEADER: csrf_token},
        )
        assert login_response.status_code == 200

        login_body = login_response.json()
        access_token_original = login_body["access_token"]
        refresh_token_original = login_body["refresh_token"]
        assert access_token_original
        assert refresh_token_original

        payload_access_original = decodificar_token(access_token_original)
        payload_refresh_original = decodificar_token(refresh_token_original)
        assert payload_access_original["type"] == "access"
        assert payload_access_original["sub"] == username
        assert payload_refresh_original["type"] == "refresh"
        assert payload_refresh_original["sub"] == str(usuario.id)

        csrf_token = login_response.headers.get(CSRF_HEADER) or csrf_token

        refresh_response = await client.post(
            REFRESH_URL,
            json={"refresh_token": refresh_token_original},
            headers={CSRF_HEADER: csrf_token},
        )
        assert refresh_response.status_code == 200

        refresh_body = refresh_response.json()
        access_token_novo = refresh_body["access_token"]
        refresh_token_novo = refresh_body["refresh_token"]
        assert access_token_novo != access_token_original
        assert refresh_token_novo != refresh_token_original

        payload_access_novo = decodificar_token(access_token_novo)
        payload_refresh_novo = decodificar_token(refresh_token_novo)
        assert payload_access_novo["type"] == "access"
        assert payload_access_novo["sub"] == username
        assert payload_access_novo["jti"] != payload_access_original["jti"]
        assert payload_refresh_novo["type"] == "refresh"
        assert payload_refresh_novo["sub"] == str(usuario.id)
        assert payload_refresh_novo["jti"] != payload_refresh_original["jti"]

        result = await db.execute(
            select(TokenRefresh).where(TokenRefresh.usuario_id == usuario.id)
        )
        refresh_tokens = {token.jti: token for token in result.scalars().all()}
        assert len(refresh_tokens) == 2
        assert refresh_tokens[payload_refresh_original["jti"]].revogado_em is not None
        assert refresh_tokens[payload_refresh_novo["jti"]].revogado_em is None

        csrf_token = refresh_response.headers.get(CSRF_HEADER) or csrf_token
        replay_response = await client.post(
            REFRESH_URL,
            json={"refresh_token": refresh_token_original},
            headers={CSRF_HEADER: csrf_token},
        )
        assert replay_response.status_code == 401
