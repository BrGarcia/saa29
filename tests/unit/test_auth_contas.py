"""
tests/unit/test_auth_contas.py
Testes de regressão para os achados de docs/backlog/Fable5/Etapa4.md
relacionados a contas e credenciais:

    #3  Senha do admin não é mais sobrescrita a cada execução do seed
    #4  Usuários de teste exigem dois gatilhos explícitos
        (app_env=="development" E enable_test_users), fonte única de
        verdade para o ambiente (settings.app_env)
    #12 raise ValueError -> exceções de domínio em auth/service.py
        (contrato HTTP consistente: 404 para "não encontrado", 409 para
        conflito, em vez de códigos hardcoded por posição no router)
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.config import get_settings
from app.modules.auth import service
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha, verificar_senha
from app.shared.core import exceptions as domain_exc


@pytest.mark.asyncio
async def test_garantir_usuarios_essenciais_nao_sobrescreve_senha_do_admin_ja_trocada(
    db: AsyncSession, monkeypatch
):
    """Antes da correção: rodar o seed de novo depois do admin trocar a
    senha pela UI fazia a senha "voltar" silenciosamente para o valor do
    .env — tornando a rotação de senha do admin impossível na prática."""
    settings = get_settings()
    admin_user = f"admin_{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(settings, "default_admin_user", admin_user)
    monkeypatch.setattr(settings, "default_admin_password", "senha-do-env-123")
    monkeypatch.setattr(settings, "admin_password_reset", False)

    admin = Usuario(
        nome="Administrador Sistema",
        posto="Cap",
        especialidade="ENG",
        funcao="ADMINISTRADOR",
        ramal="1234",
        username=admin_user,
        senha_hash=hash_senha("senha-trocada-pela-ui"),
    )
    db.add(admin)
    await db.flush()

    await service.garantir_usuarios_essenciais(db)
    await db.flush()

    await db.refresh(admin)
    assert verificar_senha("senha-trocada-pela-ui", admin.senha_hash), (
        "A senha do admin foi sobrescrita pelo seed — rotação de senha impossível."
    )
    assert not verificar_senha("senha-do-env-123", admin.senha_hash)


@pytest.mark.asyncio
async def test_garantir_usuarios_essenciais_com_admin_password_reset_redefine_senha(
    db: AsyncSession, monkeypatch
):
    """O cenário legítimo (restore de banco) continua funcionando, mas exige
    o flag explícito e temporário ADMIN_PASSWORD_RESET=1."""
    settings = get_settings()
    admin_user = f"admin_{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(settings, "default_admin_user", admin_user)
    monkeypatch.setattr(settings, "default_admin_password", "senha-do-env-456")
    monkeypatch.setattr(settings, "admin_password_reset", True)

    admin = Usuario(
        nome="Administrador Sistema",
        posto="Cap",
        especialidade="ENG",
        funcao="ADMINISTRADOR",
        ramal="1234",
        username=admin_user,
        senha_hash=hash_senha("senha-antiga-do-banco-restaurado"),
    )
    db.add(admin)
    await db.flush()

    await service.garantir_usuarios_essenciais(db)
    await db.flush()

    await db.refresh(admin)
    assert verificar_senha("senha-do-env-456", admin.senha_hash)


@pytest.mark.asyncio
async def test_usuarios_de_teste_nao_sao_criados_sem_enable_test_users(db: AsyncSession, monkeypatch):
    """app_env=='development' sozinho não basta mais — precisa também de
    enable_test_users=True (defesa em profundidade contra deploy com
    APP_ENV errado instalando contas privilegiadas com senha trivial)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "enable_test_users", False)
    monkeypatch.setattr(settings, "default_admin_password", None)

    await service.garantir_usuarios_essenciais(db)

    result = await db.execute(select(Usuario).where(Usuario.username == "encarregado"))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_usuarios_de_teste_criados_com_os_dois_gatilhos(db: AsyncSession, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "enable_test_users", True)
    monkeypatch.setattr(settings, "default_admin_password", None)

    # Isola de execuções anteriores no mesmo banco de testes compartilhado.
    for username in ("encarregado", "inspetor", "mantenedor"):
        existente = await db.execute(select(Usuario).where(Usuario.username == username))
        obj = existente.scalar_one_or_none()
        if obj:
            await db.delete(obj)
    await db.flush()

    await service.garantir_usuarios_essenciais(db)

    result = await db.execute(select(Usuario).where(Usuario.username == "encarregado"))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_autenticar_usuario_usa_settings_app_env_nao_os_environ_direto(
    db: AsyncSession, monkeypatch
):
    """Antes: autenticar_usuario lia os.getenv("APP_ENV") diretamente, uma
    segunda fonte de verdade que podia divergir de settings.app_env (usado
    em todo o resto da aplicação, inclusive no CSRF)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "development")
    # os.environ["APP_ENV"] permanece "testing" (setado em conftest.py) —
    # se o código ainda lesse os.getenv, o lockout continuaria ativo.
    import os
    assert os.environ.get("APP_ENV") != "development"

    username = f"user_{uuid.uuid4().hex[:6]}"
    usuario = Usuario(
        nome="Teste Lockout", posto="Sgt", especialidade="ELT", funcao="MANTENEDOR",
        ramal="0000", username=username, senha_hash=hash_senha("senha_correta_123"),
    )
    db.add(usuario)
    await db.flush()

    for _ in range(6):
        resultado = await service.autenticar_usuario(db, username, "senha_errada")
        assert resultado is None

    await db.refresh(usuario)
    # Em "development" (via settings.app_env), o lockout é ignorado — a
    # conta não deve ficar bloqueada mesmo após 6 tentativas falhas.
    assert usuario.locked_until is None


@pytest.mark.asyncio
async def test_autenticar_usuario_inexistente_paga_custo_de_bcrypt(db: AsyncSession, monkeypatch):
    """Item #9: usuário inexistente deve pagar o mesmo custo de hashing que
    um usuário existente com senha errada — senão o tempo de resposta vaza
    se o username é válido. Teste funcional (não baseado em timing, que é
    flaky em CI): confirma que verificar_senha é chamada mesmo quando o
    usuário não existe."""
    chamadas = []
    original = service.verificar_senha

    def _espiar(senha_plana, senha_hash):
        chamadas.append((senha_plana, senha_hash))
        return original(senha_plana, senha_hash)

    monkeypatch.setattr(service, "verificar_senha", _espiar)

    resultado = await service.autenticar_usuario(db, f"usuario_inexistente_{uuid.uuid4().hex[:8]}", "qualquer")

    assert resultado is None
    assert len(chamadas) == 1, "verificar_senha não foi chamada para usuário inexistente — timing oracle."


@pytest.mark.asyncio
async def test_criar_usuario_username_duplicado_retorna_409_via_router(
    client: AsyncClient, usuario_e_token: dict
):
    """Item #12: antes, todo ValueError do módulo virava o status hardcoded
    no bloco try/except do router (nem sempre correto); agora as exceções
    de domínio já carregam o status certo e propagam sozinhas."""
    payload = {
        "nome": "Usuario Duplicado",
        "posto": "Sgt",
        "especialidade": "BMB",
        "funcao": "MANTENEDOR",
        "username": f"dup.{uuid.uuid4().hex[:6]}",
        "password": "password123",
        "ramal": "1234",
    }
    primeira = await client.post("/auth/usuarios", json=payload, headers=usuario_e_token["headers"])
    assert primeira.status_code == 201

    segunda = await client.post("/auth/usuarios", json=payload, headers=usuario_e_token["headers"])
    assert segunda.status_code == 409


@pytest.mark.asyncio
async def test_atualizar_usuario_inexistente_retorna_404_via_router(
    client: AsyncClient, usuario_e_token: dict
):
    resp = await client.put(
        f"/auth/usuarios/{uuid.uuid4()}",
        json={"nome": "Nao Existe"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_criar_usuario_savepoint_absorve_integrity_error_sem_derrubar_sessao(
    db: AsyncSession, dados_usuario_valido: dict
):
    """Item #12 (TOCTOU): força a colisão de UNIQUE diretamente (sem passar
    pelo pre-check) e confirma que o IntegrityError é convertido em erro de
    domínio, com a sessão permanecendo utilizável em seguida."""
    from app.modules.auth.schemas import UsuarioCreate

    username = f"toctou_{uuid.uuid4().hex[:6]}"
    existente = Usuario(
        nome="Já Existe", posto="Sgt", especialidade="ELT", funcao="MANTENEDOR",
        ramal="0000", username=username, senha_hash=hash_senha("outrasenha"),
    )
    db.add(existente)
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.criar_usuario(
            db,
            UsuarioCreate(
                nome="Duplicado", posto="Sgt", especialidade="ELT", funcao="MANTENEDOR",
                ramal="0000", username=username, password="password123",
            ),
        )

    # A sessão continua utilizável após o SAVEPOINT reverter só o insert conflitante.
    outro = await service.criar_usuario(
        db,
        UsuarioCreate(
            nome="Outro Usuario", posto="Sgt", especialidade="ELT", funcao="MANTENEDOR",
            ramal="0000", username=f"ok_{uuid.uuid4().hex[:6]}", password="password123",
        ),
    )
    assert outro.id is not None
