"""
tests/test_inventario.py
Testes TDD para o módulo de Inventário de Equipamentos por Aeronave – SAA29.

Escritos ANTES da implementação (TDD – Red → Green → Refactor).
Todos os testes devem FALHAR até que a Fase 1 do plano de implementação
(endpoint de inventário e schema) seja concluída.

Cobertura:
    - TestInventarioEndpoint: endpoint GET /equipamentos/inventario/{aeronave_id}
    - TestInventarioFiltros: filtragem por nome de equipamento via query param
    - TestInventarioPermissoes: controle de acesso (autenticação e perfis)
    - TestInventarioAgrupamento: agrupamento correto por localização/sistema
    - TestInventarioEdgeCases: casos de borda e dados vazios
"""

import uuid
import pytest
from datetime import date
from httpx import AsyncClient


EQUIP_URL = "/equipamentos"
ITENS_URL = "/equipamentos/itens/"
TIPOS_URL = "/equipamentos/tipos-controle"
AERONAVES_URL = "/aeronaves/"
INVENTARIO_URL = "/equipamentos/inventario"


# ------------------------------------------------------------------ #
#  Helpers (reutilizando o padrão de test_equipamentos.py)
# ------------------------------------------------------------------ #

async def _criar_equipamento(client: AsyncClient, headers: dict, nome: str, pn: str, sistema: str | None = None) -> dict:
    """Helper: cria um tipo de equipamento."""
    payload = {"part_number": pn, "nome": nome, "sistema": sistema, "descricao": f"Equipamento {nome}"}
    resp = await client.post(f"{EQUIP_URL}/", json=payload, headers=headers)
    assert resp.status_code == 201, f"Falha ao criar equipamento {nome}: {resp.text}"
    return resp.json()


async def _criar_item(client: AsyncClient, headers: dict, equip_id: str, numero_serie: str) -> dict:
    """Helper: cria um item (instância física) de equipamento."""
    payload = {"equipamento_id": equip_id, "numero_serie": numero_serie, "status": "ATIVO"}
    resp = await client.post(ITENS_URL, json=payload, headers=headers)
    assert resp.status_code == 201, f"Falha ao criar item {numero_serie}: {resp.text}"
    return resp.json()


async def _criar_aeronave(client: AsyncClient, headers: dict, matricula: str, serial: str) -> dict:
    """Helper: cria uma aeronave."""
    payload = {"serial_number": serial, "matricula": matricula, "modelo": "A-29", "status": "OPERACIONAL"}
    resp = await client.post(AERONAVES_URL, json=payload, headers=headers)
    assert resp.status_code == 201, f"Falha ao criar aeronave {matricula}: {resp.text}"
    return resp.json()


async def _instalar_item(client: AsyncClient, headers: dict, item_id: str, aeronave_id: str) -> dict:
    """Helper: instala um item em uma aeronave."""
    payload = {"aeronave_id": aeronave_id, "data_instalacao": date.today().isoformat()}
    resp = await client.post(f"{EQUIP_URL}/itens/{item_id}/instalar", json=payload, headers=headers)
    assert resp.status_code == 201, f"Falha ao instalar item {item_id}: {resp.text}"
    return resp.json()


async def _montar_inventario_completo(client: AsyncClient, headers: dict) -> dict:
    """
    Helper composto: cria uma aeronave com 3 equipamentos instalados em 2 compartimentos.
    Retorna dict com aeronave, equipamentos e itens criados.
    """
    # Aeronave
    aeronave = await _criar_aeronave(client, headers, "5916", "SN-TEST-001")

    # Equipamentos em compartimentos diferentes
    equip_adf = await _criar_equipamento(client, headers, "ADF", "622-7382-101", "COMP. ELETRONICO")
    equip_vuhf = await _criar_equipamento(client, headers, "VUHF1", "6110.3001.12", "COMP. ELETRONICO")
    equip_pdu = await _criar_equipamento(client, headers, "PDU", "4455-1000-01", "1P")

    # Itens (serial numbers)
    item_adf = await _criar_item(client, headers, equip_adf["id"], "SN-ADF-001")
    item_vuhf = await _criar_item(client, headers, equip_vuhf["id"], "SN-VUHF-001")
    item_pdu = await _criar_item(client, headers, equip_pdu["id"], "SN-PDU-001")

    # Instalar na aeronave
    await _instalar_item(client, headers, item_adf["id"], aeronave["id"])
    await _instalar_item(client, headers, item_vuhf["id"], aeronave["id"])
    await _instalar_item(client, headers, item_pdu["id"], aeronave["id"])

    return {
        "aeronave": aeronave,
        "equipamentos": [equip_adf, equip_vuhf, equip_pdu],
        "itens": [item_adf, item_vuhf, item_pdu],
    }


