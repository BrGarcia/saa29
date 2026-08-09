"""
tests/security/test_refresh_token_rotacao.py
Testes de regressão para os achados críticos de docs/backlog/Fable5/Etapa4.md:

    #1  Revogação de família de refresh tokens desfeita por rollback
    #2  Ausência de validação do claim `type` em get_current_user (type confusion)
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import TokenRefresh, Usuario
from app.modules.auth.security import criar_refresh_token, decodificar_token, hash_senha


CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "fastapi-csrf-token"
LOGIN_URL = "/auth/login"
REFRESH_URL = "/auth/refresh"


async def _bootstrap_csrf(client: AsyncClient) -> str:
    response = await client.get("/login")
    assert response.status_code == 200
    csrf_token = response.headers.get(CSRF_HEADER)
    assert csrf_token
    return csrf_token


async def _criar_usuario_e_logar(client: AsyncClient, db: AsyncSession, dados_usuario_valido: dict):
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
        data={"username": username, "password": dados_usuario_valido["password"]},
        headers={CSRF_HEADER: csrf_token},
    )
    assert login_response.status_code == 200
    return usuario, login_response


@pytest.mark.asyncio
async def test_reuso_de_refresh_token_revogado_persiste_revogacao_da_familia(
    client: AsyncClient,
    db: AsyncSession,
    dados_usuario_valido: dict,
):
    """
    Reproduz o item #1: antes da correção, o UPDATE que revoga toda a família
    de refresh tokens era desfeito pelo rollback disparado pela própria
    HTTPException de 401 — a resposta dizia "todos os tokens foram
    revogados", mas nada persistia.

    Metodologia: depois de forçar a detecção de reuso, simulamos um rollback
    (o mesmo que aconteceria se qualquer outra parte do ciclo de vida da
    sessão de teste disparasse um) e confirmamos que a revogação sobrevive —
    prova de que ela foi de fato commitada, não apenas mantida em memória.
    """
    usuario, login_response = await _criar_usuario_e_logar(client, db, dados_usuario_valido)
    refresh_token_original = login_response.cookies.get("saa29_refresh_token")
    assert refresh_token_original

    # Cria um segundo refresh token "irmão" (mesma família/usuário) ainda
    # ativo, para provar que a revogação em massa realmente atinge outros
    # tokens do usuário, não só o que foi reusado.
    from datetime import datetime, timedelta, timezone
    outro_token_str, outro_jti = criar_refresh_token(usuario.id)
    outro_token = TokenRefresh(
        usuario_id=usuario.id,
        jti=str(outro_jti),
        expira_em=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(outro_token)
    await db.flush()

    csrf_token = login_response.headers.get(CSRF_HEADER)

    # 1a chamada: rotaciona e revoga o token original (fluxo normal).
    refresh_response = await client.post(
        REFRESH_URL,
        headers={CSRF_HEADER: csrf_token, "Cookie": f"saa29_refresh_token={refresh_token_original}"},
    )
    assert refresh_response.status_code == 200
    csrf_token = refresh_response.headers.get(CSRF_HEADER) or csrf_token

    # 2a chamada: reusa o token JÁ revogado -> deve disparar a detecção de
    # reuso e revogar toda a família (incluindo `outro_token`).
    replay_response = await client.post(
        REFRESH_URL,
        headers={CSRF_HEADER: csrf_token, "Cookie": f"saa29_refresh_token={refresh_token_original}"},
    )
    assert replay_response.status_code == 401
    assert "revogados" in replay_response.json()["detail"].lower()

    # Simula um rollback que aconteceria de qualquer forma no fim do ciclo de
    # vida da sessão de teste — sem o `db.commit()` da correção, isso
    # desfaria a revogação em massa e o teste falharia aqui.
    await db.rollback()

    result = await db.execute(select(TokenRefresh).where(TokenRefresh.usuario_id == usuario.id))
    tokens = {t.jti: t for t in result.scalars().all()}
    assert tokens[str(outro_jti)].revogado_em is not None, (
        "Token irmão não foi revogado — a revogação de família não persistiu."
    )


@pytest.mark.asyncio
async def test_refresh_token_nao_e_aceito_como_access_token(
    client: AsyncClient,
    db: AsyncSession,
    dados_usuario_valido: dict,
):
    """
    Reproduz o item #2: get_current_user não validava o claim `type`, então
    um refresh token (validade de 7 dias) seria aceito em endpoints
    protegidos como se fosse um access token (validade de 15 minutos),
    ignorando a blacklist de access tokens.
    """
    usuario, login_response = await _criar_usuario_e_logar(client, db, dados_usuario_valido)
    refresh_token = login_response.cookies.get("saa29_refresh_token")
    assert refresh_token

    payload = decodificar_token(refresh_token)
    assert payload["type"] == "refresh"

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401
