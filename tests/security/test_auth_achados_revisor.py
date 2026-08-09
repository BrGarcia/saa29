"""
tests/security/test_auth_achados_revisor.py
Testes de regressão para os achados de docs/BACKLOG/revisor/achados_auth.md:

    BUG-01  Refresh token nunca é revogado no logout (cookie path)
    BUG-02  Troca/reset de senha não invalida refresh tokens ativos
    BUG-03  Proteção do último administrador contornável via atualizar_usuario
    BUG-04  garantir_usuarios_essenciais quebra invariante case-insensitive
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.config import get_settings
from app.modules.auth import service
from app.modules.auth.models import TokenRefresh, Usuario
from app.modules.auth.schemas import UsuarioUpdate
from app.modules.auth.security import criar_refresh_token, hash_senha
from app.shared.core import exceptions as domain_exc
from app.shared.core import helpers


CSRF_HEADER = "X-CSRF-Token"
LOGIN_URL = "/auth/login"
LOGOUT_URL = "/auth/logout"


async def _bootstrap_csrf(client: AsyncClient) -> str:
    response = await client.get("/login")
    assert response.status_code == 200
    csrf_token = response.headers.get(CSRF_HEADER)
    assert csrf_token
    return csrf_token


# ================================================================== #
#  BUG-01 — cookie path do refresh token
# ================================================================== #

@pytest.mark.asyncio
async def test_logout_revoga_refresh_token_via_cookie_persistido_pelo_client(
    client: AsyncClient, db: AsyncSession, dados_usuario_valido: dict,
):
    """Antes da correção, saa29_refresh_token tinha path="/auth/refresh" —
    fora desse path, um browser real (ou o cookie-jar do AsyncClient, que
    segue o mesmo RFC 6265 de path-matching) nunca enviaria o cookie no
    POST /auth/logout, e o bloco de revogação nunca executava de fato. Este
    teste NÃO envia o cookie manualmente — depende do client anexá-lo
    sozinho, exatamente como um browser faria."""
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
    assert login_response.cookies.get("saa29_refresh_token")

    result = await db.execute(select(TokenRefresh).where(TokenRefresh.usuario_id == usuario.id))
    stored = result.scalar_one()
    assert stored.revogado_em is None

    csrf_token = login_response.headers.get(CSRF_HEADER) or csrf_token
    logout_response = await client.post(LOGOUT_URL, headers={CSRF_HEADER: csrf_token})
    assert logout_response.status_code == 204

    assert stored.revogado_em is not None, (
        "Refresh token não foi revogado no logout — o cookie provavelmente "
        "não chegou ao endpoint (path incorreto)."
    )


@pytest.mark.asyncio
async def test_cookie_refresh_token_tem_path_raiz(
    client: AsyncClient, db: AsyncSession, dados_usuario_valido: dict,
):
    """Confirma explicitamente o atributo Path do Set-Cookie (BUG-01)."""
    username = f"{dados_usuario_valido['username']}_{uuid.uuid4().hex[:6]}"
    usuario = Usuario(
        nome=dados_usuario_valido["nome"], posto=dados_usuario_valido["posto"],
        especialidade=dados_usuario_valido["especialidade"], funcao=dados_usuario_valido["funcao"],
        ramal=dados_usuario_valido["ramal"], username=username,
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

    set_cookie_headers = login_response.headers.get_list("set-cookie")
    refresh_header = next(h for h in set_cookie_headers if h.startswith("saa29_refresh_token="))
    assert "path=/;" in refresh_header.lower() or refresh_header.lower().endswith("path=/")
    assert "path=/auth/refresh" not in refresh_header.lower()


# ================================================================== #
#  BUG-02 — troca/reset de senha revoga refresh tokens ativos
# ================================================================== #

async def _criar_usuario_com_refresh_ativo(db: AsyncSession, dados_usuario_valido: dict) -> tuple[Usuario, TokenRefresh]:
    usuario = Usuario(
        nome=dados_usuario_valido["nome"], posto=dados_usuario_valido["posto"],
        especialidade=dados_usuario_valido["especialidade"], funcao=dados_usuario_valido["funcao"],
        ramal=dados_usuario_valido["ramal"], username=f"{dados_usuario_valido['username']}_{uuid.uuid4().hex[:6]}",
        senha_hash=hash_senha(dados_usuario_valido["password"]),
    )
    db.add(usuario)
    await db.flush()

    _, jti = criar_refresh_token(usuario.id)
    refresh = TokenRefresh(
        usuario_id=usuario.id,
        jti=str(jti),
        expira_em=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(refresh)
    await db.flush()
    return usuario, refresh


@pytest.mark.asyncio
async def test_alterar_senha_revoga_refresh_tokens_ativos(db: AsyncSession, dados_usuario_valido: dict):
    usuario, refresh = await _criar_usuario_com_refresh_ativo(db, dados_usuario_valido)

    await service.alterar_senha(
        db, usuario, dados_usuario_valido["password"], "nova_senha_muito_segura_999"
    )

    await db.refresh(refresh)
    assert refresh.revogado_em is not None, (
        "Trocar a senha não revogou o refresh token ativo — sessão vazada continua válida."
    )


@pytest.mark.asyncio
async def test_admin_resetar_senha_revoga_refresh_tokens_ativos(db: AsyncSession, dados_usuario_valido: dict):
    usuario, refresh = await _criar_usuario_com_refresh_ativo(db, dados_usuario_valido)

    await service.admin_resetar_senha(db, usuario.id, "outra_senha_segura_999")

    await db.refresh(refresh)
    assert refresh.revogado_em is not None, (
        "Reset de senha pelo admin não revogou o refresh token ativo — a conta "
        "comprometida continuaria com a sessão do atacante ativa."
    )


# ================================================================== #
#  BUG-03 — atualizar_usuario não pode remover o último admin ativo
# ================================================================== #

async def _isolar_administradores_ativos(db: AsyncSession) -> None:
    """Neutraliza administradores ativos deixados por outros testes que
    fazem commit explícito no mesmo banco de testes compartilhado, para que
    o cenário "último administrador" seja determinístico. Só afeta a
    transação deste teste (revertido no rollback do fixture `db`)."""
    await db.execute(update(Usuario).where(Usuario.funcao == "ADMINISTRADOR").values(ativo=False))


@pytest.mark.asyncio
async def test_atualizar_usuario_nao_remove_papel_do_ultimo_administrador_ativo(db: AsyncSession):
    await _isolar_administradores_ativos(db)

    admin = Usuario(
        nome="Admin Único", posto="Cap", especialidade="ENG", funcao="ADMINISTRADOR",
        ramal="0000", username=f"admin_unico_{uuid.uuid4().hex[:6]}",
        senha_hash=hash_senha("senha123"),
    )
    db.add(admin)
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.atualizar_usuario(db, admin.id, UsuarioUpdate(funcao="MANTENEDOR"))

    await db.refresh(admin)
    assert admin.funcao == "ADMINISTRADOR"


@pytest.mark.asyncio
async def test_atualizar_usuario_permite_remover_admin_quando_ha_outro_ativo(db: AsyncSession):
    await _isolar_administradores_ativos(db)

    admin1 = Usuario(
        nome="Admin Um", posto="Cap", especialidade="ENG", funcao="ADMINISTRADOR",
        ramal="0000", username=f"admin1_{uuid.uuid4().hex[:6]}", senha_hash=hash_senha("senha123"),
    )
    admin2 = Usuario(
        nome="Admin Dois", posto="Cap", especialidade="ENG", funcao="ADMINISTRADOR",
        ramal="0000", username=f"admin2_{uuid.uuid4().hex[:6]}", senha_hash=hash_senha("senha123"),
    )
    db.add_all([admin1, admin2])
    await db.flush()

    atualizado = await service.atualizar_usuario(db, admin1.id, UsuarioUpdate(funcao="MANTENEDOR"))
    assert atualizado.funcao == "MANTENEDOR"


@pytest.mark.asyncio
async def test_excluir_usuario_nao_desativa_ultimo_administrador_ativo(db: AsyncSession):
    """Cobertura de regressão para a proteção original do AUD-17 em
    excluir_usuario, agora reescrita como UPDATE atômico (RISCO-07)."""
    await _isolar_administradores_ativos(db)

    admin = Usuario(
        nome="Admin Único", posto="Cap", especialidade="ENG", funcao="ADMINISTRADOR",
        ramal="0000", username=f"admin_solo_{uuid.uuid4().hex[:6]}",
        senha_hash=hash_senha("senha123"),
    )
    db.add(admin)
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.excluir_usuario(db, admin.id, usuario_logado_id=uuid.uuid4())

    await db.refresh(admin)
    assert admin.ativo is True


# ================================================================== #
#  BUG-04 — garantir_usuarios_essenciais é case-insensitive
# ================================================================== #

@pytest.mark.asyncio
async def test_garantir_usuarios_essenciais_nao_duplica_admin_com_case_diferente(
    db: AsyncSession, monkeypatch,
):
    """Antes: a busca em garantir_usuarios_essenciais era exata (sem
    .lower()), então DEFAULT_ADMIN_USER com qualquer maiúscula diferente do
    username já gravado (sempre lowercase) inseria um segundo registro
    'duplicado' — e a próxima busca de login (via func.lower(), usada em
    todo o sistema) levantava MultipleResultsFound, derrubando login e toda
    requisição autenticada com 500."""
    settings = get_settings()
    admin_user_lower = f"admin_{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(settings, "default_admin_user", admin_user_lower.upper())
    monkeypatch.setattr(settings, "default_admin_password", "senha-do-env-789")
    monkeypatch.setattr(settings, "admin_password_reset", False)

    existente = Usuario(
        nome="Administrador Sistema", posto="Cap", especialidade="ENG", funcao="ADMINISTRADOR",
        ramal="1234", username=admin_user_lower, senha_hash=hash_senha("senha-ja-configurada"),
    )
    db.add(existente)
    await db.flush()

    await service.garantir_usuarios_essenciais(db)
    await db.flush()

    result = await db.execute(
        select(Usuario).where(func.lower(Usuario.username) == admin_user_lower.lower())
    )
    todos = result.scalars().all()
    assert len(todos) == 1, "Criou um segundo usuário admin com case diferente."

    # A busca usada em todo login/autorização não pode mais explodir com
    # MultipleResultsFound.
    encontrado = await helpers.buscar_usuario_por_username(db, admin_user_lower.upper())
    assert encontrado is not None
    assert encontrado.id == existente.id
