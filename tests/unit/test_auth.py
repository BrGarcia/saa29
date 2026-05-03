"""
tests/test_auth.py
Testes de autenticação e gestão de usuários – SAA29.

Cobertura (ROADMAP Fase 2 – 2.1):
    - test_login_sucesso
    - test_login_senha_errada
    - test_login_usuario_inexistente
    - test_login_payload_invalido
    - test_acesso_sem_token
    - test_acesso_token_invalido
    - test_criar_usuario
    - test_criar_usuario_username_duplicado
    - test_listar_usuarios
    - test_atualizar_usuario
    - test_excluir_usuario
    - test_restaurar_usuario
    - test_alterar_senha
    - test_logout
    - test_rbac_protecao

Padrão: Given / When / Then
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha, criar_token


# ================================================================== #
#  Helpers
# ================================================================== #

LOGIN_URL = "/auth/login"
LOGOUT_URL = "/auth/logout"
USUARIOS_URL = "/auth/usuarios"
ME_URL = "/auth/me"
ROTA_PROTEGIDA = "/auth/usuarios"  # qualquer rota que exija auth


# ================================================================== #
#  Login
# ================================================================== #

class TestLogin:

    @pytest.mark.asyncio
    async def test_login_usuario_inexistente(self, client: AsyncClient):
        """
        DADO username que não existe no banco
        QUANDO tentar fazer login
        ENTÃO retornar 401 Unauthorized.
        """
        response = await client.post(
            LOGIN_URL,
            data={"username": "nao_existe", "password": "qualquer123"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_payload_invalido(self, client: AsyncClient):
        """
        DADO payload JSON sem os campos de formulário (form-data)
        QUANDO tentar fazer login via JSON (endpoint espera form-data)
        ENTÃO retornar 422 Unprocessable Entity.
        """
        response = await client.post(
            LOGIN_URL,
            json={"username": "joao.silva", "password": "senha123"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_sucesso(self, client: AsyncClient, db: AsyncSession, dados_usuario_valido: dict):
        """
        DADO um usuário válido já cadastrado no banco
        QUANDO enviar username e senha corretos via form-data
        ENTÃO retornar token JWT e status 200.
        """
        # Criar usuário direto no banco para testar o login
        usuario = Usuario(
            nome=dados_usuario_valido["nome"],
            posto=dados_usuario_valido["posto"],
            funcao=dados_usuario_valido["funcao"],
            username=dados_usuario_valido["username"],
            senha_hash=hash_senha(dados_usuario_valido["password"]),
        )
        db.add(usuario)
        await db.flush()

        response = await client.post(
            LOGIN_URL,
            data={
                "username": dados_usuario_valido["username"],
                "password": dados_usuario_valido["password"],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["usuario"]["username"] == dados_usuario_valido["username"]

    @pytest.mark.asyncio
    async def test_login_case_insensitive(self, client: AsyncClient, db: AsyncSession, dados_usuario_valido: dict):
        """
        DADO um usuário cadastrado com username 'joao.silva'
        QUANDO enviar username 'JOAO.SILVA' ou 'Joao.Silva'
        ENTÃO retornar token JWT e status 200.
        """
        unique_username = f"user_{uuid.uuid4().hex[:6]}"
        usuario = Usuario(
            nome=dados_usuario_valido["nome"],
            posto=dados_usuario_valido["posto"],
            funcao=dados_usuario_valido["funcao"],
            username=unique_username,
            senha_hash=hash_senha(dados_usuario_valido["password"]),
        )
        db.add(usuario)
        await db.flush()

        # Tentar com maiúsculas
        response = await client.post(
            LOGIN_URL,
            data={
                "username": unique_username.upper(),
                "password": dados_usuario_valido["password"],
            },
        )
        assert response.status_code == 200
        assert response.json()["usuario"]["username"] == unique_username

        # Tentar com CamelCase
        response = await client.post(
            LOGIN_URL,
            data={
                "username": unique_username.capitalize(),
                "password": dados_usuario_valido["password"],
            },
        )
        assert response.status_code == 200
        assert response.json()["usuario"]["username"] == unique_username

    @pytest.mark.asyncio
    async def test_login_senha_errada(self, client: AsyncClient, db: AsyncSession, dados_usuario_valido: dict):
        """
        DADO um usuário existente
        QUANDO enviar senha incorreta
        ENTÃO retornar 401 Unauthorized.
        """
        unique_username = f"user_{uuid.uuid4().hex[:6]}"
        usuario = Usuario(
            nome=dados_usuario_valido["nome"],
            posto=dados_usuario_valido["posto"],
            funcao=dados_usuario_valido["funcao"],
            username=unique_username,
            senha_hash=hash_senha(dados_usuario_valido["password"]),
        )
        db.add(usuario)
        await db.flush()

        response = await client.post(
            LOGIN_URL,
            data={
                "username": unique_username,
                "password": "senha_errada_total",
            },
        )
        assert response.status_code == 401


# ================================================================== #
#  Rotas Protegidas (Autenticação)
# ================================================================== #

class TestRotasProtegidas:

    @pytest.mark.asyncio
    async def test_acesso_sem_token(self, client: AsyncClient):
        """
        DADO uma requisição sem header Authorization
        QUANDO acessar rota protegida GET /auth/me
        ENTÃO retornar 401 Unauthorized.
        """
        response = await client.get(ME_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_acesso_token_invalido(self, client: AsyncClient):
        """
        DADO um token JWT adulterado (assinatura inválida)
        QUANDO acessar rota protegida
        ENTÃO retornar 401 Unauthorized.
        """
        response = await client.get(
            ME_URL,
            headers={"Authorization": "Bearer token.invalido.adulterado"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_acesso_formato_bearer_errado(self, client: AsyncClient):
        """
        DADO header Authorization sem prefixo 'Bearer'
        QUANDO acessar rota protegida
        ENTÃO retornar 401 ou 403.
        """
        response = await client.get(
            ME_URL,
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code in (401, 403)


# ================================================================== #
#  CRUD de Usuários e RBAC
# ================================================================== #

class TestGestaoUsuarios:

    @pytest.mark.asyncio
    async def test_criar_usuario_sucesso(self, client: AsyncClient, usuario_e_token: dict):
        """
        DADO um admin autenticado
        QUANDO criar um novo usuário válido
        ENTÃO retornar 201 e dados do usuário.
        """
        payload = {
            "nome": "Novo Usuario",
            "posto": "Sgt",
            "especialidade": "BMB",
            "funcao": "MANTENEDOR",
            "username": f"user.{uuid.uuid4().hex[:4]}",
            "password": "password123",
            "ramal": "1234"
        }
        response = await client.post(USUARIOS_URL, json=payload, headers=usuario_e_token["headers"])
        assert response.status_code == 201
        assert response.json()["username"] == payload["username"]

    @pytest.mark.asyncio
    async def test_listar_usuarios_sucesso(self, client: AsyncClient, usuario_e_token: dict):
        """
        DADO um usuário autenticado
        QUANDO listar usuários
        ENTÃO retornar 200 e uma lista.
        """
        response = await client.get(USUARIOS_URL, headers=usuario_e_token["headers"])
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_atualizar_usuario(self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict):
        """
        DADO um usuário existente e admin autenticado
        QUANDO atualizar nome e ramal
        ENTÃO retornar 200 e dados atualizados.
        """
        # Criar usuário alvo
        u = Usuario(nome="Original", posto="Ten", funcao="MANTENEDOR", username=f"u.{uuid.uuid4().hex[:4]}", senha_hash="...")
        db.add(u)
        await db.flush()

        payload = {"nome": "Nome Atualizado", "ramal": "9999"}
        response = await client.put(f"{USUARIOS_URL}/{u.id}", json=payload, headers=usuario_e_token["headers"])
        assert response.status_code == 200
        assert response.json()["nome"] == "Nome Atualizado"
        assert response.json()["ramal"] == "9999"

    @pytest.mark.asyncio
    async def test_excluir_e_restaurar_usuario(self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict):
        """
        DADO um usuário existente
        QUANDO deletar e depois restaurar
        ENTÃO verificar os status codes 204 e 200.
        """
        u = Usuario(nome="Para Deletar", posto="Sgt", funcao="MANTENEDOR", username=f"del.{uuid.uuid4().hex[:4]}", senha_hash="...")
        db.add(u)
        await db.flush()

        # Delete
        res_del = await client.delete(f"{USUARIOS_URL}/{u.id}", headers=usuario_e_token["headers"])
        assert res_del.status_code == 204

        # Restaurar
        res_rest = await client.post(f"{USUARIOS_URL}/{u.id}/restaurar", headers=usuario_e_token["headers"])
        assert res_rest.status_code == 200
        assert res_rest.json()["ativo"] is True

    @pytest.mark.asyncio
    async def test_alterar_senha(self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict, dados_usuario_valido: dict):
        """
        DADO o usuário logado
        QUANDO alterar a própria senha com a senha atual correta
        ENTÃO retornar 204.
        """
        # A senha do usuario_e_token (fixture do conftest) é a da fixture dados_usuario_valido
        payload = {
            "senha_atual": dados_usuario_valido["password"],
            "nova_senha": "nova_senha_678"
        }
        response = await client.put(f"/auth/usuarios/senha", json=payload, headers=usuario_e_token["headers"])
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_rbac_mantenedor_nao_pode_criar_usuario(self, client: AsyncClient, db: AsyncSession):
        """
        DADO um usuário MANTENEDOR autenticado
        QUANDO tentar criar um usuário
        ENTÃO retornar 403 Forbidden.
        """
        # Criar mantenedor
        u_man = Usuario(
            nome="Mantenedor", 
            posto="Sgt", 
            funcao="MANTENEDOR", 
            username="man.teste", 
            senha_hash=hash_senha("senha123")
        )
        db.add(u_man)
        await db.flush()
        
        # Token manual - USANDO O USERNAME (conforme router.py cria_token(dados={"sub": usuario.username}))
        token = criar_token({"sub": u_man.username})
        headers = {"Authorization": f"Bearer {token}"}
        
        payload = {"nome": "Invasor", "posto": "Sgt", "funcao": "ADMINISTRADOR", "username": "hack", "password": "123", "ramal": "0"}
        response = await client.post(USUARIOS_URL, json=payload, headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_logout_sucesso(self, client: AsyncClient, usuario_e_token: dict):
        """
        DADO um usuário logado
        QUANDO fizer logout
        ENTÃO retornar 204 No Content.
        """
        response = await client.post(LOGOUT_URL, headers=usuario_e_token["headers"])
        assert response.status_code == 204
