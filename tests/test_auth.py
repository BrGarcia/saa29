"""
tests/test_auth.py
Testes de autenticação e gestão de usuários.
Método Akita – Dia 3: stubs sem implementação de lógica.
"""

import pytest
from httpx import AsyncClient


class TestLogin:
    """Testes do endpoint POST /auth/login."""

    @pytest.mark.asyncio
    async def test_login_sucesso(self, client: AsyncClient, dados_usuario_valido: dict):
        """
        DADO um usuário válido cadastrado
        QUANDO enviar username e senha corretos
        ENTÃO retornar token JWT e status 200.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_login_senha_errada(self, client: AsyncClient):
        """
        DADO um usuário existente
        QUANDO enviar senha incorreta
        ENTÃO retornar status 401 Unauthorized.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_login_usuario_inexistente(self, client: AsyncClient):
        """
        DADO username que não existe no banco
        QUANDO tentar fazer login
        ENTÃO retornar status 401 Unauthorized.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_login_campos_obrigatorios(self, client: AsyncClient):
        """
        DADO payload sem username ou senha
        QUANDO tentar fazer login
        ENTÃO retornar status 422 Unprocessable Entity.
        """
        # TODO (Dia 4): implementar
        pass


class TestRotasProtegidas:
    """Testes de acesso sem autenticação válida."""

    @pytest.mark.asyncio
    async def test_acesso_sem_token(self, client: AsyncClient):
        """
        DADO uma requisição sem token JWT
        QUANDO acessar rota protegida
        ENTÃO retornar status 401 Unauthorized.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_acesso_token_invalido(self, client: AsyncClient):
        """
        DADO um token JWT adulterado ou expirado
        QUANDO acessar rota protegida
        ENTÃO retornar status 401 Unauthorized.
        """
        # TODO (Dia 4): implementar
        pass


class TestGestaoUsuarios:
    """Testes de CRUD do efetivo."""

    @pytest.mark.asyncio
    async def test_criar_usuario(self, client: AsyncClient, dados_usuario_valido: dict):
        """
        DADO dados válidos de um novo usuário
        QUANDO criar via POST /auth/usuarios
        ENTÃO retornar o usuário criado e status 201.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_criar_usuario_username_duplicado(self, client: AsyncClient):
        """
        DADO um username já cadastrado
        QUANDO tentar criar outro usuário com mesmo username
        ENTÃO retornar status 409 Conflict.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_listar_usuarios(self, client: AsyncClient):
        """
        DADO usuários cadastrados no sistema
        QUANDO listar via GET /auth/usuarios
        ENTÃO retornar lista com status 200.
        """
        # TODO (Dia 4): implementar
        pass