# ================================================================== #
#  T01–T05: Endpoint de Inventário (Fase 1)
# ================================================================== #

class TestInventarioEndpoint:
    """Testes do endpoint GET /equipamentos/inventario/{aeronave_id}"""

    @pytest.mark.asyncio
    async def test_t01_inventario_retorna_itens_instalados(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T01: DADO aeronave com 3 itens instalados
             QUANDO GET /equipamentos/inventario/{aeronave_id}
             ENTÃO retornar lista com 3 itens e status 200.
        """
        headers = usuario_e_token["headers"]
        dados = await _montar_inventario_completo(client, headers)

        response = await client.get(
            f"{INVENTARIO_URL}/{dados['aeronave']['id']}", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 3

    @pytest.mark.asyncio
    async def test_t02_inventario_contem_campos_obrigatorios(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T02: DADO inventário com itens instalados
             QUANDO consultar o inventário
             ENTÃO cada item deve conter: equipamento_nome, part_number, sistema,
                  numero_serie, status_item, instalacao_id, data_instalacao.
        """
        headers = usuario_e_token["headers"]
        dados = await _montar_inventario_completo(client, headers)

        response = await client.get(
            f"{INVENTARIO_URL}/{dados['aeronave']['id']}", headers=headers
        )
        assert response.status_code == 200
        body = response.json()

        campos_obrigatorios = [
            "equipamento_nome", "part_number", "sistema",
            "numero_serie", "status_item", "instalacao_id", "data_instalacao",
        ]
        for item in body:
            for campo in campos_obrigatorios:
                assert campo in item, f"Campo '{campo}' ausente no item de inventário"

    @pytest.mark.asyncio
    async def test_t03_inventario_ignora_itens_removidos(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T03: DADO aeronave com 3 itens, sendo 1 removido (data_remocao != NULL)
             QUANDO consultar inventário
             ENTÃO retornar apenas 2 itens (somente instalações ativas).
        """
        headers = usuario_e_token["headers"]
        aeronave = await _criar_aeronave(client, headers, "5902", "SN-TEST-003")

        equip1 = await _criar_equipamento(client, headers, "DME", "622-7309-101", "COMP. ELETRONICO")
        equip2 = await _criar_equipamento(client, headers, "TDR", "622-9352-004", "COMP. ELETRONICO")

        item1 = await _criar_item(client, headers, equip1["id"], "SN-DME-001")
        item2 = await _criar_item(client, headers, equip2["id"], "SN-TDR-001")

        inst1 = await _instalar_item(client, headers, item1["id"], aeronave["id"])
        await _instalar_item(client, headers, item2["id"], aeronave["id"])

        # Remover o primeiro item
        await client.patch(
            f"{EQUIP_URL}/instalacoes/{inst1['id']}/remover",
            json={"data_remocao": date.today().isoformat()},
            headers=headers,
        )

        response = await client.get(
            f"{INVENTARIO_URL}/{aeronave['id']}", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1, "Inventário deve conter apenas itens com instalação ativa"
        assert body[0]["numero_serie"] == "SN-TDR-001"

    @pytest.mark.asyncio
    async def test_t04_inventario_aeronave_sem_itens(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T04: DADO aeronave sem nenhum equipamento instalado
             QUANDO consultar inventário
             ENTÃO retornar lista vazia [] com status 200.
        """
        headers = usuario_e_token["headers"]
        aeronave = await _criar_aeronave(client, headers, "5903", "SN-TEST-004")

        response = await client.get(
            f"{INVENTARIO_URL}/{aeronave['id']}", headers=headers
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_t05_inventario_aeronave_inexistente(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T05: DADO UUID de aeronave que não existe
             QUANDO consultar inventário
             ENTÃO retornar 404 Not Found.
        """
        headers = usuario_e_token["headers"]
        fake_id = str(uuid.uuid4())

        response = await client.get(
            f"{INVENTARIO_URL}/{fake_id}", headers=headers
        )
        assert response.status_code == 404


# ================================================================== #
#  T06–T07: Filtros
# ================================================================== #

class TestInventarioFiltros:
    """Testes de filtro por nome de equipamento."""

    @pytest.mark.asyncio
    async def test_t06_filtro_por_nome_equipamento(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T06: DADO inventário com ADF, VUHF1 e PDU
             QUANDO filtrar com ?nome=ADF
             ENTÃO retornar apenas 1 item (ADF).
        """
        headers = usuario_e_token["headers"]
        dados = await _montar_inventario_completo(client, headers)

        response = await client.get(
            f"{INVENTARIO_URL}/{dados['aeronave']['id']}?nome=ADF", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["equipamento_nome"] == "ADF"

    @pytest.mark.asyncio
    async def test_t07_filtro_por_nome_parcial(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T07: DADO inventário com ADF, VUHF1 e PDU
             QUANDO filtrar com ?nome=VU (busca parcial, case-insensitive)
             ENTÃO retornar 1 item (VUHF1).
        """
        headers = usuario_e_token["headers"]
        dados = await _montar_inventario_completo(client, headers)

        response = await client.get(
            f"{INVENTARIO_URL}/{dados['aeronave']['id']}?nome=vu", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["equipamento_nome"] == "VUHF1"


# ================================================================== #
#  T08–T09: Ordenação e Agrupamento
# ================================================================== #

class TestInventarioAgrupamento:
    """Testes de ordenação por compartimento/sistema."""

    @pytest.mark.asyncio
    async def test_t08_itens_ordenados_por_sistema_e_nome(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T08: DADO inventário com itens em compartimentos distintos
             QUANDO consultar inventário
             ENTÃO itens devem vir ordenados por sistema e depois por nome.
        """
        headers = usuario_e_token["headers"]
        dados = await _montar_inventario_completo(client, headers)

        response = await client.get(
            f"{INVENTARIO_URL}/{dados['aeronave']['id']}", headers=headers
        )
        assert response.status_code == 200
        body = response.json()

        # Verificar que a ordenação por sistema está correta
        sistemas = [item["sistema"] for item in body]
        # "1P" vem antes de "COMP. ELETRONICO" alfabeticamente
        assert sistemas == sorted(sistemas), "Itens devem estar ordenados por sistema"

    @pytest.mark.asyncio
    async def test_t09_campo_sistema_presente_para_agrupamento(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T09: DADO inventário com itens instalados
             QUANDO consultar inventário
             ENTÃO todos os itens devem ter o campo 'sistema' preenchido
                  (necessário para agrupar no frontend).
        """
        headers = usuario_e_token["headers"]
        dados = await _montar_inventario_completo(client, headers)

        response = await client.get(
            f"{INVENTARIO_URL}/{dados['aeronave']['id']}", headers=headers
        )
        assert response.status_code == 200
        body = response.json()

        for item in body:
            assert item.get("sistema") is not None, \
                f"Item '{item.get('equipamento_nome')}' sem campo 'sistema' definido"


# ================================================================== #
#  T10–T12: Permissões e Segurança
# ================================================================== #

class TestInventarioPermissoes:
    """Testes de controle de acesso ao endpoint de inventário."""

    @pytest.mark.asyncio
    async def test_t10_inventario_requer_autenticacao(
        self, client: AsyncClient,
    ):
        """
        T10: DADO requisição sem token de autenticação
             QUANDO consultar inventário
             ENTÃO retornar 401 Unauthorized.
        """
        fake_id = str(uuid.uuid4())
        response = await client.get(f"{INVENTARIO_URL}/{fake_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_t11_mantenedor_pode_consultar_inventario(
        self, client: AsyncClient, usuario_mantenedor_e_token: dict,
    ):
        """
        T11: DADO usuário com perfil MANTENEDOR autenticado
             QUANDO consultar inventário
             ENTÃO deve ser permitido (inventário é somente leitura).
        """
        headers = usuario_mantenedor_e_token["headers"]
        # Criar uma aeronave via bypass (mantenedor não pode criar aeronave pela API)
        # Então testamos apenas que o endpoint não retorna 403
        fake_id = str(uuid.uuid4())
        response = await client.get(f"{INVENTARIO_URL}/{fake_id}", headers=headers)
        # 404 é aceitável (aeronave não existe), 403 seria falha
        assert response.status_code != 403, "Mantenedor deve ter acesso ao inventário"

    @pytest.mark.asyncio
    async def test_t12_inventario_e_somente_leitura(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T12: DADO requisição POST para o endpoint de inventário
             QUANDO tentar criar via POST
             ENTÃO retornar 405 Method Not Allowed (endpoint é GET only).
        """
        headers = usuario_e_token["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"{INVENTARIO_URL}/{fake_id}",
            json={"dados": "invalidos"},
            headers=headers,
        )
        assert response.status_code == 405


# ================================================================== #
#  T13–T15: Isolamento entre Aeronaves
# ================================================================== #

class TestInventarioIsolamento:
    """Testes de isolamento de dados entre aeronaves."""

    @pytest.mark.asyncio
    async def test_t13_inventario_nao_mistura_aeronaves(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T13: DADO aeronave A com 2 itens e aeronave B com 1 item
             QUANDO consultar inventário da aeronave A
             ENTÃO retornar apenas 2 itens (sem misturar com os da B).
        """
        headers = usuario_e_token["headers"]

        # Aeronave A com 2 equipamentos
        aeronave_a = await _criar_aeronave(client, headers, "5910", "SN-ISO-A")
        equip1 = await _criar_equipamento(client, headers, "GPS-A", "066-A", "1P")
        equip2 = await _criar_equipamento(client, headers, "ELT-A", "453-A", "COMP. ELT/OBOGS")
        item1 = await _criar_item(client, headers, equip1["id"], "SN-ISO-A1")
        item2 = await _criar_item(client, headers, equip2["id"], "SN-ISO-A2")
        await _instalar_item(client, headers, item1["id"], aeronave_a["id"])
        await _instalar_item(client, headers, item2["id"], aeronave_a["id"])

        # Aeronave B com 1 equipamento
        aeronave_b = await _criar_aeronave(client, headers, "5911", "SN-ISO-B")
        equip3 = await _criar_equipamento(client, headers, "VADR-B", "174-B", "COMP. ELT/OBOGS")
        item3 = await _criar_item(client, headers, equip3["id"], "SN-ISO-B1")
        await _instalar_item(client, headers, item3["id"], aeronave_b["id"])

        # Consultar inventário apenas da aeronave A
        response = await client.get(
            f"{INVENTARIO_URL}/{aeronave_a['id']}", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2, "Inventário da aeronave A deve conter apenas seus 2 itens"

        # Verificar que nenhum SN da aeronave B está presente
        sns = [item["numero_serie"] for item in body]
        assert "SN-ISO-B1" not in sns

    @pytest.mark.asyncio
    async def test_t14_item_transferido_aparece_apenas_na_aeronave_destino(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T14: DADO item que foi removido da aeronave A e instalado na aeronave B
             QUANDO consultar inventário da aeronave A
             ENTÃO item NÃO deve aparecer.
             QUANDO consultar inventário da aeronave B
             ENTÃO item DEVE aparecer.
        """
        headers = usuario_e_token["headers"]

        aeronave_a = await _criar_aeronave(client, headers, "5920", "SN-TRANSF-A")
        aeronave_b = await _criar_aeronave(client, headers, "5921", "SN-TRANSF-B")

        equip = await _criar_equipamento(client, headers, "EGIR-T", "342-T", "COMP. ELETRONICO")
        item = await _criar_item(client, headers, equip["id"], "SN-TRANSF-001")

        # Instalar na aeronave A
        inst = await _instalar_item(client, headers, item["id"], aeronave_a["id"])

        # Remover da aeronave A
        await client.patch(
            f"{EQUIP_URL}/instalacoes/{inst['id']}/remover",
            json={"data_remocao": date.today().isoformat()},
            headers=headers,
        )

        # Instalar na aeronave B
        await _instalar_item(client, headers, item["id"], aeronave_b["id"])

        # Inventário A: deve estar vazio
        resp_a = await client.get(f"{INVENTARIO_URL}/{aeronave_a['id']}", headers=headers)
        assert resp_a.status_code == 200
        assert len(resp_a.json()) == 0

        # Inventário B: deve conter o item transferido
        resp_b = await client.get(f"{INVENTARIO_URL}/{aeronave_b['id']}", headers=headers)
        assert resp_b.status_code == 200
        assert len(resp_b.json()) == 1
        assert resp_b.json()[0]["numero_serie"] == "SN-TRANSF-001"

    @pytest.mark.asyncio
    async def test_t15_dados_do_item_refletem_equipamento_correto(
        self, client: AsyncClient, usuario_e_token: dict,
    ):
        """
        T15: DADO item do tipo VUHF1 (PN 6110.3001.12) instalado na aeronave
             QUANDO consultar inventário
             ENTÃO o item deve trazer equipamento_nome="VUHF1" e
                  part_number="6110.3001.12" (join correto).
        """
        headers = usuario_e_token["headers"]
        aeronave = await _criar_aeronave(client, headers, "5930", "SN-JOIN-001")
        equip = await _criar_equipamento(client, headers, "VUHF1-J", "6110.3001.12-J", "COMP. ELETRONICO")
        item = await _criar_item(client, headers, equip["id"], "SN-JOIN-VUHF")
        await _instalar_item(client, headers, item["id"], aeronave["id"])

        response = await client.get(
            f"{INVENTARIO_URL}/{aeronave['id']}", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["equipamento_nome"] == "VUHF1-J"
        assert body[0]["part_number"] == "6110.3001.12-J"
        assert body[0]["numero_serie"] == "SN-JOIN-VUHF"


# ================================================================== #
#  T16: Rota de Página Frontend
# ================================================================== #

class TestInventarioPagina:
    """Testes da rota de página HTML /inventario."""

    @pytest.mark.asyncio
    async def test_t16_pagina_inventario_retorna_html(
        self, client: AsyncClient,
    ):
        """
        T16: DADO rota /inventario configurada
             QUANDO acessar GET /inventario
             ENTÃO retornar HTML com status 200.
        """
        response = await client.get("/inventario")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
