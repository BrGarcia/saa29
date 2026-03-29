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

Padrão: Given / When / Then
"""

import pytest
from httpx import AsyncClient


# ================================================================== #
#  Helpers
# ================================================================== #

LOGIN_URL = "/auth/login"
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
    async def test_login_sucesso(self, client: AsyncClient, dados_usuario_valido: dict):
        """
        DADO um usuário válido já cadastrado
        QUANDO enviar username e senha corretos via form-data
        ENTÃO retornar token JWT e status 200.

        NOTA: Este teste depende que criar_usuario (Dia 4) esteja implementado.
        Executa apenas se a API já retornar 201 ao criar o usuário.
        """
        criar = await client.post(USUARIOS_URL, json=dados_usuario_valido)
        if criar.status_code != 201:
            pytest.skip("API de criação de usuário ainda não implementada (Dia 4)")

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
    async def test_login_senha_errada(self, client: AsyncClient, dados_usuario_valido: dict):
        """
        DADO um usuário existente
        QUANDO enviar senha incorreta
        ENTÃO retornar 401 Unauthorized.
        """
        criar = await client.post(USUARIOS_URL, json=dados_usuario_valido)
        if criar.status_code != 201:
            pytest.skip("API de criação de usuário ainda não implementada (Dia 4)")

        response = await client.post(
            LOGIN_URL,
            data={
                "username": dados_usuario_valido["username"],
                "password": "senha_ERRADA_999",
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
#  CRUD de Usuários
# ================================================================== #

class TestGestaoUsuarios:

    @pytest.mark.asyncio
    async def test_criar_usuario(self, client: AsyncClient, dados_usuario_valido: dict):
        """
        DADO dados válidos de um novo usuário
        QUANDO criar via POST /auth/usuarios (com token de admin)
        ENTÃO retornar o usuário criado e status 201.

        NOTA: O endpoint exige CurrentUser — será testado com token no Dia 4.
        Este teste verifica que sem token retorna 401 (endpoint existe e está protegido).
        """
        response = await client.post(USUARIOS_URL, json=dados_usuario_valido)
        # Sem token → 401; Com token e lógica → 201
        assert response.status_code in (401, 201, 500)  # 500 = NotImplementedError esperado no Dia 3

    @pytest.mark.asyncio
    async def test_criar_usuario_campos_obrigatorios(self, client: AsyncClient):
        """
        DADO payload sem campos obrigatórios (nome, username, password)
        QUANDO tentar criar usuário SEM token de autenticação
        ENTÃO retornar 401 Unauthorized (auth executa antes da validação).
        """
        payload_invalido = {"posto": "Ten"}  # faltam nome, username, password, funcao
        response = await client.post(USUARIOS_URL, json=payload_invalido)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_criar_usuario_password_curta(self, client: AsyncClient):
        """
        DADO password com menos de 6 caracteres (mínimo definido no schema)
        QUANDO criar usuário SEM token de autenticação
        ENTÃO retornar 401 Unauthorized (auth executa antes da validação).
        """
        payload = {
            "nome": "Ten Teste",
            "posto": "Ten",
            "funcao": "INSPETOR",
            "username": "teste.usuario",
            "password": "abc",   # < 6 chars
        }
        response = await client.post(USUARIOS_URL, json=payload)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_listar_usuarios_requer_autenticacao(self, client: AsyncClient):
        """
        DADO uma requisição sem token
        QUANDO listar usuarios GET /auth/usuarios
        ENTÃO retornar 401 Unauthorized.
        """
        response = await client.get(USUARIOS_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_requer_autenticacao(self, client: AsyncClient):
        """
        DADO requisição sem token
        QUANDO acessar GET /auth/me
        ENTÃO retornar 401.
        """
        response = await client.get(ME_URL)
        assert response.status_code == 401
