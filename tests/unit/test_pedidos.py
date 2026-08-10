"""
tests/unit/test_pedidos.py
Testes da Central de Pedidos — SAA29.

Cobertura (docs/backlog/modulo_pedidos/plano_implementacao.md §12):
    - test_criar_pedido_normal_sucesso                 — 201, PENDENTE, sem emergência
    - test_criar_pedido_emergencia_sem_numero_falha     — 422 (RN-03)
    - test_criar_pedido_emergencia_com_numero_sucesso   — 201, numero_emergencia preservado
    - test_numero_emergencia_forcado_null_quando_normal — RN-04
    - test_numero_pedido_sequencial                     — P-{ano}-{seq} incremental (RN-02)
    - test_atender_pedido_pendente                      — RN-11
    - test_atender_pedido_ja_atendido_conflito           — 409 (RN-10)
    - test_editar_pedido_atendido_conflito               — 409 (RN-09)
    - test_cancelar_sem_motivo_falha                     — 422 (RN-12)
    - test_cancelar_pedido_pendente                      — RN-12
    - test_mantenedor_nao_pode_criar/atender/cancelar    — 403 (RBAC)
    - test_soft_delete_e_restauracao                     — RN-13
    - test_excluir_pedido_ja_excluido_conflito           — 409 (RN-13, idempotência)
    - test_restaurar_pedido_ativo_conflito               — 409 (RN-13, idempotência)
    - test_listar_pedidos_com_filtros                    — filtros de listagem
    - test_resumo_contadores                             — GET /pedidos/resumo
    - test_export_csv_e_xlsx                             — GET /pedidos/export
    - test_atender_nao_altera_inventario                 — RN-11 (desacoplamento)
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipamentos.models import Instalacao

PEDIDOS_URL = "/pedidos/"
AERONAVES_URL = "/aeronaves/"


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def criar_aeronave(client: AsyncClient, headers: dict, dados: dict) -> dict:
    """Helper: cria uma aeronave com matrícula única e retorna o body JSON."""
    dados_copy = dados.copy()
    dados_copy["matricula"] = f"ANV-{uuid.uuid4().hex[:8].upper()}"
    resp = await client.post(AERONAVES_URL, json=dados_copy, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def criar_pedido(client: AsyncClient, headers: dict, aeronave_id: str, **kwargs) -> dict:
    """Helper: cria um pedido NORMAL (por padrão) e retorna o body JSON."""
    payload = {
        "aeronave_id": aeronave_id,
        "part_number": kwargs.get("part_number", "PN-0001"),
        "nomenclatura": kwargs.get("nomenclatura", "Rádio VUHF"),
        "quantidade": kwargs.get("quantidade", 1),
        "tipo_pedido": kwargs.get("tipo_pedido", "NORMAL"),
        "numero_emergencia": kwargs.get("numero_emergencia"),
        "observacao": kwargs.get("observacao"),
    }
    resp = await client.post(PEDIDOS_URL, json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ================================================================== #
#  Criação
# ================================================================== #

class TestCriarPedido:

    @pytest.mark.asyncio
    async def test_criar_pedido_normal_sucesso(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO payload NORMAL válido QUANDO criar ENTÃO 201, status PENDENTE, sem emergência."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        pedido = await criar_pedido(client, headers, aeronave["id"])

        assert pedido["status"] == "PENDENTE"
        assert pedido["tipo_pedido"] == "NORMAL"
        assert pedido["numero_emergencia"] is None
        assert pedido["numero_pedido"].startswith("P-")
        assert pedido["ativo"] is True

    @pytest.mark.asyncio
    async def test_criar_pedido_emergencia_sem_numero_falha(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO tipo EMERGENCIA sem numero_emergencia QUANDO criar ENTÃO 422 (RN-03)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        payload = {
            "aeronave_id": aeronave["id"],
            "part_number": "PN-0002",
            "nomenclatura": "GPS",
            "tipo_pedido": "EMERGENCIA",
        }
        resp = await client.post(PEDIDOS_URL, json=payload, headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_criar_pedido_emergencia_com_numero_sucesso(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO tipo EMERGENCIA com numero_emergencia QUANDO criar ENTÃO 201, número preservado."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        pedido = await criar_pedido(
            client, headers, aeronave["id"], tipo_pedido="EMERGENCIA", numero_emergencia="EMG-0099"
        )
        assert pedido["tipo_pedido"] == "EMERGENCIA"
        assert pedido["numero_emergencia"] == "EMG-0099"

    @pytest.mark.asyncio
    async def test_numero_emergencia_forcado_null_quando_normal(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO tipo NORMAL com numero_emergencia informado QUANDO criar ENTÃO campo forçado a NULL (RN-04)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        payload = {
            "aeronave_id": aeronave["id"],
            "part_number": "PN-0003",
            "nomenclatura": "Bateria",
            "tipo_pedido": "NORMAL",
            "numero_emergencia": "EMG-9999",
        }
        resp = await client.post(PEDIDOS_URL, json=payload, headers=headers)
        assert resp.status_code == 201, resp.text
        assert resp.json()["numero_emergencia"] is None

    @pytest.mark.asyncio
    async def test_numero_pedido_sequencial(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO dois pedidos criados no mesmo ano QUANDO consultados ENTÃO números sequenciais (RN-02)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        p1 = await criar_pedido(client, headers, aeronave["id"], part_number="PN-A")
        p2 = await criar_pedido(client, headers, aeronave["id"], part_number="PN-B")

        prefixo1 = p1["numero_pedido"].rsplit("-", 1)[0]
        prefixo2 = p2["numero_pedido"].rsplit("-", 1)[0]
        assert prefixo1 == prefixo2

        seq1 = int(p1["numero_pedido"].rsplit("-", 1)[1])
        seq2 = int(p2["numero_pedido"].rsplit("-", 1)[1])
        assert seq2 == seq1 + 1

    @pytest.mark.asyncio
    async def test_criar_pedido_aeronave_inexistente(
        self, client: AsyncClient, usuario_e_token: dict
    ):
        """DADO aeronave_id inexistente QUANDO criar ENTÃO 404 (RN-01)."""
        headers = usuario_e_token["headers"]
        payload = {
            "aeronave_id": str(uuid.uuid4()),
            "part_number": "PN-9999",
            "nomenclatura": "Peça Fantasma",
        }
        resp = await client.post(PEDIDOS_URL, json=payload, headers=headers)
        assert resp.status_code == 404


# ================================================================== #
#  Atender / Cancelar / Editar
# ================================================================== #

class TestCicloDeVida:

    @pytest.mark.asyncio
    async def test_atender_pedido_pendente(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido PENDENTE QUANDO atender ENTÃO status ATENDIDO + data_atendimento (RN-11)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        resp = await client.post(f"{PEDIDOS_URL}{pedido['id']}/atender", headers=headers)
        assert resp.status_code == 200, resp.text
        atendido = resp.json()
        assert atendido["status"] == "ATENDIDO"
        assert atendido["data_atendimento"] is not None
        assert "atendido_por_trigrama" in atendido

    @pytest.mark.asyncio
    async def test_atender_pedido_ja_atendido_conflito(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido já ATENDIDO QUANDO atender novamente ENTÃO 409 (RN-10)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        await client.post(f"{PEDIDOS_URL}{pedido['id']}/atender", headers=headers)
        resp = await client.post(f"{PEDIDOS_URL}{pedido['id']}/atender", headers=headers)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_editar_pedido_atendido_conflito(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido ATENDIDO QUANDO editar ENTÃO 409 — somente leitura (RN-09)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])
        await client.post(f"{PEDIDOS_URL}{pedido['id']}/atender", headers=headers)

        resp = await client.put(
            f"{PEDIDOS_URL}{pedido['id']}", json={"observacao": "tentativa de edição"}, headers=headers
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_editar_pedido_pendente_sucesso(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido PENDENTE QUANDO editar ENTÃO campos atualizados (RN-09)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        resp = await client.put(
            f"{PEDIDOS_URL}{pedido['id']}",
            json={"quantidade": 5, "observacao": "atualizado"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        atualizado = resp.json()
        assert atualizado["quantidade"] == 5
        assert atualizado["observacao"] == "atualizado"

    @pytest.mark.asyncio
    async def test_cancelar_sem_motivo_falha(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO cancelamento sem motivo QUANDO cancelar ENTÃO 422 (RN-12)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        resp = await client.post(f"{PEDIDOS_URL}{pedido['id']}/cancelar", json={"motivo": ""}, headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cancelar_pedido_pendente(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido PENDENTE QUANDO cancelar com motivo ENTÃO status CANCELADO (RN-12)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        resp = await client.post(
            f"{PEDIDOS_URL}{pedido['id']}/cancelar",
            json={"motivo": "Pane resolvida sem necessidade de substituição."},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        cancelado = resp.json()
        assert cancelado["status"] == "CANCELADO"
        assert cancelado["data_cancelamento"] is not None
        assert cancelado["motivo_cancelamento"] == "Pane resolvida sem necessidade de substituição."

    @pytest.mark.asyncio
    async def test_atender_nao_altera_inventario(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido PENDENTE QUANDO atender ENTÃO nenhuma linha é criada em `instalacoes` (RN-11)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        antes = (await db.execute(select(func.count()).select_from(Instalacao))).scalar_one()
        resp = await client.post(f"{PEDIDOS_URL}{pedido['id']}/atender", headers=headers)
        assert resp.status_code == 200
        depois = (await db.execute(select(func.count()).select_from(Instalacao))).scalar_one()

        assert antes == depois


# ================================================================== #
#  RBAC
# ================================================================== #

class TestPermissoes:

    # Nota (as três variações abaixo): um HTTPException 403 atravessa a
    # yield-dependency `get_db` e o `override_get_db` de teste captura essa
    # exceção com rollback() na sessão COMPARTILHADA (mesma sessão dos
    # fixtures de usuário/aeronave) — inclusive derrubando o próprio usuário
    # que fez a chamada, ainda não commitado. Por isso cada variação de RBAC
    # é um teste isolado com exatamente UM disparo de 403, sempre como
    # última ação — nenhuma chamada autenticada acontece depois dele.

    @pytest.mark.asyncio
    async def test_mantenedor_nao_pode_criar(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
        usuario_mantenedor_e_token: dict,
        dados_aeronave_valida: dict,
    ):
        """DADO usuário MANTENEDOR QUANDO criar pedido ENTÃO 403."""
        headers_admin = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)

        payload = {"aeronave_id": aeronave["id"], "part_number": "PN-M", "nomenclatura": "Item"}
        resp = await client.post(PEDIDOS_URL, json=payload, headers=usuario_mantenedor_e_token["headers"])
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_mantenedor_nao_pode_atender(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
        usuario_mantenedor_e_token: dict,
        dados_aeronave_valida: dict,
    ):
        """DADO usuário MANTENEDOR QUANDO atender pedido ENTÃO 403."""
        headers_admin = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers_admin, aeronave["id"])

        resp = await client.post(
            f"{PEDIDOS_URL}{pedido['id']}/atender", headers=usuario_mantenedor_e_token["headers"]
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_mantenedor_nao_pode_cancelar(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
        usuario_mantenedor_e_token: dict,
        dados_aeronave_valida: dict,
    ):
        """DADO usuário MANTENEDOR QUANDO cancelar pedido ENTÃO 403."""
        headers_admin = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers_admin, aeronave["id"])

        resp = await client.post(
            f"{PEDIDOS_URL}{pedido['id']}/cancelar",
            json={"motivo": "x"},
            headers=usuario_mantenedor_e_token["headers"],
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_encarregado_pode_gerir(
        self,
        client: AsyncClient,
        usuario_e_token: dict,
        usuario_encarregado_e_token: dict,
        dados_aeronave_valida: dict,
    ):
        """DADO usuário ENCARREGADO QUANDO criar pedido ENTÃO 201 (RBAC)."""
        headers_admin = usuario_e_token["headers"]
        headers_encarregado = usuario_encarregado_e_token["headers"]
        aeronave = await criar_aeronave(client, headers_admin, dados_aeronave_valida)

        pedido = await criar_pedido(client, headers_encarregado, aeronave["id"])
        assert pedido["status"] == "PENDENTE"

    @pytest.mark.asyncio
    async def test_criar_pedido_requer_autenticacao(self, client: AsyncClient):
        """DADO payload válido sem Authorization QUANDO criar ENTÃO 401."""
        payload = {"aeronave_id": str(uuid.uuid4()), "part_number": "PN-X", "nomenclatura": "Item"}
        resp = await client.post(PEDIDOS_URL, json=payload)
        assert resp.status_code == 401


# ================================================================== #
#  Soft Delete / Restauração
# ================================================================== #

class TestSoftDelete:

    @pytest.mark.asyncio
    async def test_soft_delete_e_restauracao(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido ativo QUANDO excluir ENTÃO some da listagem padrão, aparece em
        `excluidos=true` e reaparece na listagem padrão após restaurar (RN-13)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])
        pedido_id = pedido["id"]

        resp_del = await client.delete(f"{PEDIDOS_URL}{pedido_id}", headers=headers)
        assert resp_del.status_code == 204

        resp_lista = await client.get(
            PEDIDOS_URL, params={"aeronave_id": aeronave["id"]}, headers=headers
        )
        assert all(p["id"] != pedido_id for p in resp_lista.json())

        resp_excluidos = await client.get(
            PEDIDOS_URL, params={"aeronave_id": aeronave["id"], "excluidos": "true"}, headers=headers
        )
        assert any(p["id"] == pedido_id for p in resp_excluidos.json())

        resp_restaurar = await client.post(f"{PEDIDOS_URL}{pedido_id}/restaurar", headers=headers)
        assert resp_restaurar.status_code == 200

        resp_lista2 = await client.get(
            PEDIDOS_URL, params={"aeronave_id": aeronave["id"]}, headers=headers
        )
        assert any(p["id"] == pedido_id for p in resp_lista2.json())

    @pytest.mark.asyncio
    async def test_excluir_pedido_ja_excluido_conflito(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido já excluído QUANDO excluir novamente ENTÃO 409 (RN-13, idempotência).

        O 409 (HTTPException) é o disparo que aciona o rollback do
        override_get_db de teste sobre a sessão compartilhada — mantido como
        última chamada do teste (ver nota em TestPermissoes.test_mantenedor_sem_permissao).
        """
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        resp_del = await client.delete(f"{PEDIDOS_URL}{pedido['id']}", headers=headers)
        assert resp_del.status_code == 204

        resp_del_dup = await client.delete(f"{PEDIDOS_URL}{pedido['id']}", headers=headers)
        assert resp_del_dup.status_code == 409

    @pytest.mark.asyncio
    async def test_restaurar_pedido_ativo_conflito(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedido ativo QUANDO restaurar ENTÃO 409 (RN-13, idempotência)."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        pedido = await criar_pedido(client, headers, aeronave["id"])

        resp_restaurar = await client.post(f"{PEDIDOS_URL}{pedido['id']}/restaurar", headers=headers)
        assert resp_restaurar.status_code == 409


# ================================================================== #
#  Listagem, Resumo e Exportação
# ================================================================== #

class TestListagemEResumo:

    @pytest.mark.asyncio
    async def test_listar_pedidos_com_filtros(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedidos de tipos e status distintos QUANDO filtrar ENTÃO retorna apenas os correspondentes."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        normal = await criar_pedido(client, headers, aeronave["id"], part_number="PN-NORMAL")
        emergencia = await criar_pedido(
            client, headers, aeronave["id"], part_number="PN-EMG",
            tipo_pedido="EMERGENCIA", numero_emergencia="EMG-1234",
        )
        await client.post(f"{PEDIDOS_URL}{normal['id']}/atender", headers=headers)

        resp_status = await client.get(
            PEDIDOS_URL, params={"aeronave_id": aeronave["id"], "status": "ATENDIDO"}, headers=headers
        )
        assert resp_status.status_code == 200
        ids_status = [p["id"] for p in resp_status.json()]
        assert normal["id"] in ids_status
        assert emergencia["id"] not in ids_status

        resp_tipo = await client.get(
            PEDIDOS_URL, params={"aeronave_id": aeronave["id"], "tipo_pedido": "EMERGENCIA"}, headers=headers
        )
        ids_tipo = [p["id"] for p in resp_tipo.json()]
        assert emergencia["id"] in ids_tipo
        assert normal["id"] not in ids_tipo

        resp_texto = await client.get(
            PEDIDOS_URL, params={"texto": "PN-EMG"}, headers=headers
        )
        ids_texto = [p["id"] for p in resp_texto.json()]
        assert emergencia["id"] in ids_texto

    @pytest.mark.asyncio
    async def test_resumo_contadores(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedidos criados QUANDO consultar /resumo ENTÃO contadores batem com o filtro de aeronave."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)

        p1 = await criar_pedido(client, headers, aeronave["id"], part_number="PN-R1")
        await criar_pedido(
            client, headers, aeronave["id"], part_number="PN-R2",
            tipo_pedido="EMERGENCIA", numero_emergencia="EMG-4321",
        )
        await client.post(f"{PEDIDOS_URL}{p1['id']}/atender", headers=headers)

        resp = await client.get(
            f"{PEDIDOS_URL}resumo", params={"aeronave_id": aeronave["id"]}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        resumo = resp.json()
        assert resumo["total"] == 2
        assert resumo["pendentes"] == 1
        assert resumo["atendidos"] == 1
        assert resumo["emergencias"] == 1

    @pytest.mark.asyncio
    async def test_export_csv_e_xlsx(
        self, client: AsyncClient, usuario_e_token: dict, dados_aeronave_valida: dict
    ):
        """DADO pedidos existentes QUANDO exportar ENTÃO 200 com anexo CSV/XLSX."""
        headers = usuario_e_token["headers"]
        aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
        await criar_pedido(client, headers, aeronave["id"])

        resp_csv = await client.get(f"{PEDIDOS_URL}export", params={"format": "csv"}, headers=headers)
        assert resp_csv.status_code == 200
        assert "attachment" in resp_csv.headers.get("content-disposition", "")

        resp_xlsx = await client.get(f"{PEDIDOS_URL}export", params={"format": "xlsx"}, headers=headers)
        assert resp_xlsx.status_code == 200
        assert "attachment" in resp_xlsx.headers.get("content-disposition", "")
