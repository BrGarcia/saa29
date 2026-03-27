"""
tests/test_aeronaves.py
Testes de gestão de aeronaves.
Método Akita – Dia 3: stubs com docstrings Given/When/Then.
"""

import pytest
from httpx import AsyncClient


class TestListarAeronaves:

    @pytest.mark.asyncio
    async def test_listar_aeronaves_vazio(self, client: AsyncClient):
        """
        DADO banco sem aeronaves
        QUANDO listar GET /aeronaves/
        ENTÃO retornar lista vazia e status 200.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_listar_aeronaves_com_dados(self, client: AsyncClient, dados_aeronave_valida: dict):
        """
        DADO aeronaves cadastradas
        QUANDO listar GET /aeronaves/
        ENTÃO retornar lista preenchida e status 200.
        """
        # TODO (Dia 4): implementar
        pass


class TestCriarAeronave:

    @pytest.mark.asyncio
    async def test_criar_aeronave_sucesso(self, client: AsyncClient, dados_aeronave_valida: dict):
        """
        DADO dados válidos de aeronave
        QUANDO criar via POST /aeronaves/
        ENTÃO retornar aeronave criada e status 201.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_criar_aeronave_matricula_duplicada(self, client: AsyncClient):
        """
        DADO matrícula já cadastrada
        QUANDO criar outra aeronave com mesma matrícula
        ENTÃO retornar status 409 Conflict.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_criar_aeronave_sem_matricula(self, client: AsyncClient):
        """
        DADO payload sem campo matricula (obrigatório)
        QUANDO criar aeronave
        ENTÃO retornar status 422 Unprocessable Entity.
        """
        # TODO (Dia 4): implementar
        pass


class TestBuscarAeronave:

    @pytest.mark.asyncio
    async def test_buscar_aeronave_existente(self, client: AsyncClient):
        """
        DADO aeronave cadastrada com ID conhecido
        QUANDO buscar GET /aeronaves/{id}
        ENTÃO retornar aeronave e status 200.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_buscar_aeronave_inexistente(self, client: AsyncClient):
        """
        DADO ID de aeronave que não existe
        QUANDO buscar GET /aeronaves/{id}
        ENTÃO retornar status 404 Not Found.
        """
        # TODO (Dia 4): implementar
        pass
