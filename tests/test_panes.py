"""
tests/test_panes.py
Testes de gestão de panes aeronáuticas.
Método Akita – Dia 3: stubs com docstrings Given/When/Then.
"""

import pytest
from httpx import AsyncClient


class TestCriarPane:

    @pytest.mark.asyncio
    async def test_criar_pane_sucesso(self, client: AsyncClient, dados_pane_valida: dict):
        """
        DADO aeronave existente e usuário autenticado
        QUANDO criar pane POST /panes/
        ENTÃO retornar pane com status=ABERTA e status HTTP 201.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_criar_pane_descricao_vazia_padrao(self, client: AsyncClient):
        """
        DADO payload com descrição vazia
        QUANDO criar pane
        ENTÃO descrição deve ser "AGUARDANDO EDICAO" (RN-05).
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_criar_pane_aeronave_inexistente(self, client: AsyncClient):
        """
        DADO ID de aeronave que não existe
        QUANDO criar pane
        ENTÃO retornar status 404 Not Found (RN-01).
        """
        # TODO (Dia 4): implementar
        pass


class TestListarPanes:

    @pytest.mark.asyncio
    async def test_listar_panes(self, client: AsyncClient):
        """
        DADO panes cadastradas
        QUANDO listar GET /panes/
        ENTÃO retornar lista e status 200.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_filtrar_panes_por_status(self, client: AsyncClient):
        """
        DADO panes com diferentes status
        QUANDO filtrar por status=ABERTA
        ENTÃO retornar apenas panes abertas (RF-06).
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_filtrar_panes_por_texto(self, client: AsyncClient):
        """
        DADO panes com diferentes descrições
        QUANDO filtrar por texto="VUHF"
        ENTÃO retornar apenas panes que contêm o texto (RF-06).
        """
        # TODO (Dia 4): implementar
        pass


class TestConcluirPane:

    @pytest.mark.asyncio
    async def test_concluir_pane_aberta(self, client: AsyncClient):
        """
        DADO pane com status=ABERTA
        QUANDO concluir via POST /panes/{id}/concluir
        ENTÃO status=RESOLVIDA e data_conclusao preenchida (RN-04).
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_concluir_pane_ja_resolvida(self, client: AsyncClient):
        """
        DADO pane com status=RESOLVIDA
        QUANDO tentar concluir novamente
        ENTÃO retornar status 409 Conflict.
        """
        # TODO (Dia 4): implementar
        pass


class TestTransicoesStatus:

    @pytest.mark.asyncio
    async def test_transicao_aberta_para_em_pesquisa(self, client: AsyncClient):
        """DADO pane ABERTA QUANDO mover para EM_PESQUISA ENTÃO aceitar."""
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_transicao_invalida_resolvida_para_aberta(self, client: AsyncClient):
        """DADO pane RESOLVIDA QUANDO tentar mover para ABERTA ENTÃO rejeitar (RN-03)."""
        # TODO (Dia 4): implementar
        pass


class TestUploadAnexo:

    @pytest.mark.asyncio
    async def test_upload_imagem_valida(self, client: AsyncClient):
        """
        DADO imagem JPG válida
        QUANDO fazer upload em POST /panes/{id}/anexos
        ENTÃO registrar anexo e retornar status 201.
        """
        # TODO (Dia 4): implementar
        pass

    @pytest.mark.asyncio
    async def test_upload_tipo_invalido(self, client: AsyncClient):
        """
        DADO arquivo .exe inválido
        QUANDO fazer upload
        ENTÃO retornar status 422.
        """
        # TODO (Dia 4): implementar
        pass
